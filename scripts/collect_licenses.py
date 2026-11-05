"""Collect actual license texts from the build environment into the distribution."""
import importlib.metadata
from pathlib import Path
import shutil
import sys
import tkinter

root = Path(__file__).resolve().parents[1]
destination = root / "dist" / "CodexSwitch" / "licenses"
destination.mkdir(parents=True, exist_ok=True)
shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", destination / "PYTHON-LICENSE.txt")
tcl = Path(tkinter.Tcl().eval("info library"))
tk_license = tcl.parent / "tk8.6" / "license.terms"
if not tk_license.is_file():
    raise SystemExit("Tcl/Tk license file not found.")
shutil.copyfile(tk_license, destination / "TCL-TK-LICENSE.txt")
for name in ("tomlkit", "pyinstaller"):
    distribution = importlib.metadata.distribution(name)
    found = False
    for entry in distribution.files:
        if "/licenses/" in str(entry).replace("\\", "/"):
            file = distribution.locate_file(entry)
            if file.is_file():
                shutil.copyfile(file, destination / (name.upper() + "-" + file.name))
                found = True
    if not found:
        raise SystemExit("Missing distribution license for " + name)
