"""Collect actual license texts from the build environment into the distribution."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
destination = root / "dist" / "CodexSwitch" / "licenses"
destination.mkdir(parents=True, exist_ok=True)
shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", destination / "PYTHON-LICENSE.txt")
for file in (root / "third_party").glob("QT-*.txt"):
    shutil.copyfile(file, destination / file.name)
for name in ("tomlkit", "pyinstaller", "PySide6-Essentials", "shiboken6"):
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
