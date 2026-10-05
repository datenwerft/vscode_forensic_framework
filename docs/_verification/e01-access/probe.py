#!/usr/bin/env python3
"""Disposable E01 access experiment. Only generates/reads its own synthetic evidence."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import shutil
import select
import struct
import subprocess
import time

PAYLOAD = b"Forensic workspace synthetic evidence.\n"
LARGE = b"".join(hashlib.sha256(str(i).encode()).digest() for i in range(98304))


def fixture(extended=False):
    # MBR + 8 MiB FAT16, one allocated file; deterministic filler forces segmentation.
    start, sectors = 2048, 16384
    image = bytearray((start + sectors) * 512)
    image[446:462] = struct.pack("<B3sB3sII", 0, b"\0\2\0", 6,
                                  b"\xfe\xff\xff", start, sectors)
    image[510:512] = b"\x55\xaa"
    base = start * 512
    boot = bytearray(512)
    boot[:11] = b"\xeb\x3c\x90MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11,
                     512, 2, 1, 2, 512, sectors, 0xf8, 32, 32, 64, start, 0)
    boot[36:62] = struct.pack("<BBBI11s8s", 0x80, 0, 0x29, 1234,
                              b"E01PROOF   ", b"FAT16   ")
    boot[510:512] = b"\x55\xaa"
    image[base:base + 512] = boot
    for sector in (1, 33):
        struct.pack_into("<HHH", image, base + sector * 512, 0xfff8, 0xffff, 0xffff)
    root = base + 65 * 512
    image[root:root + 11] = b"HELLO   TXT"
    image[root + 11] = 0x20
    struct.pack_into("<H", image, root + 26, 2)
    struct.pack_into("<I", image, root + 28, len(PAYLOAD))
    data = base + 97 * 512
    image[data:data + len(PAYLOAD)] = PAYLOAD
    # Unallocated sectors are synthetic deterministic bytes, not real user data.
    for offset in range(data + 1024, len(image), 32):
        image[offset:offset + 32] = hashlib.sha256(str(offset).encode()).digest()[:len(image)-offset]
    if extended:
        clusters = len(LARGE) // 1024
        for sector in (1, 33):
            for cluster in range(3, 3 + clusters):
                following = cluster + 1 if cluster < 2 + clusters else 0xffff
                struct.pack_into("<H", image, base + sector * 512 + cluster * 2, following)
        entry = root + 32
        image[entry:entry + 11] = b"SPAN    BIN"
        image[entry + 11] = 0x20
        struct.pack_into("<H", image, entry + 26, 3)
        struct.pack_into("<I", image, entry + 28, len(LARGE))
        image[data + 1024:data + 1024 + len(LARGE)] = LARGE
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory; must not already exist")
    parser.add_argument("--extended", action="store_true", help="3 MiB file, corruption and cancellation checks")
    parser.add_argument("--source", type=Path, help="reuse a generated probe's segment directory read-only")
    parser.add_argument("--raw", type=Path, help="synthetic partitionless ext4 image containing HELLO.TXT and SPAN.BIN")
    args = parser.parse_args()
    required = ["ewfacquirestream", "ewfinfo", "ewfverify", "mmls", "fls", "icat"]
    missing = [tool for tool in required if not shutil.which(tool)]
    if missing:
        parser.error("Missing required tools: " + ", ".join(missing))
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output.resolve()
    report = {"platform": platform.platform(), "machine": platform.machine(),
              "tools": {t: shutil.which(t) for t in required}, "commands": [], "checks": {},
              "extended": args.extended, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def run(argv, data=None, expect_success=True, binary=False):
        before = time.monotonic()
        result = subprocess.run([str(a) for a in argv], input=data, capture_output=True, timeout=90)
        report["commands"].append({"argv": [str(a) for a in argv],
                                   "returncode": result.returncode,
                                   "seconds": time.monotonic() - before,
                                   "stdout": (f"{len(result.stdout)} binary bytes; SHA256=" + hashlib.sha256(result.stdout).hexdigest()) if binary else result.stdout.decode(errors="replace"),
                                   "stderr": result.stderr.decode(errors="replace")})
        if expect_success and result.returncode:
            raise RuntimeError(f"{argv[0]} failed: {result.stderr.decode(errors='replace')}")
        return result

    def hashes(paths):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    try:
        for tool in ("ewfinfo", "fls"):
            run([tool, "-V"])
        run(["fls", "-f", "list"], expect_success=False)
        raw = args.raw.read_bytes() if args.raw else fixture(args.extended)
        report["logical_image_sha256"] = hashlib.sha256(raw).hexdigest()
        if not args.source:
            run(["ewfacquirestream", "-q", "-c", "none", "-S", "1048576",
                 "-t", out / "evidence", "-d", "sha256"], raw)
        source = args.source.resolve() if args.source else out
        report["source"] = str(source)
        segments = sorted(source.glob("evidence.E[0-9][0-9]"))
        assert len(segments) > 2, "Fixture must span multiple EWF segments"
        report["segments"] = [p.name for p in segments]
        before = hashes(segments)
        report["source_sha256_before"] = before
        # Defense in depth for this experiment, not an engine security boundary.
        if not args.source:
            for segment in segments:
                segment.chmod(0o444)
        first = segments[0]
        run(["ewfinfo", first])
        if args.raw:
            offset = "0"
            report["filesystem_fixture"] = "partitionless ext4"
        else:
            partitions = run(["mmls", "-i", "ewf", first]).stdout.decode()
            partition = re.search(r"^\d+:\s+\d+:\d+\s+(\d+)\s+\d+\s+\d+\s+.*FAT16", partitions, re.M)
            assert partition, "FAT16 partition not discovered"
            offset = str(int(partition.group(1)))
            report["filesystem_fixture"] = "MBR FAT16"
        listing = run(["fls", "-i", "ewf", "-o", offset, first]).stdout.decode()
        found = re.search(r"r/r\s+(\d+):\s+HELLO.TXT", listing)
        assert found, "Known file not found"
        content = run(["icat", "-i", "ewf", "-o", offset, first, found.group(1)]).stdout
        assert content == PAYLOAD, "Extracted content differs"
        report["checks"]["first_segment_to_file"] = True
        report["file_sha256"] = hashlib.sha256(content).hexdigest()
        if args.extended:
            span = re.search(r"r/r\s+(\d+):\s+SPAN.BIN", listing)
            assert span, "Large file not found"
            command = ["icat", "-i", "ewf", "-o", offset, str(first), span.group(1)]
            large = run(command, binary=True).stdout
            assert large == LARGE, "Cross-segment file differs"
            report["large_file_sha256"] = hashlib.sha256(large).hexdigest()
            report["checks"]["cross_segment_file"] = True
            # Block a real reader on its output pipe, then cancel and reap it.
            # This checks active-process cancellation, not cancellation during I/O.
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                ready, _, _ = select.select([process.stdout], [], [], 5)
                assert ready and process.stdout.read(4096), "Reader produced no bytes"
                assert process.poll() is None, "Reader finished before cancellation"
                process.terminate()
                process.communicate(timeout=5)
                report["cancellation_returncode"] = process.returncode
                assert process.returncode != 0, "Reader was not interrupted"
                report["checks"]["active_reader_cancelled_and_reaped"] = True
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        verification = run(["ewfverify", "-q", "-d", "sha256", first])
        assert report["logical_image_sha256"] in verification.stdout.decode()
        report["checks"]["logical_image_verification"] = True
        # Fault injection uses separate copies; original segments remain untouched.
        broken = out / "missing-segment"
        broken.mkdir()
        for p in segments:
            if p != segments[1]:
                shutil.copyfile(p, broken / p.name)
        failed = run(["ewfverify", "-q", broken / first.name], expect_success=False)
        assert failed.returncode > 0, "Missing segment was not cleanly rejected"
        report["checks"]["missing_segment_rejected"] = True
        if args.extended:
            for fault in ("missing-final", "truncated-middle"):
                target = out / fault
                target.mkdir()
                for p in segments:
                    if fault == "missing-final" and p == segments[-1]:
                        continue
                    shutil.copyfile(p, target / p.name)
                if fault == "truncated-middle":
                    damaged = target / segments[1].name
                    with damaged.open("r+b") as stream:
                        stream.truncate(damaged.stat().st_size // 2)
                failed = run(["ewfverify", "-q", target / first.name], expect_success=False)
                assert failed.returncode > 0, f"{fault} was not cleanly rejected"
                report["checks"][fault + "_rejected"] = True
        report["source_sha256_after"] = hashes(segments)
        assert before == report["source_sha256_after"], "Source bytes changed"
        report["checks"]["source_bytes_unchanged"] = True
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{report['status']}: {out / 'report.json'}")


if __name__ == "__main__":
    main()
