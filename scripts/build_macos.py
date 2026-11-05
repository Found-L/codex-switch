"""Build, verify and package a native macOS app/CLI. Run on macOS, not a cross build."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_switch import __version__


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def main():
    if sys.platform != "darwin":
        raise SystemExit("Run build_macos.py on macOS.")
    os.chdir(ROOT)
    architecture = "arm64" if platform.machine() == "arm64" else "x64"
    target = "arm64" if architecture == "arm64" else "x86_64"
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "-")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    run(sys.executable, "scripts/make_icon.py")
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--target-arch", target, "--paths", "src"]
    run(*common, "--onefile", "--console", "--name", "codex-switch", "--exclude-module", "PySide6",
        "--exclude-module", "tkinter", "--codesign-identity", identity, "app_cli.py")
    # Write a reproducible spec so menu-bar behavior and bundle metadata are explicit.
    spec = ROOT / "build" / "macos-app.spec"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(f'''a = Analysis([{str(ROOT / "app_gui.py")!r}], pathex=[{str(ROOT / "src")!r}],
    binaries=[], datas=[({str(ROOT / "assets")!r}, 'assets'), ({str(ROOT / "ui")!r}, 'ui')],
    hiddenimports=[], hookspath=[], hooksconfig={{}}, runtime_hooks=[], excludes=['tkinter'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Codex Switch', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    target_arch={target!r}, codesign_identity={identity!r}, entitlements_file={str(ROOT / "installer/macos-entitlements.plist")!r})
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Codex Switch')
app = BUNDLE(coll, name='Codex Switch.app', icon={str(ROOT / "assets/codex-switch.icns")!r},
    bundle_identifier='com.foundl.codex-switch', version={__version__!r},
    info_plist={{'LSUIElement': True, 'LSMinimumSystemVersion': '14.0',
        'CFBundleShortVersionString': {__version__!r}, 'NSHighResolutionCapable': True}})
''', encoding="utf-8")
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", spec)
    app = ROOT / "dist/Codex Switch.app"
    contents = app / "Contents"
    helper = contents / "Helpers/codex-switch"
    helper.parent.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "dist/codex-switch", helper)
    for name in ("README.md", "README.en.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, contents / "Resources" / name)
    run(sys.executable, "scripts/collect_licenses.py", contents / "Resources/licenses")
    # Sign after adding the helper and notices so the final bundle is sealed.
    signing = ["/usr/bin/codesign", "--force", "--sign", identity]
    if identity != "-":
        signing += ["--options", "runtime", "--timestamp"]
    run(*signing, helper)
    run(*signing, "--entitlements", ROOT / "installer/macos-entitlements.plist", app)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
    run(sys.executable, "scripts/gui_smoke.py", contents / "MacOS/Codex Switch")
    run(sys.executable, "scripts/smoke.py", helper)
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    dmg = release / f"CodexSwitch-{__version__}-macos-{architecture}.dmg"
    with tempfile.TemporaryDirectory(prefix="codex-switch-dmg-") as temporary:
        stage = Path(temporary) / "volume"
        stage.mkdir()
        run("/usr/bin/ditto", app, stage / app.name)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        (stage / "READ ME.txt").write_text(
            "Drag Codex Switch.app to Applications, then open that copy.\n"
            "Configure your own API key in the app. Terminal tab > Install terminal command.\n"
            "macOS 14+. See the repository README for unsigned-build opening instructions.\n"
            "https://github.com/Found-L/codex-switch\n", encoding="utf-8")
        run("/usr/bin/hdiutil", "create", "-volname", "Codex Switch", "-srcfolder", stage, "-ov", "-format", "UDZO", dmg)
    notary = [os.environ.get(name) for name in ("MACOS_NOTARY_KEY", "MACOS_NOTARY_KEY_ID", "MACOS_NOTARY_ISSUER")]
    if any(notary):
        if not all(notary) or identity == "-":
            raise SystemExit("Notarization requires a Developer ID identity and all three notary settings.")
        with tempfile.TemporaryDirectory(prefix="codex-switch-notary-") as temporary:
            key = Path(temporary) / "AuthKey.p8"
            key.write_text(notary[0], encoding="utf-8")
            key.chmod(0o600)
            run("/usr/bin/xcrun", "notarytool", "submit", dmg, "--key", key,
                "--key-id", notary[1], "--issuer", notary[2], "--wait")
            run("/usr/bin/xcrun", "stapler", "staple", dmg)
            run("/usr/bin/xcrun", "stapler", "validate", dmg)
    # The installer check copies the app from the actual mounted DMG before setup.
    run(sys.executable, "scripts/macos_installer_smoke.py", dmg)
    checksum = hashlib.sha256(dmg.read_bytes()).hexdigest()
    (release / f"SHA256SUMS-macos-{architecture}.txt").write_text(checksum + "  " + dmg.name + "\n", encoding="utf-8")
    print(f"Built macOS {architecture}: {dmg.name}; signing={'Developer ID' if identity != '-' else 'ad-hoc'}; notarized={all(notary)}")


if __name__ == "__main__":
    main()
