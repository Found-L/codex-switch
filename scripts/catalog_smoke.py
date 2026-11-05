"""Read a local catalog through an installed Codex app-server; never run inference."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.catalog import model_info
from codex_switch.settings import atomic_json

executable = shutil.which("codex")
if not executable:
    raise SystemExit("Codex executable required for catalog acceptance.")
with tempfile.TemporaryDirectory(prefix="switch-catalog-") as temporary:
    home = Path(temporary)
    catalog = home / "catalog.json"
    atomic_json(catalog, {"models": [model_info("gateway-test-deepseek", 65536, ["low", "high"]),
                                   model_info("gateway-test-other", 32768)]})
    (home / "config.toml").write_text('model_provider="fixture"\nmodel_catalog_json=' + json.dumps(str(catalog)) + '\n[model_providers.fixture]\nname="Test only"\nbase_url="http://127.0.0.1:9/v1"\nwire_api="responses"\n', encoding="utf-8")
    env = dict(os.environ, CODEX_HOME=str(home))
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY"):
        env.pop(name, None)
    process = subprocess.Popen([executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env, cwd=home,
                               **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
    messages = queue.Queue()
    def reader():
        for line in process.stdout:
            try: messages.put(json.loads(line))
            except ValueError: pass
    threading.Thread(target=reader, daemon=True).start()
    def send(value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()
    def receive(identifier):
        for _ in range(50):
            value = messages.get(timeout=15)
            if value.get("id") == identifier:
                if "error" in value:
                    raise RuntimeError("Codex rejected catalog operation: " + str(value["error"]))
                return value["result"]
        raise RuntimeError("No matching Codex response.")
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "catalog_smoke", "version": "0.4.0"}}})
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "model/list", "params": {}})
        result = receive(2)
        models = result["data"]
        assert {m["model"] for m in models} == {"gateway-test-deepseek", "gateway-test-other"}, "Unexpected models in picker"
        deepseek = next(m for m in models if m["model"] == "gateway-test-deepseek")
        assert [v["reasoningEffort"] for v in deepseek["supportedReasoningEfforts"]] == ["low", "high"]
        assert all(not m.get("additionalSpeedTiers") and not m.get("serviceTiers") for m in models)
        print("Codex app-server accepted both custom model entries, reasoning levels and empty speed tiers; no inference.")
    finally:
        if os.name == "nt":
            # The Windows launcher owns an app-server child; terminate our whole tree.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                process.terminate()
            process.wait(timeout=10)
        process.stdout.close()
