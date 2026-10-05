"""Check the container's read-only evidence bind mount using disposable files."""
import errno
import json
from pathlib import Path
import subprocess
import sys

evidence = Path("/evidence/evidence.E01")
result = {}
for name, path, mode in (("open_for_write", evidence, "r+b"),
                         ("create_file", Path("/evidence/write-test"), "xb")):
    try:
        with path.open(mode):
            pass
    except OSError as error:
        result[name] = {"errno": error.errno, "message": str(error)}
        if error.errno != errno.EROFS:
            raise RuntimeError("Expected a read-only filesystem error") from error
    else:
        raise RuntimeError(f"Read-only boundary failed: {name}")
Path("/results/readonly.json").write_text(json.dumps(result, indent=2) + "\n")
subprocess.run([sys.executable, "/probe/probe.py", "/results/read",
                "--extended", "--source", "/evidence"], check=True, timeout=120)
