"""Opt-in loopback HTTP relay; upstream secrets never enter local request headers.

No inference is initiated here. Only caller-submitted Responses requests are sent.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from .catalog import NoRedirect
from .config import API_URL, lock, parse, patch
from .errors import SwitchError
from .settings import atomic_json, read_state

SPEED_PROVIDER = "codex_switch_speed"
SPEED_NAME = "Speed relay (Codex Switch)"
TIERS = ("default", "fast", "ultrafast")
ULTRA_MODELS = ("gpt-6.1-sol", "gpt-6-astra")
FAST_MODELS = (*ULTRA_MODELS, "gpt-6.1-terra", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol")
MAX_BODY = 32 * 1024 * 1024


def token_service(service):
    from .service import SwitchService
    return SwitchService(service.home / "codex-switch" / "speed-token", helper=service.helper, track=False)


def runtime_file(home):
    return home / "codex-switch" / "speed-runtime.json"


def runtime(home):
    try:
        data = json.loads(runtime_file(home).read_text("utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("port"), int) and 1024 <= data["port"] <= 65535 else {}
    except (OSError, ValueError, TypeError):
        return {}


def observed(home):
    try:
        path = home / "codex-switch" / "speed-observed.json"
        if path.stat().st_size > 4096:
            return {}
        value = json.loads(path.read_text("utf-8"))
        if (not isinstance(value, dict) or value.get("actual") not in (*TIERS, "priority", "flex")
                or not isinstance(value.get("model"), str) or len(value["model"]) > 200
                or not isinstance(value.get("at"), (int, float))):
            return {}
        return {k: value[k] for k in ("requested", "actual", "model", "at")}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def health(port, token):
    """Authenticate the daemon without sending a bearer token to an occupied port."""
    challenge = secrets.token_hex(16)
    try:
        with build_opener(ProxyHandler({}), NoRedirect).open(f"http://127.0.0.1:{port}/health?challenge={challenge}", timeout=.6) as r:
            body = json.loads(r.read(1024))
        expected = hmac.new(token.encode(), challenge.encode(), hashlib.sha256).hexdigest()
        return isinstance(body, dict) and hmac.compare_digest(str(body.get("proof", "")), expected)
    except (OSError, ValueError):
        return False


def ensure_running(service, token):
    with lock(service.home / "codex-switch" / "speed-daemon"):
        port = runtime(service.home).get("port", 0)
        if port and health(port, token):
            return port
        command, prefix = service.helper
        process = subprocess.Popen([command, *prefix, "--codex-home", str(service.home), "speed-relay", "--port", str(port)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"),
                                   **({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
                                      if os.name == "nt" else {"start_new_session": True}))
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            live_port = runtime(service.home).get("port")
            if live_port and health(live_port, token):
                return live_port
            if process.poll() is not None:
                break
            time.sleep(.1)
        # This is our newly spawned helper only.
        if process.poll() is None:
            process.terminate()
        raise SwitchError("Local speed relay did not start. No speed configuration was applied.")


def select(service, tier):
    """Opt in through a distinct provider; retain the original direct provider."""
    if tier not in (*TIERS, "off"):
        raise SwitchError("Choose default, fast, ultrafast or off.")
    state = service.status()
    if tier == "off" and not state["speed_enabled"]:
        return state
    if tier != "off":
        if read_state(service.home).get("native_speed"):
            raise SwitchError("Disable native speed mode before enabling the fallback relay.")
        if state["mode"] != "api" or not state["api_ready"] or state["base_url"] != API_URL or state["profile_override"]:
            raise SwitchError("Speed relay currently requires a ready direct OpenAI API connection, without profile overrides.")
        if tier == "ultrafast" and state["model"] not in ULTRA_MODELS or tier == "fast" and state["model"] not in FAST_MODELS:
            raise SwitchError("This model has no confirmed support for the selected API speed tier.")
        token_store = token_service(service).credentials
        token = token_store.read()
        if not token:
            token = secrets.token_urlsafe(48)
            token_store.write(token)
        port = ensure_running(service, token)
    with lock(service.home):
        original = service.config.read()
        current = service.status()
        if any(current[k] != state[k] for k in ("mode", "model", "api_provider", "base_url", "api_ready", "profile_override")):
            raise SwitchError("Connection changed during synchronization. Retry.")
        doc = parse(original)
        connection = read_state(service.home)
        if tier != "off" and connection.get("native_speed"):
            raise SwitchError("Disable native speed mode before enabling the fallback relay.")
        existing = doc.get("model_providers", {}).get(SPEED_PROVIDER)
        if existing and existing.get("name") != SPEED_NAME:
            raise SwitchError("Speed provider ID is already used by another configuration.")
        if tier == "off":
            if doc.get("model_provider") == SPEED_PROVIDER:
                doc["model_provider"] = state["api_provider"]
            if connection.get("active_provider") == SPEED_PROVIDER:
                connection["active_provider"] = state["api_provider"]
            connection.pop("speed_tier", None)
            connection.pop("speed_enabled", None)
            connection.pop("speed_upstream_provider", None)
            doc.get("model_providers", {}).pop(SPEED_PROVIDER, None)
        else:
            command, prefix = service.helper
            doc.setdefault("model_providers", {})[SPEED_PROVIDER] = {
                "name": SPEED_NAME, "base_url": f"http://127.0.0.1:{port}/v1", "wire_api": "responses",
                "supports_websockets": False,
                "auth": {"command": command, "args": [*prefix, "--codex-home", str(service.home), "speed-credential"]}}
            doc["model_provider"] = SPEED_PROVIDER
            connection.update(speed_enabled=True, speed_tier=tier, speed_upstream_provider=state["api_provider"])
            if "active_provider" in connection:
                connection["active_provider"] = SPEED_PROVIDER
        def change(value):
            value["model_provider"] = doc.get("model_provider", "openai")
            if tier == "off":
                value.get("model_providers", {}).pop(SPEED_PROVIDER, None)
            else:
                value.setdefault("model_providers", {})[SPEED_PROVIDER] = doc["model_providers"][SPEED_PROVIDER]
        updated = patch(original, change)
        if parse(updated) != doc:
            raise SwitchError("Unrelated configuration changed; speed was not saved.")
        backup = service._commit(original, updated, connection)
        if not state["speed_enabled"] or tier == "off":
            (service.home / "codex-switch" / "speed-observed.json").unlink(missing_ok=True)
    return {"backup": backup, **service.status()}


def credential(service):
    if not read_state(service.home).get("speed_enabled"):
        raise SwitchError("Speed relay is disabled. Start a new direct API chat.")
    token = token_service(service).credentials.read()
    if not token:
        raise SwitchError("Speed relay credential is missing. Select a speed again.")
    ensure_running(service, token)
    return token


def make_server(service, token, port=0, opener=None, upstream=API_URL):
    """HTTP SSE passthrough, without buffering full responses or logging bodies."""
    opener = opener or build_opener(NoRedirect)
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *args):
            pass
        def error(self, code, message):
            data = json.dumps({"error": {"message": message, "type": "speed_relay_error"}}).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data))); self.send_header("Connection", "close")
            self.end_headers(); self.wfile.write(data); self.close_connection = True
        def do_GET(self):
            if self.path.startswith("/health?challenge=") and len(self.path) < 160 and not self.headers.get("Origin"):
                challenge = self.path.split("=", 1)[1]
                data = json.dumps({"proof": hmac.new(token.encode(), challenge.encode(), hashlib.sha256).hexdigest()}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            else:
                self.error(404, "Only Responses POST requests are supported.")
        def do_POST(self):
            self.connection.settimeout(120)
            if (self.headers.get("Origin") or self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"
                    or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)):
                return self.error(401, "Local relay authentication failed.")
            if self.path not in ("/v1/responses", "/v1/responses/compact"):
                return self.error(404, "Only Responses endpoints are supported.")
            try:
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Encoding"):
                    return self.error(400, "Compressed or chunked request bodies are not supported.")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    return self.error(413, "Request exceeds the local relay limit.")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    return self.error(400, "Incomplete request body.")
                body = json.loads(raw)
                if not isinstance(body, dict):
                    return self.error(400, "Request body must be a JSON object.")
                connection = read_state(service.home)
                tier = connection.get("speed_tier")
                if not connection.get("speed_enabled") or tier not in TIERS:
                    return self.error(409, "Speed relay is disabled; restart with the direct API connection.")
                state = service.status()
                if state["base_url"] != API_URL:
                    return self.error(409, "API endpoint changed; reconfigure the relay.")
                model = body.get("model")
                if not isinstance(model, str) or len(model) > 200 or any(ord(c) < 32 for c in model):
                    return self.error(400, "Invalid request model.")
                if ((tier == "ultrafast" and model not in ULTRA_MODELS)
                        or (tier == "fast" and model not in FAST_MODELS)):
                    return self.error(400, "Selected speed is not confirmed for this request model. Choose Standard or a supported model.")
                if self.path == "/v1/responses":
                    body["service_tier"] = tier
                # Compact requests have no service_tier field in their API schema.
                # Capture key and endpoint under the same lock used by setup/key rotation.
                # Never send a newly entered gateway key to a previous OpenAI endpoint.
                with lock(service.home):
                    live = service.status()
                    if live["base_url"] != API_URL or not live["api_ready"] or not read_state(service.home).get("speed_enabled"):
                        return self.error(409, "Connection changed; reconfigure the relay.")
                    key = service._discovery_credential(live)
                request = Request(upstream + self.path[3:], data=json.dumps(body).encode(),
                                  headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                           "Accept": self.headers.get("Accept", "text/event-stream"),
                                           "User-Agent": "CodexSwitch-SpeedRelay"}, method="POST")
                for name, value in self.headers.items():
                    if name.lower().startswith(("x-codex-", "openai-")) or name.lower() in ("originator", "session_id", "conversation_id", "idempotency-key"):
                        request.add_header(name, value)
                try:
                    response = opener.open(request, timeout=120)
                except HTTPError as error:
                    error.close()
                    return self.error(error.code if error.code < 300 or error.code >= 400 else 502,
                                      "Upstream rejected the request. No automatic downgrade or retry was attempted.")
                with response:
                    content_type = response.headers.get("Content-Type", "application/json")
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    for name in ("x-codex-turn-state", "x-request-id", "retry-after"):
                        if response.headers.get(name):
                            self.send_header(name, response.headers[name])
                    self.send_header("Connection", "close"); self.end_headers(); self.close_connection = True
                    # Bounded event parser records only tier/model, never prompt or output.
                    pending = b""
                    json_body = bytearray()
                    is_sse = "text/event-stream" in content_type.lower()
                    def record(info):
                        actual = info.get("service_tier") if isinstance(info, dict) else None
                        if actual in (*TIERS, "priority", "flex"):
                            atomic_json(service.home / "codex-switch" / "speed-observed.json",
                                        {"requested": tier, "actual": actual, "model": model, "at": time.time()})
                    while True:
                        chunk = response.read1(16384) if hasattr(response, "read1") else response.read(16384)
                        if not chunk:
                            break
                        self.wfile.write(chunk); self.wfile.flush()
                        if not is_sse:
                            if len(json_body) <= 1024 * 1024:
                                json_body.extend(chunk)
                            continue
                        pending += chunk
                        if len(pending) > 1024 * 1024:
                            pending = b""
                        lines = pending.split(b"\n")
                        pending = lines.pop()
                        for line in lines:
                            if line.startswith(b"data: "):
                                try:
                                    event = json.loads(line[6:])
                                    record(event.get("response", {}) if isinstance(event, dict) else {})
                                except (ValueError, TypeError, OSError):
                                    pass
                    if not is_sse and len(json_body) <= 1024 * 1024:
                        try:
                            record(json.loads(json_body))
                        except (ValueError, TypeError, OSError):
                            pass
            except (ValueError, TypeError, OSError, SwitchError):
                if not self.close_connection:
                    self.error(502, "Relay request failed. No automatic downgrade or retry was attempted.")
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        request_queue_size = 16
        slots = threading.BoundedSemaphore(8)
        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                request.close()
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self.slots.release()
                raise
        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()
        def handle_error(self, request, client_address):
            pass  # Never log request data or credentials.
        def get_request(self):
            request, address = super().get_request()
            request.settimeout(120)
            return request, address
    return Server(("127.0.0.1", port), Handler)


def serve(service, port):
    token = token_service(service).credentials.read()
    if not token:
        raise SwitchError("Speed relay credential is missing.")
    server = make_server(service, token, port)
    atomic_json(runtime_file(service.home), {"port": server.server_port, "pid": os.getpid()})
    def stop_when_disabled():
        # Allow the initial configuration transaction to finish before inspecting it.
        time.sleep(30)
        try:
            while read_state(service.home).get("speed_enabled"):
                time.sleep(30)
        except SwitchError:
            pass
        server.shutdown()
    threading.Thread(target=stop_when_disabled, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
