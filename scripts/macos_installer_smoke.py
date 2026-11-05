"""Mount the released DMG, copy its app, configure Keychain/CLI, then detach safely."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.credentials import default_credentials


def main():
    dmg = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="codex-switch-install-") as temporary:
        root = Path(temporary)
        mount = root / "volume"
        mount.mkdir()
        mounted = False
        home = root / "中文 user's home"
        app = home / "Applications/Codex Switch.app"
        config = home / "codex config"
        config.mkdir(parents=True)
        (config / "auth.json").write_bytes(b"macos-account-sentinel")
        helper = app / "Contents/Helpers/codex-switch"
        environment = dict(os.environ, HOME=str(home), SHELL="/bin/zsh", CODEX_HOME=str(config),
                           CODEX_SWITCH_DATA_HOME=str(home / "state"))

        def call(*args, stdin=None):
            result = subprocess.run(list(map(str, args)), input=stdin, capture_output=True,
                                    text=True, encoding="utf-8", env=environment, timeout=60)
            if result.returncode:
                raise RuntimeError("macOS installer smoke command failed: " + str(args[0]) + "; " + result.stderr[:600])
            return result.stdout

        try:
            call("/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, dmg)
            mounted = True
            blocked = subprocess.run([str(mount / "Codex Switch.app/Contents/Helpers/codex-switch"),
                                      "setup", "--key-stdin", "--use"], input="blocked-fixture\n",
                                     text=True, capture_output=True, env=environment, timeout=30)
            assert blocked.returncode != 0 and "Copy Codex Switch.app" in blocked.stderr
            assert not (config / "config.toml").exists()
            call("/usr/bin/ditto", mount / "Codex Switch.app", app)
            call("/usr/bin/hdiutil", "detach", mount)
            mounted = False
            call("/usr/bin/codesign", "--verify", "--deep", "--strict", app)
            call(helper, "setup", "--key-stdin", "--use", stdin="macos-install-fixture-not-real\n")
            state = json.loads(call(helper, "status", "--json"))
            assert state["api_ready"] and state["mode"] == "api"
            data = tomllib.loads((config / "config.toml").read_text("utf-8"))
            auth = data["model_providers"]["codex_switch_api"]["auth"]
            assert auth["command"] == str(helper)
            assert call(auth["command"], *auth["args"]).strip() == "macos-install-fixture-not-real"
            call(helper, "install-cli")
            launcher = home / ".local/bin/codex-switch"
            assert json.loads(call(launcher, "status", "--json"))["mode"] == "api"
            # Exercise PATH as Terminal/iTerm/VS Code interactive zsh will see it.
            assert str(launcher) in call("/bin/zsh", "-l", "-i", "-c", "command -v codex-switch")
            call(launcher, "use", "account")
            call(launcher, "use", "api")
            assert (config / "auth.json").read_bytes() == b"macos-account-sentinel"
            for path in config.rglob("*"):
                if path.is_file():
                    assert b"macos-install-fixture-not-real" not in path.read_bytes()
            call(launcher, "uninstall", "--yes")
            assert not launcher.exists()
            assert "# BEGIN Codex Switch PATH" not in (home / ".zshrc").read_text("utf-8")
            after = tomllib.loads((config / "config.toml").read_text("utf-8"))
            assert after["model_provider"] == "openai"
            assert "codex_switch_api" not in after.get("model_providers", {})
            assert (config / "auth.json").read_bytes() == b"macos-account-sentinel"
            assert default_credentials(config, str(helper)).read() is None
            # GUI-side Keychain writes explicitly authorize the separate bundled CLI.
            store = default_credentials(config, str(helper))
            store.write("macos-cross-process-fixture")
            assert call(helper, "credential").strip() == "macos-cross-process-fixture"
            call(helper, "setup", "--key-stdin", "--use", stdin="macos-cross-process-updated\n")
            assert call(helper, "credential").strip() == "macos-cross-process-updated"
            call(helper, "uninstall", "--yes")
            assert store.read() is None
            print("macOS DMG smoke passed: copied app, native Keychain/helper, zsh PATH, account/API, uninstall; 0 model requests.")
        finally:
            if helper.is_file():
                subprocess.run([str(helper), "remove-api", "--yes"], capture_output=True,
                               env=environment, timeout=60)
            if mounted:
                call("/usr/bin/hdiutil", "detach", mount)


if __name__ == "__main__":
    main()
