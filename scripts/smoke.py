"""Exercise packaged CLI with a disposable Windows credential, never a real key."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.credentials import default_credentials
from codex_switch.speed import health

executable = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="codex-switch-smoke-") as temporary:
    root = Path(temporary)
    home = root / "中文 home"
    home.mkdir()
    auth = home / "auth.json"
    auth.write_bytes(b"account-sentinel")
    (home / "config.toml").write_bytes(b'model = "existing-model"\nservice_tier = "priority"\n')
    environment = dict(os.environ, LOCALAPPDATA=str(root / "local"), CODEX_SWITCH_DATA_HOME=str(root / "local"), PYTHONIOENCODING="utf-8")

    def call(*arguments, stdin=None):
        result = subprocess.run([str(executable), "--codex-home", str(home), *arguments],
                                input=stdin, text=True, encoding="utf-8", capture_output=True,
                                env=environment, timeout=30)
        if result.returncode:
            raise RuntimeError("Packaged CLI failed: " + " ".join(arguments) + "; " + result.stderr[:600])
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
        assert parsed["model"] == "existing-model" and parsed["service_tier"] == "default"
        call("use", "account")
        assert json.loads(call("status", "--json"))["mode"] == "account"
        assert tomllib.loads((home / "config.toml").read_text("utf-8"))["service_tier"] == "priority"
        call("api")
        assert json.loads(call("status", "--json"))["mode"] == "api"
        assert tomllib.loads((home / "config.toml").read_text("utf-8"))["service_tier"] == "default"
        for path in home.rglob("*"):
            if path.is_file():
                assert b"packaged-fixture-not-real" not in path.read_bytes()
        assert auth.read_bytes() == b"account-sentinel"
        # Start the packaged relay with fixture credentials, without model requests.
        call("speed", "default")
        relay_state = json.loads(call("status", "--json"))
        assert relay_state["speed_enabled"] and relay_state["speed_route_configured"]
        route = tomllib.loads((home / "config.toml").read_text("utf-8"))["model_providers"]["codex_switch_speed"]
        local_auth = route["auth"]
        local_helper = subprocess.run([local_auth["command"], *local_auth["args"]], capture_output=True,
            text=True, encoding="utf-8", env=environment, timeout=30)
        local_token = local_helper.stdout.strip()
        assert local_helper.returncode == 0 and local_token and local_token != "packaged-fixture-not-real"
        relay_runtime = json.loads((home / "codex-switch" / "speed-runtime.json").read_text("utf-8"))
        assert health(relay_runtime["port"], local_token)
        call("speed", "off")
        assert not json.loads(call("status", "--json"))["speed_enabled"]
        deadline = time.monotonic() + 35
        while health(relay_runtime["port"], local_token) and time.monotonic() < deadline:
            time.sleep(.25)
        assert not health(relay_runtime["port"], local_token)
        requests = []
        class GatewayFixture(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                assert self.headers.get("Authorization") == "Bearer packaged-gateway-fixture"
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"gateway-model-a"},{"id":"gateway-model-b"}]}')
            def log_message(self, *args): pass
        gateway = ThreadingHTTPServer(("127.0.0.1", 0), GatewayFixture)
        worker = threading.Thread(target=gateway.serve_forever, daemon=True)
        worker.start()
        try:
            call("setup", "--base-url", "http://127.0.0.1:" + str(gateway.server_port) + "/v1", "--key-stdin", stdin="packaged-gateway-fixture\n")
            call("models", "sync")
            call("models", "configure", "gateway-model-a", "--context", "65536", "--reasoning", "low,high")
            call("models", "configure", "gateway-model-b")
            call("models", "apply", "--default", "gateway-model-b", "--use")
            state = json.loads(call("status", "--json"))
            assert state["model"] == "gateway-model-b" and state["catalog_active"]
            api_config = tomllib.loads((home / "config.toml").read_text("utf-8"))
            assert "service_tier" not in api_config and "model_reasoning_effort" not in api_config
            call("account")
            account_config = tomllib.loads((home / "config.toml").read_text("utf-8"))
            assert account_config["model"] == "existing-model" and account_config["service_tier"] == "priority"
            call("api")
            call("models", "reset")
            assert not json.loads(call("status", "--json"))["catalog_enabled"]
            assert requests == ["/v1/models"]
            assert auth.read_bytes() == b"account-sentinel"
            for file in home.rglob("*"):
                if file.is_file(): assert b"packaged-gateway-fixture" not in file.read_bytes()
        finally:
            gateway.shutdown()
            gateway.server_close()
            worker.join()
        call("uninstall-cleanup")
        parsed = tomllib.loads((home / "config.toml").read_text("utf-8"))
        assert parsed["model_provider"] == "openai"
        assert "codex_switch_api" not in parsed.get("model_providers", {})
        assert auth.read_bytes() == b"account-sentinel"
        print("Packaged CLI smoke passed: credential helper, gateway model discovery/apply/reset, account restoration, safe cleanup; 0 model requests.")
    finally:
        # Clean the isolated vault entry even if a broken binary cannot run cleanup.
        if sys.platform == "darwin":
            subprocess.run([str(executable), "--codex-home", str(home), "remove-api", "--yes"],
                           capture_output=True, env=environment, timeout=30)
        else:
            default_credentials(home, str(executable)).delete()
