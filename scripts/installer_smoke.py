"""Install/uninstall in a disposable home and assert PATH and account preservation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import winreg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.credentials import WindowsCredentials

installer = Path(sys.argv[1]).resolve()
uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{4805AB72-7459-4E65-96D9-CB907342A82F}_is1"
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key):
        raise SystemExit("Existing Codex Switch installation detected; refusing destructive smoke test.")
except FileNotFoundError:
    pass


def user_path():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            return winreg.QueryValueEx(key, "Path")[0]
        except FileNotFoundError:
            return ""


before_path = user_path()
with tempfile.TemporaryDirectory(prefix="codex-switch-install-") as temporary:
    root = Path(temporary)
    home = root / "中文 home"
    installed = root / "installed app"
    home.mkdir()
    auth = home / "auth.json"
    auth.write_bytes(b"installer-account-sentinel")
    environment = dict(os.environ, CODEX_HOME=str(home), LOCALAPPDATA=str(root / "local"))

    def command(arguments, stdin=None):
        result = subprocess.run([str(v) for v in arguments], input=stdin, text=True,
                                capture_output=True, encoding="utf-8", env=environment, timeout=60)
        if result.returncode:
            raise RuntimeError("Installer smoke command failed with exit " + str(result.returncode))
        return result.stdout

    try:
        command([installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=" + str(installed), "/TASKS=addtopath"])
        cli = installed / "codex-switch.exe"
        assert cli.is_file() and (installed / "CodexSwitch.exe").is_file()
        assert user_path() == (before_path + ";" if before_path else "") + str(installed)
        command([cli, "setup", "--key-stdin", "--use"], "installer-fixture-not-real\n")
        assert json.loads(command([cli, "status", "--json"]))["api_ready"]
        assert WindowsCredentials(home).read() == "installer-fixture-not-real"
        command([installed / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        deadline = time.monotonic() + 10
        # Inno's original EXE can disappear before its relocated child finishes
        # the post-uninstall PATH callback. Wait for the actual final state.
        while time.monotonic() < deadline:
            if not cli.exists() and not (installed / "unins000.exe").exists() and user_path() == before_path:
                break
            time.sleep(0.1)
        config = tomllib.loads((home / "config.toml").read_text("utf-8"))
        assert config["model_provider"] == "openai"
        assert "codex_switch_api" not in config.get("model_providers", {})
        assert WindowsCredentials(home).read() is None
        assert auth.read_bytes() == b"installer-account-sentinel"
        assert user_path() == before_path
        assert not cli.exists()
        print("Installer smoke passed: per-user installation, PATH, setup, active-provider cleanup, credentials removed, login preserved.")
    finally:
        if (installed / "unins000.exe").exists():
            command([installed / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
            time.sleep(1)
        WindowsCredentials(home).delete()
