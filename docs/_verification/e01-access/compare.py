"""Validate recorded runs and retain compact, shareable results without binary images."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAMES = ["macos-01", "linux-01", "macos-extended", "linux-suite/baseline",
         "linux-suite/extended", "linux-suite/macos-evidence", "linux-suite/ext4",
         "macos-linux-evidence", "macos-ext4", "readonly-result/read"]
reports = {name: json.loads((ROOT / "runs" / name / "report.json").read_text()) for name in NAMES}
for name, report in reports.items():
    if name == "linux-01":
        assert report["status"] == "failed"
        assert report["commands"][-1]["returncode"] == -11
    else:
        assert report["status"] == "passed", name
        assert report["checks"] and all(report["checks"].values()), name
        assert report["source_sha256_before"] == report["source_sha256_after"], name

comparisons = []
for left, right, same_segments in [
    ("macos-01", "linux-suite/baseline", False),
    ("macos-extended", "linux-suite/extended", False),
    ("macos-extended", "linux-suite/macos-evidence", True),
    ("linux-suite/extended", "macos-linux-evidence", True),
    ("linux-suite/ext4", "macos-ext4", True),
    ("macos-extended", "readonly-result/read", True),
]:
    fields = ["logical_image_sha256", "file_sha256"]
    if reports[left].get("extended"):
        fields.append("large_file_sha256")
    if same_segments:
        fields.append("source_sha256_before")
    for field in fields:
        assert reports[left][field] == reports[right][field], (left, right, field)
    comparisons.append({"left": left, "right": right, "matched": fields})

readonly = json.loads((ROOT / "runs/readonly-result/readonly.json").read_text())
assert all(value["errno"] == 30 for value in readonly.values())
destination = ROOT / "results"
destination.mkdir(exist_ok=True)
for name, report in reports.items():
    (destination / (name.replace("/", "--") + ".json")).write_text(json.dumps(report, indent=2) + "\n")
summary = {"comparisons": comparisons, "readonly_boundary": readonly,
           "linux_environment": json.loads((ROOT / "runs/linux-suite/environment.json").read_text()),
           "passed_runs": len(reports) - 1, "known_failed_runs": 1}
(destination / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
print(f"Validated {len(reports)-1} passing runs, 1 recorded Linux failure, {len(comparisons)} comparisons")
