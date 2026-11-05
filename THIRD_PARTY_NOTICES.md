# Third-party software

Distribution bundles Python and its standard library (including tkinter), Tcl/Tk, tomlkit and the PyInstaller bootloader. Their licenses remain applicable.

- CPython 3.14: Python Software Foundation License Version 2; https://docs.python.org/3/license.html
- Tcl/Tk 8.6: BSD-style Tcl/Tk license; https://www.tcl-lang.org/software/tcltk/license.html
- tomlkit 0.15.2: MIT; https://github.com/python-poetry/tomlkit/blob/main/LICENSE
- PyInstaller 6.22.3: GPL-2.0-or-later with bootloader exception permitting distribution of bundled applications under their own license; https://pyinstaller.org/en/stable/license.html
- Inno Setup is used to create the installer; https://jrsoftware.org/files/is/license.txt

Build tooling also includes altgraph, packaging, pefile, pyinstaller-hooks-contrib, pywin32-ctypes and setuptools; these are build-time dependencies. Complete bundled license texts are included in the `licenses` directory produced by the build script.
