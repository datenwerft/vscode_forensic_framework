"""Native macOS write-boundary experiment using only disposable generated evidence."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import select
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CANARY = b"Disposable write-boundary canary.\n"
OPERATIONS = ["overwrite", "append", "truncate", "create", "rename", "unlink",
              "chmod", "utime", "symlink_write", "hardlink_write", "relative_write",
              "child_write"]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def stage(directory):
    directory.mkdir()
    for name in OPERATIONS:
        path = directory / name
        path.write_bytes(CANARY)
        path.chmod(0o666)
    (directory / "symlink").symlink_to(directory / "symlink_write")
    os.link(directory / "hardlink_write", directory / "hardlink")


def attempt(name, directory):
    path = directory / name
    if name == "overwrite":
        with path.open("r+b") as stream:
            stream.write(b"CHANGED")
    elif name == "append":
        with path.open("ab") as stream:
            stream.write(b"CHANGED")
    elif name == "truncate":
        os.truncate(path, 0)
    elif name == "create":
        (directory / "new-file").write_bytes(b"CHANGED")
    elif name == "rename":
        path.rename(directory / "renamed")
    elif name == "unlink":
        path.unlink()
    elif name == "chmod":
        path.chmod(0o600)
    elif name == "utime":
        os.utime(path, (1000000, 1000000))
    elif name == "symlink_write":
        (directory / "symlink").write_bytes(b"CHANGED")
    elif name == "hardlink_write":
        (directory / "hardlink").write_bytes(b"CHANGED")
    elif name == "relative_write":
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_TRUNC, dir_fd=descriptor)
            os.close(fd)
        finally:
            os.close(descriptor)
    elif name == "child_write":
        child = subprocess.run([sys.executable, "-B", str(HERE / "macos_readonly.py"),
                                "--child-write", str(path)], capture_output=True,
                               text=True, timeout=10, close_fds=True)
        require(child.returncode == 0, "Child did not return a structured result")
        result = json.loads(child.stdout)
        if result["errno"]:
            raise OSError(result["errno"], result["message"])


def worker(directory, protected, evidence=None):
    report = {"protected": protected, "attempts": {}, "reads": {}}
    for name in OPERATIONS:
        try:
            attempt(name, directory)
            outcome = {"allowed": True}
        except OSError as error:
            outcome = {"allowed": False, "errno": error.errno, "message": str(error)}
        report["attempts"][name] = outcome
    require(all(not r["allowed"] and r["errno"] in (errno.EPERM, errno.EACCES)
                for r in report["attempts"].values()) if protected
            else all(r["allowed"] for r in report["attempts"].values()),
            "Write outcomes differ from the expected boundary: " + json.dumps(report))
    if evidence:
        # Import without creating bytecode; all tools inherit the sandbox.
        from probe import LARGE, PAYLOAD

        def run(command):
            result = subprocess.run([str(a) for a in command], capture_output=True,
                                    timeout=30, close_fds=True)
            require(result.returncode == 0, f"Reader failed: {command}: {result.stderr!r}")
            return result.stdout

        for kind, offset in (("fat16", "2048"), ("ext4", "0")):
            first = evidence / kind / "evidence.E01"
            # Test the actual generated source, not only adjacent canary files.
            try:
                with first.open("r+b"):
                    pass
            except OSError as error:
                require(error.errno in (errno.EPERM, errno.EACCES), "Unexpected source denial")
                source_denial = error.errno
            else:
                raise RuntimeError("Evidence was writable")
            info = run(["ewfinfo", first]).decode()
            if kind == "fat16":
                partitions = run(["mmls", "-i", "ewf", first]).decode()
                require(re.search(r"^\d+:\s+\d+:\d+\s+0*2048\s+.*FAT16", partitions, re.M),
                        "FAT16 partition missing")
            listing = run(["fls", "-i", "ewf", "-o", offset, first]).decode()
            hashes = {}
            for filename, expected in (("HELLO.TXT", PAYLOAD), ("SPAN.BIN", LARGE)):
                match = re.search(r"r/r\s+(\d+):\s+" + re.escape(filename), listing)
                require(match is not None, f"Missing {filename}")
                command = ["icat", "-i", "ewf", "-o", offset, str(first), match.group(1)]
                data = run(command)
                require(data == expected, f"Wrong bytes in {kind}/{filename}")
                hashes[filename] = hashlib.sha256(data).hexdigest()
            verification = run(["ewfverify", "-q", "-d", "sha256", first]).decode()
            # Cancel the last reader (the large file) after it starts producing output.
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       close_fds=True)
            try:
                ready, _, _ = select.select([process.stdout], [], [], 5)
                require(ready and process.stdout.read(4096), "Reader never produced bytes")
                require(process.poll() is None, "Reader completed before cancellation")
                process.terminate()
                process.communicate(timeout=5)
                require(process.returncode != 0, "Reader not interrupted")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            report["reads"][kind] = {"source_write_errno": source_denial,
                                     "files_sha256": hashes, "metadata": info,
                                     "listing": listing, "verification": verification,
                                     "cancel_returncode": process.returncode}
    print(json.dumps(report))


def snapshot(directory):
    return {str(p.relative_to(directory)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
             "mode": p.stat().st_mode & 0o777, "size": p.stat().st_size,
             "mtime_ns": p.stat().st_mtime_ns}
            for p in directory.rglob("*") if p.is_file() and not p.is_symlink()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--protected", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--child-write", type=Path)
    args = parser.parse_args()
    if args.child_write:
        try:
            args.child_write.write_bytes(b"CHANGED")
            print(json.dumps({"errno": 0}))
        except OSError as error:
            print(json.dumps({"errno": error.errno, "message": str(error)}))
        return
    if args.worker:
        worker(args.worker, args.protected, args.evidence)
        return
    require(platform.system() == "Darwin", "This experiment requires macOS")
    require(args.output is not None, "An output directory is required")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    report = {"platform": platform.platform(), "status": "running",
              "profile": (HERE / "macos-readonly.sb").read_text(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        stage(root / "control")
        stage(root / "protected")
        evidence = root / "evidence"
        for kind, source in (("fat16", "macos-extended"), ("ext4", "linux-suite/ext4")):
            dest = evidence / kind
            dest.mkdir(parents=True)
            originals = sorted((HERE / "runs" / source).glob("evidence.E[0-9][0-9]"))
            require(len(originals) > 2, f"Missing generated fixture: {source}")
            for p in originals:
                target = dest / p.name
                shutil.copyfile(p, target)
                target.chmod(0o666)
            # Establish that the actual evidence is writable outside the worker.
            with (dest / "evidence.E01").open("r+b"):
                pass
        before = {"evidence": snapshot(evidence), "canaries": snapshot(root / "protected")}
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        base = [sys.executable, "-B", str(Path(__file__).resolve())]
        for name, prefix, flags in (("control", [], []),
                ("protected", ["/usr/bin/sandbox-exec", "-f", str(HERE / "macos-readonly.sb")],
                 ["--protected", "--evidence", str(evidence)])):
            command = prefix + base + ["--worker", str(root / name)] + flags
            with open(os.devnull, "rb") as input_stream:
                result = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                        close_fds=True, stdin=input_stream, env=env)
            report[name + "_launch"] = {"command": command, "returncode": result.returncode,
                                          "stderr": result.stderr}
            require(result.returncode == 0, f"{name} worker failed: {result.stderr}")
            report[name] = json.loads(result.stdout)
        after = {"evidence": snapshot(evidence), "canaries": snapshot(root / "protected")}
        report["before"] = before
        report["after"] = after
        require(before == after, "Protected evidence or canaries changed")
        for kind, source in (("fat16", "macos-extended"), ("ext4", "linux-suite/ext4")):
            reference = json.loads((HERE / "runs" / source / "report.json").read_text())
            read = report["protected"]["reads"][kind]
            require(reference["logical_image_sha256"] in read["verification"], "Wrong logical hash")
            require(read["files_sha256"]["SPAN.BIN"] == reference["large_file_sha256"], "Wrong file hash")
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{report['status']}: {root / 'report.json'}")


if __name__ == "__main__":
    main()
