import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.catalog import model_info
from codex_switch.config import parse
from codex_switch.errors import SwitchError
from codex_switch.native import (CDP, CURRENT_VERSION, EXECUTION_ASSET, PREVIOUS_VERSION, PREVIOUS_EXECUTION_ASSET, SAVED_GATE, SUBMIT_GATE, adapt,
    adapt_execution, asset_key, cancel_launch, enrich_catalog, inspect_archive, intercept, launch, launch_requested, local_ws, prepare,
    request_path, required_labels, restore, runtime_path, runtime_status, wait_for_active, wait_for_document, wait_for_exit)
from codex_switch.service import SwitchService
from codex_switch.settings import read_state
from test_service import MemoryCredentials

ACCESS = 'ipV4(e,t,n){let p=h?.authMethod==="chatgpt"||h?.authMethod==="personalAccessToken"||h?.authMethod==="amazonBedrock";return p}'
REQUEST = 'PAzX(e,t,n){if("chatgpt"!==a&&"personalAccessToken"!==a&&"amazonBedrock"!==a)return null;return requirements}'


class NativeTests(unittest.TestCase):
    def test_pending_launch_waits_without_mutating_the_provider_or_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.setup("fixture-only")
            service.use("api")
            before = service.config.read()
            request_path(service).write_text(json.dumps({"nonce": "fixture", "provider": service.status()["provider"]}), encoding="utf-8")
            events = []
            with patch("codex_switch.native.desktop_running", side_effect=[True, True, False]), patch("codex_switch.native.time.sleep"):
                self.assertTrue(wait_for_exit(service, {"version": CURRENT_VERSION}, "fixture", lambda phase, **values: events.append(phase)))
            self.assertEqual(events, ["waiting_for_exit"])
            self.assertEqual(service.config.read(), before)
            self.assertFalse(service.status()["speed_enabled"])

    def test_pending_launch_cancels_on_user_cancel_account_switch_or_nonce_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.setup("fixture-only")
            service.use("api")
            provider = service.status()["provider"]
            for action in ("cancel", "account", "nonce"):
                with self.subTest(action=action):
                    service.use("api")
                    request_path(service).write_text(json.dumps({"nonce": "fixture", "provider": provider}), encoding="utf-8")
                    if action == "cancel":
                        cancel_launch(service)
                    elif action == "account":
                        service.use("account")
                    else:
                        request_path(service).write_text('{"nonce":"newer","provider":"unrelated"}', encoding="utf-8")
                    before = service.config.read()
                    events = []
                    with patch("codex_switch.native.desktop_running") as running:
                        self.assertFalse(wait_for_exit(service, {"version": CURRENT_VERSION}, "fixture", lambda phase, **values: events.append(phase)))
                        running.assert_not_called()
                    self.assertEqual(events, ["cancelled"])
                    self.assertEqual(service.config.read(), before)

    def test_pending_launch_timeout_and_dead_host_never_report_active(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.setup("fixture-only")
            service.use("api")
            request_path(service).write_text(json.dumps({"nonce": "fixture", "provider": service.status()["provider"]}), encoding="utf-8")
            with patch("codex_switch.native.desktop_running", return_value=True):
                with self.assertRaisesRegex(SwitchError, "timed out"):
                    wait_for_exit(service, {"version": CURRENT_VERSION}, "fixture", lambda *args, **values: None, timeout=0)
            runtime_path(service).write_text(json.dumps({"phase": "active", "host_pid": os.getpid()}), encoding="utf-8")
            self.assertTrue(runtime_status(service)["host_alive"])
            with patch("codex_switch.native.process_running", return_value=False):
                self.assertEqual(runtime_status(service)["phase"], "closed")
            with self.assertRaisesRegex(SwitchError, "Fully quit"):
                cancel_launch(service)

    def test_launch_keeps_api_provider_and_reuses_the_pending_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary) / ".codex", MemoryCredentials(), track=False)
            service.setup("fixture-only")
            service.use("api")
            before = service.config.read()
            def pending(current_service, process, nonce, **kwargs):
                self.assertTrue(kwargs["allow_pending"])
                record = {"phase": "waiting_for_exit", "nonce": nonce, "host_pid": os.getpid()}
                runtime_path(current_service).write_text(json.dumps(record), encoding="utf-8")
                return record
            with patch("codex_switch.native.Path.home", return_value=Path(temporary)), \
                 patch("codex_switch.native.installation", return_value={"version": CURRENT_VERSION, "archive": "fixture.asar"}), \
                 patch("codex_switch.native.subprocess.CREATE_NO_WINDOW", 0, create=True), \
                 patch("codex_switch.native.subprocess.CREATE_NEW_PROCESS_GROUP", 0, create=True), \
                 patch("codex_switch.native.inspect_archive"), patch("codex_switch.native.subprocess.Popen") as spawn, \
                 patch("codex_switch.native.wait_for_active", side_effect=pending):
                self.assertEqual(launch(service)["phase"], "waiting_for_exit")
                self.assertEqual(launch(service)["phase"], "waiting_for_exit")
                self.assertEqual(spawn.call_count, 1)
            self.assertEqual(service.config.read(), before)
            self.assertTrue(launch_requested(service, json.loads(request_path(service).read_text())["nonce"]))

    def test_native_launch_restores_a_legacy_relay_before_queuing(self):
        from types import SimpleNamespace
        from codex_switch.speed import select, SPEED_PROVIDER
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary) / ".codex", MemoryCredentials(), track=False)
            service.config.path.parent.mkdir(parents=True)
            service.config.path.write_bytes(b'model="gpt-6.1-sol"\nmodel_provider="openai_api"\n[model_providers.openai_api]\nname="OpenAI API"\nbase_url="https://api.openai.com/v1"\nwire_api="responses"\nenv_key="FIXTURE_KEY"\n')
            before = service.config.read()
            with patch("codex_switch.speed.ensure_running", return_value=54321), \
                 patch("codex_switch.speed.token_service", return_value=SimpleNamespace(credentials=MemoryCredentials())):
                select(service, "fast")
            self.assertEqual(service.status()["provider"], SPEED_PROVIDER)
            with patch("codex_switch.native.Path.home", return_value=Path(temporary)), \
                 patch("codex_switch.native.installation", return_value={"version": CURRENT_VERSION, "archive": "fixture.asar"}), \
                 patch("codex_switch.native.subprocess.CREATE_NO_WINDOW", 0, create=True), \
                 patch("codex_switch.native.subprocess.CREATE_NEW_PROCESS_GROUP", 0, create=True), \
                 patch("codex_switch.native.inspect_archive"), patch("codex_switch.native.subprocess.Popen"), \
                 patch("codex_switch.native.wait_for_active", return_value={"phase": "waiting_for_exit"}):
                launch(service)
            self.assertEqual(service.status()["provider"], "openai_api")
            self.assertEqual(parse(service.config.read()), parse(before))
            self.assertFalse(service.status()["speed_enabled"])

    def test_launch_waits_for_module_interception_and_reports_late_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            process = type("Process", (), {"poll": lambda self: None})()
            records = [json.dumps({"nonce": "older", "phase": "active"}),
                       json.dumps({"nonce": "current", "phase": "attached"}),
                       json.dumps({"nonce": "current", "phase": "active"})]
            with patch.object(Path, "read_text", side_effect=records) as read, patch("codex_switch.native.time.sleep"):
                self.assertEqual(wait_for_active(service, process, "current")["phase"], "active")
                self.assertEqual(read.call_count, 3)
            records = [json.dumps({"nonce": "current", "phase": "attached"}),
                       json.dumps({"nonce": "current", "phase": "error", "message": "fixture failure"})]
            with patch.object(Path, "read_text", side_effect=records), patch("codex_switch.native.time.sleep"):
                with self.assertRaisesRegex(SwitchError, "fixture failure"):
                    wait_for_active(service, process, "current")
            with patch.object(Path, "read_text", return_value=json.dumps({"nonce": "current", "phase": "closed"})):
                with self.assertRaisesRegex(SwitchError, "closed before"):
                    wait_for_active(service, process, "current")

    def test_launch_can_return_an_explicit_pending_state_without_claiming_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            process = type("Process", (), {"poll": lambda self: None})()
            for phase in ("waiting_for_exit", "starting"):
                with self.subTest(phase=phase), patch.object(Path, "read_text", return_value=json.dumps({"nonce": "current", "phase": phase})):
                    result = wait_for_active(service, process, "current", allow_pending=True)
                    self.assertEqual(result["phase"], phase)
                    self.assertNotEqual(result["phase"], "active")
            records = [json.dumps({"nonce": "current", "phase": "attached"}),
                       json.dumps({"nonce": "current", "phase": "active"})]
            with patch.object(Path, "read_text", side_effect=records), patch("codex_switch.native.time.sleep"):
                self.assertEqual(wait_for_active(service, process, "current", allow_pending=True)["phase"], "active")

    def test_native_catalog_preserves_original_account_speed_without_an_api_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.config.path.write_bytes(b'model="gpt-6.1-sol"\nservice_tier="ultrafast"\n')
            service.setup("fixture-only")
            service.use("api")
            self.assertEqual(parse(service.config.read())["service_tier"], "default")
            prior_state = read_state(service.home)
            with patch("codex_switch.native.bundled_metadata", return_value={"gpt-6.1-sol": model_info("gpt-6.1-sol", 32768)}):
                prepare(service)
            self.assertEqual(read_state(service.home)["account_settings"]["service_tier"], "ultrafast")
            restore(service)
            self.assertEqual(read_state(service.home), prior_state)
            service.use("account")
            self.assertEqual(parse(service.config.read())["service_tier"], "ultrafast")

    def test_scoped_gates_preserve_other_account_checks(self):
        untouched = 'else(e,t,n){return h?.authMethod==="chatgpt"||h?.authMethod==="personalAccessToken"||h?.authMethod==="amazonBedrock"}'
        changed, labels = adapt(ACCESS + ',' + REQUEST + ',' + untouched)
        self.assertEqual(labels, {"access", "request"})
        self.assertTrue(changed.endswith(untouched))
        self.assertIn('h?.requiresAuth===!1', changed)
        self.assertIn('&&"apikey"!==a&&null!==a', changed)
        with self.assertRaises(SwitchError): adapt(changed)
        with self.assertRaises(SwitchError): adapt(ACCESS.replace(';return p', ';' + ACCESS.split('{', 1)[1].split(';')[0] + ';return p'))

    def test_new_execution_checks_are_scoped_and_reject_ambiguous_sources(self):
        unrelated = 'return t?.type==="chatgpt"||t?.type==="amazonBedrock"?d.serviceTier:null'
        source = SAVED_GATE + '},' + SUBMIT_GATE + '},' + unrelated
        changed, labels = adapt_execution(source)
        self.assertEqual(labels, {"saved", "submit"})
        self.assertIn('n.account?.type==="apiKey"||(null==n.account&&!1===n.requiresOpenaiAuth)', changed)
        self.assertIn('t?.type==="apiKey"||(null==t&&!1===__codexSwitchRequiresAuth)', changed)
        self.assertTrue(changed.endswith(unrelated))
        for bad in (source.replace(SAVED_GATE, ''), source + SAVED_GATE, changed):
            with self.assertRaises(SwitchError):
                adapt_execution(bad)

    def test_new_build_requires_all_pinned_assets_and_rejects_changes(self):
        # Minimal ASAR fixture using the same header and offset layout as the client.
        execution = (SAVED_GATE + '},' + SUBMIT_GATE).encode()
        def write_archive(path, files):
            tree, content = {'files': {}}, bytearray()
            for name, data in files.items():
                node = tree
                parts = name.split('/')
                for part in parts[:-1]:
                    node = node['files'].setdefault(part, {'files': {}})
                node['files'][parts[-1]] = {'offset': str(len(content)), 'size': len(data)}
                content.extend(data)
            header = json.dumps(tree).encode()
            path.write_bytes(struct.pack('<4I', 4, len(header) + 8, 0, len(header)) + header + content)
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'app.asar'
            for version, execution_name, hashes_name in (
                    (CURRENT_VERSION, EXECUTION_ASSET, 'CURRENT_ASSET_HASHES'),
                    (PREVIOUS_VERSION, PREVIOUS_EXECUTION_ASSET, 'PREVIOUS_ASSET_HASHES')):
                with self.subTest(version=version):
                    scripts = {'webview/assets/access.js': ACCESS.encode(),
                               'webview/assets/request.js': REQUEST.encode(), execution_name: execution}
                    hashes = {name.removeprefix('webview'): hashlib.sha256(data).hexdigest() for name, data in scripts.items()}
                    with patch('codex_switch.native.' + hashes_name, hashes):
                        write_archive(archive, scripts)
                        assets = inspect_archive(archive, version)
                        self.assertEqual(set().union(*(item['labels'] for item in assets.values())), required_labels(version))
                        write_archive(archive, {**scripts, execution_name: execution + b' '})
                        with self.assertRaises(SwitchError):
                            inspect_archive(archive, version)
                        write_archive(archive, {k: v for k, v in scripts.items() if k != execution_name})
                        with self.assertRaises(SwitchError):
                            inspect_archive(archive, version)
                        write_archive(archive, {**scripts, 'webview/assets/extra.js': ACCESS.encode()})
                        with self.assertRaises(SwitchError):
                            inspect_archive(archive, version)
            with self.assertRaises(SwitchError):
                inspect_archive(archive, 'unknown')

    def test_model_matrix_does_not_invent_tiers_for_unknown_models_or_select_premium_default(self):
        source = {"models": [model_info(m, 32768) for m in ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna", "deepseek", "custom-alias")]}
        result = enrich_catalog(source)
        tiers = {m["slug"]: [t["id"] for t in m["service_tiers"]] for m in result["models"]}
        self.assertEqual(tiers["gpt-6.1-sol"], ["priority", "ultrafast"])
        self.assertEqual(tiers["gpt-6-astra"], ["priority", "ultrafast"])
        self.assertEqual(tiers["gpt-6-luna"], ["priority"])
        self.assertEqual(tiers["deepseek"], [])
        self.assertEqual(tiers["custom-alias"], [])
        self.assertTrue(all(m["default_service_tier"] is None for m in result["models"]))
        self.assertTrue(all(not m["service_tiers"] for m in source["models"]))
        self.assertEqual(enrich_catalog(result), result)

    def test_catalog_is_reversible_and_account_switch_restores_original_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.config.path.write_bytes(b'model="gpt-6.1-sol"\n')
            service.setup("native-fixture-only")
            service.use("api")
            original = parse(service.config.read())
            original_connection = read_state(service.home)
            metadata = {"gpt-6.1-sol": model_info("gpt-6.1-sol", 32768)}
            with patch("codex_switch.native.bundled_metadata", return_value=metadata):
                prepare(service)
            self.assertTrue(service.status()["native_speed_configured"])
            self.assertNotIn("service_tier", parse(service.config.read()))
            service.use("account")
            self.assertNotIn("model_catalog_json", parse(service.config.read()))
            service.use("api")
            self.assertTrue(service.status()["native_speed_configured"])
            restore(service)
            self.assertEqual(parse(service.config.read()), original)
            self.assertEqual(read_state(service.home), original_connection)

    def test_account_can_disable_native_and_relay_is_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.config.path.write_bytes(b'model="gpt-6.1-sol"\n')
            service.setup("native-fixture-only")
            service.use("api")
            with patch("codex_switch.native.bundled_metadata", return_value={"gpt-6.1-sol": model_info("gpt-6.1-sol", 32768)}):
                prepare(service)
                before = service.config.read()
                prepare(service)
                self.assertEqual(service.config.read(), before)
            from codex_switch.speed import select
            with patch("codex_switch.speed.ensure_running") as spawn:
                with self.assertRaises(SwitchError): select(service, "fast")
                spawn.assert_not_called()
            service.use("account")
            account_config = service.config.read()
            restore(service)
            self.assertEqual(service.config.read(), account_config)
            self.assertFalse(service.status()["native_speed_saved"])
            service.use("api")
            self.assertNotIn("model_catalog_json", parse(service.config.read()))

    def test_restore_rejects_external_catalog_and_runtime_is_historical(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SwitchService(Path(temporary), MemoryCredentials(), track=False)
            service.config.path.write_bytes(b'model="gpt-6.1-sol"\n')
            service.setup("native-fixture-only")
            service.use("api")
            with patch("codex_switch.native.bundled_metadata", return_value={"gpt-6.1-sol": model_info("gpt-6.1-sol", 32768)}): prepare(service)
            service.config.path.write_bytes(service.config.read() + b'\n# external edit\n')
            from codex_switch.config import patch as config_patch
            service.config.path.write_bytes(config_patch(service.config.read(), lambda d: d.update(model_catalog_json="external.json")))
            before = service.config.read()
            with self.assertRaises(SwitchError): restore(service)
            self.assertEqual(service.config.read(), before)
            self.assertTrue(service.status()["native_speed_saved"])
            from codex_switch.native import runtime_path
            runtime_path(service).write_text('{"phase":"active"}', encoding="utf-8")
            self.assertTrue(runtime_status(service)["historical_record"])
            self.assertFalse(runtime_status(service)["native_menu_verified"])

    def test_request_interception_binds_origin_path_and_hash(self):
        raw = b'fixture javascript'
        assets = {"/assets/test.js": {"sha256": hashlib.sha256(raw).hexdigest(), "body": b'changed fixture', "labels": {"access"}}}
        class Client:
            def __init__(self): self.calls = []
            def call(self, method, params):
                self.calls.append((method, params))
                return {"body": base64.b64encode(raw).decode(), "base64Encoded": True}
        client = Client()
        event = {"params": {"requestId": "fixture-id", "request": {"url": "app://-/assets/test.js"},
            "responseHeaders": [{"name": "Content-Length", "value": "18"}, {"name": "Content-Type", "value": "text/javascript"}], "responseStatusCode": 200}}
        self.assertEqual(intercept(client, event, assets), {"access"})
        payload = client.calls[-1][1]
        self.assertEqual(base64.b64decode(payload["body"]), b'changed fixture')
        self.assertEqual([h["name"] for h in payload["responseHeaders"]], ["Content-Type"])
        assets["/assets/test.js"]["sha256"] = "wrong"
        with self.assertRaises(SwitchError): intercept(client, event, assets)
        self.assertEqual(client.calls[-1][0], "Fetch.continueRequest")
        for url in ("https://example.invalid/assets/test.js", "app://evil/assets/test.js"):
            event["params"]["request"]["url"] = url
            self.assertEqual(intercept(client, event, assets), set())

    def test_debug_endpoint_and_asset_urls_are_restricted(self):
        self.assertEqual(local_ws("ws://127.0.0.1:12345/devtools/page/a", 12345), "ws://127.0.0.1:12345/devtools/page/a")
        for url in ("ws://example.invalid:12345/devtools/page/a", "ws://127.0.0.1:12346/devtools/page/a", "ws://127.0.0.1:12345/unrelated", "ws://user@127.0.0.1:12345/devtools/page/a"):
            with self.assertRaises(SwitchError): local_ws(url, 12345)
        self.assertEqual(asset_key("app://-/webview/assets/x.js"), "/assets/x.js")
        self.assertIsNone(asset_key("app://-/assets/x.js?unexpected=1"))

    def test_cdp_reader_ignores_unrelated_network_notifications(self):
        events = iter([json.dumps({"method": "Network.requestWillBeSent"})] * 1000
                      + [json.dumps({"method": "Fetch.requestPaused", "params": {"requestId": "fixture"}})])
        class Socket:
            def recv(self):
                return next(events)
        client = CDP.__new__(CDP)
        client.ws, client.closed = Socket(), False
        client.timeout_error = TimeoutError
        client.events = queue.Queue(maxsize=2)
        client._reader()
        self.assertEqual(client.events.qsize(), 1)
        self.assertEqual(client.events.get_nowait()['params']['requestId'], 'fixture')

    def test_waits_for_initial_document_before_intercepting(self):
        class Client:
            closed = False
            def __init__(self): self.calls = 0
            def call(self, method, params):
                self.calls += 1
                if self.calls == 1:
                    raise SwitchError("navigation changed context")
                return {"result": {"value": self.calls >= 3}}
        client = Client()
        with patch('codex_switch.native.time.sleep'):
            wait_for_document(client)
        self.assertEqual(client.calls, 3)
        client.closed = True
        with self.assertRaises(SwitchError):
            wait_for_document(client)


if __name__ == "__main__": unittest.main()
