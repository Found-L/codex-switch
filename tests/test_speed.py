import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from test_service import MemoryCredentials
from codex_switch.config import PROVIDER, parse, patch as patch_config
from codex_switch.errors import SwitchError
from codex_switch.service import SwitchService
from codex_switch.settings import read_state, write_state
from codex_switch.speed import SPEED_PROVIDER, make_server, observed, select, health


class SpeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.service = SwitchService(self.home, MemoryCredentials(), (sys.executable, ["helper.py"]), track=False)
        self.service.config.path.write_bytes(b'model="gpt-6.1-sol"\n[features]\nkeep=true\n')
        self.service.setup("upstream-fixture")
        self.service.use("api")
        token = SimpleNamespace(credentials=MemoryCredentials())
        self.token_patch = patch("codex_switch.speed.token_service", return_value=token)
        self.token_patch.start(); self.addCleanup(self.token_patch.stop)

    def test_opt_in_tiers_switch_account_and_off_restore_direct_provider(self):
        before = parse(self.service.config.read())
        with patch("codex_switch.speed.ensure_running", return_value=54321):
            select(self.service, "ultrafast")
            state = self.service.status()
            self.assertEqual((state["mode"], state["api_provider"]), ("api", PROVIDER))
            self.assertTrue(state["speed_route_configured"])
            route = parse(self.service.config.read())["model_providers"][SPEED_PROVIDER]
            self.assertFalse(route["supports_websockets"])
            self.assertEqual(route["auth"]["args"][-1], "speed-credential")
            self.service.use("account")
            self.assertFalse(self.service.status()["speed_route_configured"])
            self.service.use("api")
            self.assertTrue(self.service.status()["speed_route_configured"])
            select(self.service, "fast")
            self.assertEqual(self.service.status()["speed_tier"], "fast")
            select(self.service, "off")
        self.assertEqual(parse(self.service.config.read()), before)
        for p in self.home.rglob("*"):
            if p.is_file():
                self.assertNotIn(b"upstream-fixture", p.read_bytes())

    def test_incompatible_model_gateway_and_account_never_opt_in(self):
        original = self.service.config.read()
        self.service.config.path.write_bytes(patch_config(original, lambda d: d.update(model="deepseek")))
        with self.assertRaises(SwitchError): select(self.service, "ultrafast")
        self.service.use("account")
        with self.assertRaises(SwitchError): select(self.service, "default")
        self.assertFalse(read_state(self.home).get("speed_enabled"))

    def test_key_rotation_and_reset_remove_speed_route(self):
        with patch("codex_switch.speed.ensure_running", return_value=54321):
            select(self.service, "fast")
            self.service.setup("rotated-fixture")
            self.assertFalse(self.service.status()["speed_enabled"])
            self.assertEqual(self.service.status()["provider"], PROVIDER)
            self.assertNotIn(SPEED_PROVIDER, parse(self.service.config.read())["model_providers"])
            select(self.service, "fast")
            self.service.reset_models()
            self.assertEqual(self.service.status()["provider"], PROVIDER)
            self.assertNotIn(SPEED_PROVIDER, parse(self.service.config.read())["model_providers"])

    def test_active_legacy_provider_is_retained_when_managed_provider_also_exists(self):
        def add_legacy(doc):
            doc["model_providers"]["openai_api"] = {"name": "Legacy", "base_url": "https://api.openai.com/v1",
                "wire_api": "responses", "env_key": "SWITCH_FIXTURE_KEY"}
            doc["model_provider"] = "openai_api"
        self.service.config.path.write_bytes(patch_config(self.service.config.read(), add_legacy))
        with patch.dict("os.environ", {"SWITCH_FIXTURE_KEY": "legacy-fixture"}), patch("codex_switch.speed.ensure_running", return_value=54321):
            select(self.service, "fast")
            state = self.service.status()
            self.assertEqual(state["api_provider"], "openai_api")
            self.assertEqual(self.service._discovery_credential(state), "legacy-fixture")
            select(self.service, "off")
            self.assertEqual(self.service.status()["provider"], "openai_api")

    def test_malformed_observation_is_ignored_and_off_is_noop(self):
        folder = self.home / "codex-switch"
        (folder / "speed-observed.json").write_text("[]", encoding="utf-8")
        self.assertEqual(observed(self.home), {})
        before = self.service.config.read()
        select(self.service, "off")
        self.assertEqual(self.service.config.read(), before)

    def test_json_response_and_compact_transport(self):
        connection = read_state(self.home)
        write_state(self.home, dict(connection, speed_enabled=True, speed_tier="fast"))
        requests = []
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Type": "application/json"}
        class Opener:
            def open(self, request, timeout):
                requests.append(json.loads(request.data))
                return Response(b'{"service_tier":"priority"}')
        server = make_server(self.service, "local-fixture", opener=Opener())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def send(path, body):
            return urlopen(Request(f"http://127.0.0.1:{server.server_port}/v1/" + path,
                data=json.dumps(body).encode(), headers={"Authorization": "Bearer local-fixture"}), timeout=3)
        with send("responses", {"model": "gpt-6.1-sol"}) as response: response.read()
        self.assertEqual(observed(self.home)["actual"], "priority")
        with send("responses/compact", {"model": "gpt-6.1-sol"}) as response: response.read()
        self.assertNotIn("service_tier", requests[-1])
        with self.assertRaises(HTTPError) as result: send("responses", [])
        self.assertEqual(result.exception.code, 400)
        result.exception.close()

    def test_sse_transport_overrides_desktop_null_without_exposing_upstream_key(self):
        connection = read_state(self.home)
        connection.update(speed_enabled=True, speed_tier="ultrafast")
        write_state(self.home, connection)
        requests = []
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Type": "text/event-stream", "x-codex-turn-state": "fixture-state"}
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                # Upstream reports Standard: preserve the actual response and report it honestly.
                return Response(b'data: {"type":"response.completed","response":{"service_tier":"default","output":[{"private":"fixture-answer"}]}}\n\n')
        server = make_server(self.service, "local-fixture", opener=Opener())
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/v1/responses"
        body = {"model": "gpt-6.1-sol", "input": "private-fixture-prompt", "stream": True, "service_tier": None}
        def send(token="local-fixture", origin=None):
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", "x-codex-turn-state": "continue-fixture"}
            if origin: headers["Origin"] = origin
            return urlopen(Request(url, data=json.dumps(body).encode(), headers=headers), timeout=3)
        with send() as response:
            raw = response.read()
            self.assertIn(b'"service_tier":"default"', raw)
            self.assertEqual(response.headers["x-codex-turn-state"], "fixture-state")
        self.assertEqual(json.loads(requests[0].data)["service_tier"], "ultrafast")
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer upstream-fixture")
        self.assertNotIn("local-fixture", str(requests[0].headers))
        self.assertEqual(observed(self.home)["actual"], "default")
        self.assertNotIn("private", str(observed(self.home)))
        # Dynamic changes need no Codex restart once the relay connection is loaded.
        connection["speed_tier"] = "fast"; write_state(self.home, connection)
        with send() as response: response.read()
        self.assertEqual(json.loads(requests[-1].data)["service_tier"], "fast")
        for params in ({"token": "wrong"}, {"origin": "https://untrusted.example"}):
            with self.assertRaises(HTTPError) as result: send(**params)
            self.assertEqual(result.exception.code, 401)
            result.exception.close()
        body["model"] = "deepseek"
        with self.assertRaises(HTTPError) as result: send()
        self.assertEqual(result.exception.code, 400); result.exception.close()
        self.assertEqual(len(requests), 2)
        self.assertTrue(health(server.server_port, "local-fixture"))
        self.assertFalse(health(server.server_port, "wrong"))


if __name__ == "__main__": unittest.main()
