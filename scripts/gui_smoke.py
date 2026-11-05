"""Prove the packaged GUI contains a working Tcl/Tk runtime, including on CI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="codex-switch-gui-report-") as temporary:
    report = Path(temporary) / "result.json"
    result = subprocess.run([str(Path(sys.argv[1]).resolve()), "--self-test", str(report)], timeout=30)
    if result.returncode or not report.is_file():
        raise SystemExit("Frozen GUI self-test did not complete.")
    data = json.loads(report.read_text("utf-8"))
    if not data.get("ok"):
        raise SystemExit("Frozen GUI startup failed: " + str(data.get("error_type")))
    print("Packaged GUI startup passed: Tcl " + data["tcl"] + ", Tk " + data["tk"])
