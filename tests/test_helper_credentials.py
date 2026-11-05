import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.credentials import HelperCredentials
from codex_switch.errors import SwitchError
from codex_switch.service import SwitchService


class HelperCredentialTests(unittest.TestCase):
    def test_packaged_mac_gui_uses_the_same_keychain_owner_as_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            contents = Path(temporary) / "Codex Switch.app/Contents"
            with patch.object(sys, "platform", "darwin"), patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(contents / "MacOS/Codex Switch")):
                service = SwitchService(Path(temporary) / "home")
            self.assertIsInstance(service.credentials, HelperCredentials)
            self.assertEqual(service.helper[0], str((contents / "Helpers/codex-switch").resolve()))

    def test_key_is_piped_to_helper_and_never_enters_arguments(self):
        store = HelperCredentials(Path("fixture home"), ("helper", []))
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{"ok":true}', '')) as run:
            store.write("fixture-not-real")
        args, kwargs = run.call_args
        self.assertNotIn("fixture-not-real", args[0])
        self.assertEqual(args[0][-1], "vault-write")
        self.assertEqual(kwargs["input"], "fixture-not-real\n")

    def test_read_and_delete_use_protocol(self):
        store = HelperCredentials(Path("fixture"), ("python", ["app_cli.py"]))
        with patch("subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, json.dumps({"key": "fixture"}), ''),
            subprocess.CompletedProcess([], 0, '{"ok":true}', '')
        ]) as run:
            self.assertEqual(store.read(), "fixture")
            store.delete()
        self.assertEqual(run.call_args_list[0].args[0][:2], ["python", "app_cli.py"])
        self.assertEqual(run.call_args_list[1].args[0][-1], "vault-delete")

    def test_errors_never_include_helper_output_or_credential(self):
        store = HelperCredentials(Path("fixture"), ("helper", []))
        for result in (subprocess.CompletedProcess([], 1, "private-fixture", "private-fixture"),
                       subprocess.CompletedProcess([], 0, "private-fixture", "")):
            with patch("subprocess.run", return_value=result):
                with self.assertRaises(SwitchError) as raised:
                    store.read()
                self.assertNotIn("private-fixture", str(raised.exception))
