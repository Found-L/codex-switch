"""Check the installed Codex backend's tier propagation using only loopback fixtures."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.catalog import model_info
from codex_switch.native import enrich_catalog

executable = shutil.which("codex")
if not executable:
    raise SystemExit("Codex executable required for the local request check.")
received = queue.Queue()


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.put({"model": body.get("model"), "tier": body.get("service_tier")})
            response = {"id": "resp_fixture", "object": "response", "status": "completed",
                        "model": "gpt-6.1-sol", "output": [],
                        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
            event = ("data: " + json.dumps({"type": "response.completed", "response": response}) + "\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(event)))
            self.end_headers()
            self.wfile.write(event)
        except (OSError, ValueError, TypeError, KeyError):
            self.close_connection = True


server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix="switch-native-request-") as temporary:
        home = Path(temporary)
        catalog = enrich_catalog({"models": [model_info("gpt-6.1-sol", 32768)]})
        (home / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
        (home / "config.toml").write_text(
            'model="gpt-6.1-sol"\nmodel_provider="fixture"\n'
            + 'model_catalog_json=' + json.dumps(str(home / "catalog.json")) + '\n'
            + '[model_providers.fixture]\nname="Local fixture"\n'
            + f'base_url="http://127.0.0.1:{server.server_port}/v1"\n'
            + 'wire_api="responses"\nenv_key="CODEX_SWITCH_FIXTURE_KEY"\nsupports_websockets=false\n',
            encoding="utf-8")
        env = dict(os.environ, CODEX_HOME=str(home), CODEX_SWITCH_FIXTURE_KEY="local-fixture-only")
        for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                     "http_proxy", "https_proxy", "all_proxy"):
            env.pop(name, None)
        process = subprocess.Popen([executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env, cwd=home,
                                   **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        messages = queue.Queue()
        def reader():
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    pass
        threading.Thread(target=reader, daemon=True).start()
        def request(identifier, method, params):
            process.stdin.write(json.dumps({"id": identifier, "method": method, "params": params}) + "\n")
            process.stdin.flush()
            for _ in range(100):
                value = messages.get(timeout=15)
                if value.get("id") == identifier:
                    if "error" in value:
                        raise RuntimeError("Local app-server rejected " + method + ".")
                    return value["result"]
            raise RuntimeError("Local app-server response was not received.")
        try:
            request(1, "initialize", {"clientInfo": {"name": "native_request_fixture", "version": "0.8.1"}})
            process.stdin.write('{"method":"initialized"}\n')
            process.stdin.flush()
            account = request(2, "account/read", {"refreshToken": False})
            if account.get("account") is not None or account.get("requiresOpenaiAuth") is not False:
                raise RuntimeError("Local fixture did not use the expected external-provider account state.")
            checks = []
            for index, tier in enumerate((None, "priority", "ultrafast")):
                result = request(10 + index * 2, "thread/start", {"model": "gpt-6.1-sol", "serviceTier": tier,
                                                                  "cwd": str(home), "ephemeral": True})
                request(11 + index * 2, "turn/start", {"threadId": result["thread"]["id"],
                    "input": [{"type": "text", "text": "local fixture"}]})
                observed = received.get(timeout=20)
                if observed != {"model": "gpt-6.1-sol", "tier": tier}:
                    raise RuntimeError("Local backend sent an unexpected speed tier: " + str(observed["tier"]))
                checks.append(tier or "standard")
            print(json.dumps({"local_backend_tiers": checks, "external_provider_account_verified": True,
                              "paid_requests": 0}))
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
            process.stdout.close()
finally:
    server.shutdown()
    server.server_close()
