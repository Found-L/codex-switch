"""Collect actual license texts from the build environment into the distribution."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
destination = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "dist" / "CodexSwitch" / "licenses"
destination.mkdir(parents=True, exist_ok=True)
python_license = next((path for path in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "Resources" / "LICENSE.txt", root / "third_party" / "PYTHON-LICENSE.txt") if path.is_file()), None)
if python_license is None:
    raise SystemExit("Python license is missing from the build interpreter.")
shutil.copyfile(python_license, destination / "PYTHON-LICENSE.txt")
for file in (root / "third_party").glob("QT-*.txt"):
    shutil.copyfile(file, destination / file.name)
for name in ("tomlkit", "pyinstaller", "PySide6-Essentials", "shiboken6"):
    distribution = importlib.metadata.distribution(name)
    found = False
    for entry in distribution.files:
        if "/licenses/" in str(entry).replace("\\", "/").lower() or entry.name.lower().startswith(("license", "copying")):
            file = distribution.locate_file(entry)
            if file.is_file():
                shutil.copyfile(file, destination / (name.upper() + "-" + file.name))
                found = True
    if not found and name in ("PySide6-Essentials", "shiboken6"):
        # Some macOS wheels omit license files from RECORD. Our selected LGPL
        # license is vendored independently of wheel packaging differences.
        shutil.copyfile(root / "third_party/QT-LGPL-3.0.txt", destination / (name.upper() + "-LGPL-3.0.txt"))
        found = True
    if not found:
        raise SystemExit("Missing distribution license for " + name)
