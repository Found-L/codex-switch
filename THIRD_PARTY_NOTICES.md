# Third-party software

The Windows distribution bundles CPython, tomlkit, PySide6 Essentials, shiboken6, Qt dynamic libraries and the PyInstaller bootloader. Their licenses remain applicable.

- CPython 3.14: Python Software Foundation License Version 2; https://docs.python.org/3/license.html
- tomlkit 0.15.2: MIT; https://github.com/python-poetry/tomlkit/blob/main/LICENSE
- PySide6 Essentials and shiboken6 6.12.0: used under GNU LGPL version 3; https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.12.0
- Qt 6.12.0 libraries: used under GNU LGPL version 3; https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v6.12.0 and https://code.qt.io/cgit/qt/qtdeclarative.git/tree/?h=v6.12.0
- PyInstaller 6.22.3: GPL-2.0-or-later with bootloader exception permitting distribution of bundled applications under their own license; https://pyinstaller.org/en/stable/license.html
- Inno Setup creates the installer; https://jrsoftware.org/files/is/license.txt

Qt and PySide libraries are unmodified, dynamically linked and distributed separately in the portable application directory. You may replace them with compatible modified versions and reverse engineer the application for debugging such modifications as allowed by the LGPL. Application source and build instructions: https://github.com/Found-L/codex-switch. Corresponding Qt/PySide source is available at the versioned upstream links above and https://download.qt.io/official_releases/QtForPython/pyside6/. LGPL-3.0 and GPL-3.0 license texts are included in `licenses`; the LGPL incorporates provisions of GPL-3.0. The application's MIT license does not restrict the LGPL rights for these components.

Build tooling also includes Pillow, altgraph, packaging, pefile, pyinstaller-hooks-contrib, pywin32-ctypes and setuptools. Pillow renders the project's original icon and is not a runtime dependency. Windows system fonts are not redistributed. Bundled license texts are included in the `licenses` directory produced by the build script.
