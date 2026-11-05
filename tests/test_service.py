from copy import deepcopy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.config import API_URL, PROVIDER, parse
from codex_switch.credentials import default_credentials, target_for
from codex_switch.errors import SwitchError
from codex_switch.service import SwitchService, helper_command


class MemoryCredentials:
    def __init__(self):
        self.value = None

    def read(self):
        return self.value

    def write(self, key):
        self.value = key

    def delete(self):
        self.value = None


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.credentials = MemoryCredentials()
        self.service = SwitchService(self.home, self.credentials, (sys.executable, ["helper.py"]), track=False)

    def write_config(self, raw):
        (self.home / "config.toml").write_bytes(raw)

    def test_first_setup_creates_provider_but_does_not_switch_or_store_key_in_files(self):
        self.service.setup("fixture-secret")
        state = self.service.status()
        self.assertEqual(state["mode"], "account")
        self.assertTrue(state["api_ready"])
        self.assertNotIn("model", parse(self.service.config.read()))
        for path in self.home.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"fixture-secret", path.read_bytes())
        provider = parse(self.service.config.read())["model_providers"][PROVIDER]
        self.assertEqual(provider["auth"]["args"][-1], "credential")
        self.assertEqual(provider["wire_api"], "responses")
        self.assertNotIn("requires_openai_auth", provider)

    @unittest.skipUnless(os.name == "nt", "Windows source interpreter path")
    def test_source_gui_uses_console_python_for_credential_stdout(self):
        with mock_patch("sys.executable", r"C:\Python\pythonw.exe"):
            self.assertEqual(Path(helper_command()[0]).name, "python.exe")

    def test_setup_and_switch_preserve_auth_comments_bom_crlf_and_unrelated_values(self):
        raw = ('# 中文说明\r\nmodel_provider = "openai" # keep\r\n'
               'model = "existing-model"\r\nservice_tier = "priority"\r\n'
               '[features]\r\nmulti_agent = true\r\n'
               '[mcp_servers.keep]\r\ncommand = "leave-this-alone"\r\n').encode("utf-8-sig")
        self.write_config(raw)
        auth = self.home / "auth.json"
        auth.write_bytes(b"original-account-sentinel")
        self.service.setup("fixture-secret")
        configured = self.service.config.read()
        self.assertTrue(configured.startswith(b"\xef\xbb\xbf"))
        self.assertIn('# 中文说明\r\n'.encode(), configured)
        self.assertNotIn(b"\n", configured.replace(b"\r\n", b""))
        expected = parse(raw)
        actual = parse(configured)
        del actual["model_providers"]
        self.assertEqual(actual, expected)
        self.service.use("api")
        self.service.use("account")
        self.assertEqual(self.service.config.read(), configured)
        self.assertEqual(auth.read_bytes(), b"original-account-sentinel")
        self.assertFalse(self.service.use("account")["changed"])

    def test_credential_is_rolled_back_when_config_write_fails(self):
        self.credentials.value = "old-fixture"
        with mock_patch.object(self.service.config, "commit", side_effect=SwitchError("write failed")):
            with self.assertRaises(SwitchError):
                self.service.setup("new-fixture")
        self.assertEqual(self.credentials.read(), "old-fixture")
        self.assertFalse(self.service.config.path.exists())

    def test_new_credential_is_removed_on_config_failure(self):
        with mock_patch.object(self.service.config, "commit", side_effect=OSError()):
            with self.assertRaises(OSError):
                self.service.setup("new-fixture")
        self.assertIsNone(self.credentials.read())

    def test_existing_legacy_api_is_reusable_without_moving_or_reading_key(self):
        raw = ('model_provider = "openai_api"\n[model_providers.openai_api]\n'
               'base_url = "' + API_URL + '"\n[model_providers.openai_api.auth]\ncommand = "external-helper.exe"\n').encode()
        self.write_config(raw)
        self.assertTrue(self.service.status()["api_ready"])
        self.service.use("account")
        self.service.use("api")
        self.assertEqual(self.service.config.read(), raw)
        self.assertIsNone(self.credentials.read())

    def test_foreign_provider_collision_refuses_without_key_write(self):
        self.write_config(b'[model_providers.codex_switch_api]\nname = "Another app"\n')
        original = self.service.config.read()
        with self.assertRaises(SwitchError):
            self.service.setup("new-fixture")
        self.assertEqual(self.service.config.read(), original)
        self.assertIsNone(self.credentials.read())

    def test_foreign_current_provider_is_not_overwritten(self):
        raw = b'model_provider = "different"\n'
        self.write_config(raw)
        with self.assertRaises(SwitchError):
            self.service.use("account")
        self.assertEqual(self.service.config.read(), raw)

    def test_selected_profile_override_blocks_misleading_global_switch(self):
        raw = b'profile = "work"\n[profiles.work]\nmodel_provider = "proxy"\n'
        self.write_config(raw)
        with self.assertRaises(SwitchError):
            self.service.use("account")
        self.assertEqual(self.service.config.read(), raw)

    def test_concurrent_external_change_is_not_overwritten(self):
        self.write_config(b'model = "before"\n')
        original = self.service.config.read()
        self.write_config(b'model = "external-edit"\n')
        with self.assertRaises(SwitchError):
            self.service.config.commit(original, b'model = "attempted-overwrite"\n')
        self.assertEqual(parse(self.service.config.read())["model"], "external-edit")

    def test_remove_api_restores_account_and_preserves_existing_providers_and_login(self):
        raw = b'model = "keep"\n[model_providers.other]\nname = "Leave me"\n'
        self.write_config(raw)
        auth = self.home / "auth.json"
        auth.write_bytes(b"account-sentinel")
        self.service.setup("fixture-secret")
        self.service.use("api")
        self.service.remove_api()
        config = parse(self.service.config.read())
        self.assertEqual(config["model_provider"], "openai")
        self.assertEqual(config["model_providers"], {"other": {"name": "Leave me"}})
        self.assertIsNone(self.credentials.read())
        self.assertEqual(auth.read_bytes(), b"account-sentinel")

    def test_uninstall_fresh_setup_with_only_managed_provider(self):
        self.service.setup("fixture-secret")
        self.service.use("api")
        self.service.remove_api()
        result = parse(self.service.config.read())
        self.assertEqual(result["model_provider"], "openai")
        self.assertEqual(result.get("model_providers", {}), {})
        self.assertIsNone(self.credentials.read())

    def test_invalid_toml_does_not_write_key(self):
        self.write_config(b'bad = [unclosed')
        with self.assertRaises(SwitchError):
            self.service.setup("fixture-secret")
        self.assertIsNone(self.credentials.read())

    def test_empty_or_control_character_keys_are_refused(self):
        for key in ("", "  ", "fixture secret", "fixture\x00secret"):
            with self.subTest(key=repr(key)):
                with self.assertRaises(SwitchError):
                    self.service.setup(key)
        self.assertFalse(self.service.config.path.exists())

    def test_status_is_readonly_and_contains_no_key(self):
        self.service.setup("fixture-secret")
        before = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertNotIn("fixture-secret", repr(self.service.status()))
        after = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_tampered_endpoint_or_helper_cannot_be_selected(self):
        self.service.setup("fixture-secret")
        original = self.service.config.read()
        for changed in (original.replace(API_URL.encode(), b"https://untrusted.example/v1"),
                        original.replace(b'credential"', b'other-command"')):
            self.write_config(changed)
            self.assertFalse(self.service.status()["api_ready"])
            with self.assertRaises(SwitchError):
                self.service.use("api")
        self.write_config(original)

    @unittest.skipUnless(os.name == "nt" or sys.platform == "darwin", "Native credential store")
    def test_native_store_roundtrip_isolated_to_test_home(self):
        store = default_credentials(self.home, sys.executable)
        self.addCleanup(store.delete)
        self.assertIsNone(store.read())
        store.write("credential-store-fixture")
        self.assertEqual(store.read(), "credential-store-fixture")
        self.assertNotEqual(target_for(self.home), target_for(self.home / "another"))
        store.delete()
        self.assertIsNone(store.read())


if __name__ == "__main__":
    unittest.main()
