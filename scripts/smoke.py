"""Exercise packaged CLI with a disposable Windows credential, never a real key."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.credentials import WindowsCredentials

executable = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="codex-switch-smoke-") as temporary:
    root = Path(temporary)
    home = root / "中文 home"
    home.mkdir()
    auth = home / "auth.json"
    auth.write_bytes(b"account-sentinel")
    (home / "config.toml").write_bytes(b'model = "existing-model"\nservice_tier = "priority"\n')
    environment = dict(os.environ, LOCALAPPDATA=str(root / "local"), PYTHONIOENCODING="utf-8")

    def call(*arguments, stdin=None):
        result = subprocess.run([str(executable), "--codex-home", str(home), *arguments],
                                input=stdin, text=True, encoding="utf-8", capture_output=True,
                                env=environment, timeout=30)
        if result.returncode:
            raise RuntimeError("Packaged CLI failed: " + " ".join(arguments))
        return result.stdout

    try:
        call("setup", "--key-stdin", "--use", stdin="packaged-fixture-not-real\n")
        state = json.loads(call("status", "--json"))
        assert state["mode"] == "api" and state["api_ready"]
        parsed = tomllib.loads((home / "config.toml").read_text("utf-8"))
        auth_config = parsed["model_providers"]["codex_switch_api"]["auth"]
        helper = subprocess.run([auth_config["command"], *auth_config["args"]],
                                capture_output=True, text=True, encoding="utf-8", env=environment, timeout=30)
        assert helper.returncode == 0 and helper.stdout.strip() == "packaged-fixture-not-real"
        assert parsed["model"] == "existing-model" and parsed["service_tier"] == "priority"
        call("use", "account")
        assert json.loads(call("status", "--json"))["mode"] == "account"
        call("api")
        assert json.loads(call("status", "--json"))["mode"] == "api"
        for path in home.rglob("*"):
            if path.is_file():
                assert b"packaged-fixture-not-real" not in path.read_bytes()
        assert auth.read_bytes() == b"account-sentinel"
        call("uninstall-cleanup")
        parsed = tomllib.loads((home / "config.toml").read_text("utf-8"))
        assert parsed["model_provider"] == "openai"
        assert "codex_switch_api" not in parsed.get("model_providers", {})
        assert auth.read_bytes() == b"account-sentinel"
        print("Packaged CLI smoke passed: setup, credential helper, account/API roundtrip, safe cleanup; 0 model requests.")
    finally:
        # Clean the isolated vault entry even if a broken binary cannot run cleanup.
        WindowsCredentials(home).delete()
