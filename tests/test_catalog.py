import json
import hashlib
import os
import subprocess
from types import SimpleNamespace
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import test_service
from codex_switch.catalog import discover, endpoint
from codex_switch.config import API_URL, PROVIDER, parse
from codex_switch.errors import SwitchError
from codex_switch.settings import read_state, write_state


class GatewayTests(unittest.TestCase):
    setUp = test_service.ServiceTests.setUp
    write_config = test_service.ServiceTests.write_config

    def test_existing_legacy_api_sync_apply_and_cleanup_keep_external_credentials(self):
        raw = b'model_provider="openai_api"\nmodel="original-model"\nservice_tier="priority"\n[model_providers.openai_api]\nbase_url="https://api.openai.com/v1"\nwire_api="responses"\nenv_key="SWITCH_TEST_LEGACY_KEY"\n'
        self.write_config(raw)
        values = [{"id": "model-a", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]
        with patch.dict(os.environ, {"SWITCH_TEST_LEGACY_KEY": "legacy-test-secret"}):
            with patch("codex_switch.service.discover", return_value=values) as discovery:
                self.service.sync_models()
                discovery.assert_called_once_with(API_URL, "legacy-test-secret")
            self.assertEqual(self.service.config.read(), raw)
            self.assertIsNone(self.credentials.read())
            self.service.configure_model("model-a", True)
            self.service.apply_models("model-a")
            self.assertEqual(self.service.status()["provider"], "openai_api")
            self.assertTrue(self.service.status()["catalog_active"])
            self.service.use("account")
            self.assertEqual(self.service.status()["model"], "original-model")
            self.service.use("api")
            self.service.remove_api()
            self.assertEqual(parse(self.service.config.read()), parse(raw))
            self.assertFalse(self.service.status()["catalog_enabled"])
            self.assertIsNone(self.credentials.read())
            for file in self.home.rglob("*"):
                if file.is_file(): self.assertNotIn(b"legacy-test-secret", file.read_bytes())

    def test_legacy_helper_is_piped_without_shell_or_secret_error_output(self):
        self.write_config(b'[model_providers.openai_api]\nbase_url="https://api.openai.com/v1"\n[model_providers.openai_api.auth]\ncommand="existing-helper"\nargs=["--read"]\n')
        with patch("codex_switch.service.subprocess.run", return_value=SimpleNamespace(stdout=b"legacy-test-secret\r\n", returncode=0)) as run:
            key = self.service._discovery_credential(self.service.status())
            self.assertEqual(key, "legacy-test-secret")
            self.assertEqual(run.call_args.args[0], ["existing-helper", "--read"])
            self.assertFalse(run.call_args.kwargs.get("shell", False))
            self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
        with patch("codex_switch.service.subprocess.run", return_value=SimpleNamespace(stdout=b"legacy-test-secret", returncode=1)):
            with self.assertRaises(SwitchError) as error: self.service._discovery_credential(self.service.status())
            self.assertNotIn("legacy-test-secret", str(error.exception))

    def test_legacy_key_rotation_during_sync_rejects_stale_results(self):
        self.write_config(b'[model_providers.openai_api]\nbase_url="https://api.openai.com/v1"\nenv_key="SWITCH_TEST_LEGACY_KEY"\n')
        with patch.dict(os.environ, {"SWITCH_TEST_LEGACY_KEY": "old-fixture"}):
            def rotate(*args):
                os.environ["SWITCH_TEST_LEGACY_KEY"] = "new-fixture"
                return []
            with patch("codex_switch.service.discover", side_effect=rotate):
                with self.assertRaises(SwitchError): self.service.sync_models()
        self.assertEqual(read_state(self.home), {})
    def test_gateway_catalog_roundtrip_and_reapply_restore_account(self):
        original = b'model="account-model"\nservice_tier="priority"\nmodel_reasoning_effort="xhigh"\nmodel_catalog_json="account.json"\n[mcp_servers.keep]\ncommand="keep"\n'
        self.write_config(original)
        self.service.setup("gateway-key", "https://gateway.example/v1/")
        with self.assertRaises(SwitchError):
            self.service.use("api")
        with patch("codex_switch.service.discover", return_value=[
            {"id": "deepseek", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"},
            {"id": "gpt-alias", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]):
            self.service.sync_models()
        self.service.configure_model("deepseek", True, 65536, ["low", "high"])
        self.service.configure_model("gpt-alias", True)
        self.service.apply_models("deepseek")
        self.assertEqual(parse(self.service.config.read())["model"], "account-model")
        self.service.use("api")
        config = parse(self.service.config.read())
        self.assertEqual(config["model"], "deepseek")
        self.assertEqual(config["model_reasoning_effort"], "low")
        self.assertNotIn("service_tier", config)
        catalog = json.loads(Path(config["model_catalog_json"]).read_text("utf-8"))
        self.assertEqual([m["slug"] for m in catalog["models"]], ["deepseek", "gpt-alias"])
        self.assertTrue(all(not m["service_tiers"] for m in catalog["models"]))
        self.service.apply_models("gpt-alias")
        self.assertEqual(parse(self.service.config.read())["model"], "gpt-alias")
        self.service.use("account")
        restored = parse(self.service.config.read())
        for name, value in parse(original).items():
            self.assertEqual(restored[name], value)
        self.service.use("api")
        self.assertEqual(parse(self.service.config.read())["model"], "gpt-alias")
        self.service.remove_api()
        for name, value in parse(original).items():
            self.assertEqual(parse(self.service.config.read())[name], value)
        for file in self.home.rglob("*"):
            if file.is_file():
                self.assertNotIn(b"gateway-key", file.read_bytes())

    def test_endpoint_change_requires_new_key_and_failed_setup_rolls_back_binding(self):
        self.service.setup("first")
        with self.assertRaises(SwitchError):
            self.service.setup(None, "https://gateway.example/v1")
        with patch.object(self.service.config, "commit", side_effect=OSError()):
            with self.assertRaises(OSError):
                self.service.setup("second", "https://gateway.example/v1")
        self.assertEqual(self.credentials.read(), "first")
        self.assertEqual(read_state(self.home)["base_url"], API_URL)
        self.assertTrue(self.service.status()["api_ready"])

    def test_discovery_failure_and_stale_results_preserve_prior_catalog(self):
        self.service.setup("first")
        before = read_state(self.home)
        with patch("codex_switch.service.discover", side_effect=SwitchError("failed")):
            with self.assertRaises(SwitchError): self.service.sync_models()
        self.assertEqual(read_state(self.home), before)
        def change(*args):
            self.write_config(self.service.config.read() + b'\n# external change\n')
            return []
        with patch("codex_switch.service.discover", side_effect=change):
            with self.assertRaises(SwitchError): self.service.sync_models()
        self.assertEqual(read_state(self.home), before)

    def test_removed_models_not_kept_and_key_rotation_invalidates_catalog(self):
        self.service.setup("first", "https://gateway.example/v1")
        values = [{"id": "model-a", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]
        with patch("codex_switch.service.discover", return_value=values):
            self.service.sync_models()
        self.service.configure_model("model-a", True)
        self.service.apply_models()
        self.service.use("api")
        values = [{**values[0], "id": "model-b"}]
        with patch("codex_switch.service.discover", return_value=values):
            self.service.sync_models()
        self.assertEqual([m["id"] for m in self.service.status()["models"]], ["model-b"])
        with self.assertRaises(SwitchError): self.service.apply_models()
        self.service.setup("second")
        self.assertFalse(self.service.status()["catalog_enabled"])
        self.assertEqual(self.service.status()["mode"], "account")
        self.assertNotIn("model_catalog_json", parse(self.service.config.read()))
        with self.assertRaises(SwitchError): self.service.use("api")

    def test_apply_failure_rolls_back_state_and_config(self):
        self.service.setup("first")
        values = [{"id": "model-a", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]
        with patch("codex_switch.service.discover", return_value=values): self.service.sync_models()
        self.service.configure_model("model-a", True)
        before = self.service.config.read(), read_state(self.home)
        with patch.object(self.service.config, "commit", side_effect=OSError()):
            with self.assertRaises(OSError): self.service.apply_models()
        self.assertEqual((self.service.config.read(), read_state(self.home)), before)

    def test_reset_restores_account_model_but_keeps_gateway_key(self):
        self.write_config(b'model="account-model"\nservice_tier="priority"\n')
        self.service.setup("gateway", "https://gateway.example/v1")
        values = [{"id": "model-a", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]
        with patch("codex_switch.service.discover", return_value=values): self.service.sync_models()
        self.service.configure_model("model-a", True)
        self.service.apply_models()
        self.service.use("api")
        self.service.reset_models()
        state = self.service.status()
        self.assertEqual(state["mode"], "account")
        self.assertEqual(state["model"], "account-model")
        self.assertTrue(state["api_ready"])
        self.assertEqual(self.credentials.read(), "gateway")
        self.assertFalse(state["catalog_enabled"])
        self.assertEqual(parse(self.service.config.read())["service_tier"], "priority")

    def test_custom_endpoint_tampering_blocks_discovery_without_network(self):
        self.service.setup("gateway", "https://gateway.example/v1")
        self.write_config(self.service.config.read().replace(b"https://gateway.example/v1", b"https://different.example/v1"))
        self.assertFalse(self.service.status()["api_ready"])
        with patch("codex_switch.service.discover") as get:
            with self.assertRaises(SwitchError): self.service.sync_models()
            get.assert_not_called()

    def test_interrupted_config_transaction_resolves_matching_state(self):
        self.service.setup("fixture")
        original = self.service.config.read()
        old = read_state(self.home)
        updated = original + b'\n# completed transaction\n'
        new = dict(old, api_model="new-model")
        pending = dict(new, _transaction={"previous": old, "before": hashlib.sha256(original).hexdigest(),
                                         "after": hashlib.sha256(updated).hexdigest()})
        write_state(self.home, pending)
        self.assertEqual(read_state(self.home), old)
        self.write_config(updated)
        self.assertEqual(read_state(self.home), new)
        self.write_config(updated + b'# external edit\n')
        with self.assertRaises(SwitchError): read_state(self.home)

    def test_catalog_state_survives_journal_cleanup_failure_with_unchanged_config(self):
        self.service.setup("fixture")
        values = [{"id": "model-a", "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}]
        with patch("codex_switch.service.discover", return_value=values): self.service.sync_models()
        self.service.configure_model("model-a", True)
        original = self.service.config.read()
        calls = []
        def interrupt_clear(home, state):
            calls.append(state)
            if len(calls) == 2:
                raise OSError("simulated interrupted journal cleanup")
            write_state(home, state)
        with patch("codex_switch.service.write_state", side_effect=interrupt_clear):
            self.service.apply_models()
        self.assertEqual(self.service.config.read(), original)
        self.assertTrue(self.service.status()["catalog_enabled"])
        self.service.use("api")
        self.assertEqual(self.service.status()["model"], "model-a")


class DiscoveryTests(unittest.TestCase):
    def test_get_auth_list_and_redirect_never_forward_key(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization")))
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", "/stolen/models")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"data": [{"id": "deepseek"}, {"id": "gpt"}]}).encode())
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = "http://127.0.0.1:" + str(server.server_port)
            listed = discover(base + "/v1", "test-only")
            self.assertEqual([m["id"] for m in listed], ["deepseek", "gpt"])
            self.assertFalse(any(m["enabled"] for m in listed))
            with self.assertRaises(SwitchError): discover(base + "/redirect", "test-only")
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0], ("/v1/models", "Bearer test-only"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_endpoint_refuses_credential_urls_and_plain_remote_http(self):
        for value in ("http://example.com", "https://key@example.com", "https://example.com?key=secret", "https://example.com/#fragment", "file:///tmp/models", "https://host/\npath"):
            with self.subTest(value=value), self.assertRaises(SwitchError): endpoint(value)


if __name__ == "__main__": unittest.main()
