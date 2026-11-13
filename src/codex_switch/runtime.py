from . import __version__
"""Read an existing local server. Never launch a replacement or start a turn."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone


def inspect_runtime(home):
    state = {"status": "unavailable", "source": "existing_app_server_proxy",
             "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "models": [], "loaded_thread_count": None,
             "foreground_model": None, "billing_route_verified": False}
    executable = shutil.which("codex")
    if not executable:
        return dict(state, reason="client_not_found")
    process = None
    try:
        process = subprocess.Popen([executable, "app-server", "proxy"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=dict(os.environ, CODEX_HOME=str(home)),
                                   **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        messages = queue.Queue(maxsize=64)

        def reader():
            try:
                while True:
                    line = process.stdout.readline(1024 * 1024 + 1)
                    if not line or len(line) > 1024 * 1024:
                        return
                    value = json.loads(line)
                    if isinstance(value, dict) and "id" in value and "method" not in value:
                        messages.put_nowait(value)
            except (OSError, ValueError, queue.Full):
                pass

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        deadline = time.monotonic() + 4

        def send(value):
            process.stdin.write(json.dumps(value).encode() + b"\n")
            process.stdin.flush()

        def request(identifier, method, params):
            send({"id": identifier, "method": method, "params": params})
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                reply = messages.get(timeout=remaining)
                if reply.get("id") == identifier:
                    if "error" in reply:
                        raise ValueError()
                    return reply["result"]

        request(1, "initialize", {"clientInfo": {"name": "codex_switch_status", "version": __version__}})
        send({"method": "initialized"})
        result = request(2, "model/list", {"limit": 100})
        models = result.get("data", [])
        ids = [m["model"] for m in models if isinstance(m, dict) and isinstance(m.get("model"), str)
               and len(m["model"]) <= 200 and not any(ord(c) < 32 for c in m["model"])]
        # Incomplete pages must not be compared with a saved full catalog.
        state.update(status="connected", models=list(dict.fromkeys(ids)),
                     models_complete=not bool(result.get("nextCursor")))
        try:
            loaded = request(3, "thread/loaded/list", {})
            if isinstance(loaded.get("data"), list):
                state["loaded_thread_count"] = len(loaded["data"])
        except (ValueError, KeyError, TypeError, TimeoutError, queue.Empty):
            pass
        return state
    except (OSError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, queue.Empty):
        return dict(state, reason="control_unavailable")
    finally:
        if process:
            if process.poll() is None:
                process.terminate()  # Only our proxy, never the server or its threads.
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
