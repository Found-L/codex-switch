import io
import json
from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.runtime import inspect_runtime


class ProxyFixture:
    def __init__(self, replies):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(b"\n".join(json.dumps(r).encode() for r in replies) + b"\n")
        self.sent = None
        self.stopped = False
    def poll(self): return None
    def terminate(self):
        self.sent = self.stdin.getvalue()
        self.stopped = True
    def wait(self, timeout): return 0


class RuntimeTests(unittest.TestCase):
    def test_readonly_attach_exposes_no_foreground_billing_or_private_content(self):
        proxy = ProxyFixture([{"id": 1, "result": {}}, {"id": 2, "result": {"data": [{"model": "gpt-live", "secret": "private"}], "nextCursor": None}}, {"id": 3, "result": {"data": ["thread-a", "thread-b"]}}])
        with patch("codex_switch.runtime.shutil.which", return_value="codex-test"), patch("codex_switch.runtime.subprocess.Popen", return_value=proxy) as spawn:
            state = inspect_runtime(Path("fixture-home"))
        self.assertEqual(spawn.call_args.args[0], ["codex-test", "app-server", "proxy"])
        self.assertEqual(spawn.call_args.kwargs["env"]["CODEX_HOME"], "fixture-home")
        self.assertEqual(state["models"], ["gpt-live"])
        self.assertEqual(state["loaded_thread_count"], 2)
        self.assertTrue(state["models_complete"])
        self.assertIsNone(state["foreground_model"])
        self.assertFalse(state["billing_route_verified"])
        self.assertNotIn("thread-a", repr(state))
        self.assertNotIn("private", repr(state))
        methods = [json.loads(line)["method"] for line in proxy.sent.splitlines()]
        self.assertEqual(methods, ["initialize", "initialized", "model/list", "thread/loaded/list"])
        self.assertTrue(proxy.stopped)

    def test_unavailable_control_never_starts_a_replacement(self):
        proxy = ProxyFixture([])
        with patch("codex_switch.runtime.shutil.which", return_value="codex-test"), patch("codex_switch.runtime.subprocess.Popen", return_value=proxy) as spawn, patch("codex_switch.runtime.queue.Queue.get", side_effect=queue.Empty):
            state = inspect_runtime(Path("fixture-home"))
        self.assertEqual(state["status"], "unavailable")
        self.assertEqual(state["models"], [])
        self.assertEqual(spawn.call_count, 1)
        self.assertTrue(proxy.stopped)

    def test_missing_client_and_error_messages_stay_unknown(self):
        with patch("codex_switch.runtime.shutil.which", return_value=None):
            self.assertEqual(inspect_runtime(Path("fixture"))["reason"], "client_not_found")
        proxy = ProxyFixture([{"id": 1, "error": {"message": "private-error"}}])
        with patch("codex_switch.runtime.shutil.which", return_value="codex-test"), patch("codex_switch.runtime.subprocess.Popen", return_value=proxy):
            state = inspect_runtime(Path("fixture"))
        self.assertEqual(state["status"], "unavailable")
        self.assertNotIn("private-error", repr(state))

    def test_partial_model_page_is_not_reported_as_full_catalog(self):
        proxy = ProxyFixture([{"id": 1, "result": {}}, {"id": 2, "result": {"data": [{"model": "partial"}], "nextCursor": "more"}}, {"id": 3, "error": {}}])
        with patch("codex_switch.runtime.shutil.which", return_value="codex-test"), patch("codex_switch.runtime.subprocess.Popen", return_value=proxy):
            state = inspect_runtime(Path("fixture"))
        self.assertEqual(state["status"], "connected")
        self.assertFalse(state["models_complete"])
        self.assertIsNone(state["loaded_thread_count"])
