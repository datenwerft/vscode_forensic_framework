"""Run inside the test container; all generated data belongs under /work."""
import json
from pathlib import Path
import subprocess
import sys

from probe import LARGE, PAYLOAD


def run(*args):
    subprocess.run(args, check=True, timeout=120)


def main():
    root = Path("/work/linux-suite")
    root.mkdir(exist_ok=False)
    (root / "environment.json").write_text(json.dumps({
        "os_release": Path("/etc/os-release").read_text(),
        "packages": subprocess.check_output(["dpkg-query", "-W", "ewf-tools", "libewf2",
                                             "libbfio1", "sleuthkit", "e2fsprogs"], text=True),
    }, indent=2) + "\n")
    probe = "/probe/probe.py"
    run(sys.executable, probe, str(root / "baseline"))
    run(sys.executable, probe, str(root / "extended"), "--extended")
    run(sys.executable, probe, str(root / "macos-evidence"), "--extended",
        "--source", "/probe/runs/macos-extended")
    contents = root / "ext4-contents"
    contents.mkdir()
    (contents / "HELLO.TXT").write_bytes(PAYLOAD)
    (contents / "SPAN.BIN").write_bytes(LARGE)
    raw = root / "ext4.raw"
    with raw.open("xb") as stream:
        stream.truncate(32 * 1024 * 1024)
    run("mke2fs", "-q", "-t", "ext4", "-F", "-d", str(contents), str(raw))
    run(sys.executable, probe, str(root / "ext4"), "--extended", "--raw", str(raw))


if __name__ == "__main__":
    main()
