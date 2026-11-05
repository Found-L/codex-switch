"""Render the isolated QML scene offscreen; never capture the user's desktop."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtCore import QEventLoop, QTimer
from codex_switch.gui import Bridge, application, load_scene
from codex_switch.service import SwitchService


class FixtureCredentials:
    value = None
    def read(self): return self.value
    def write(self, value): self.value = value
    def delete(self): self.value = None


def settle():
    loop = QEventLoop()
    QTimer.singleShot(350, loop.quit)
    loop.exec()


app = application(testing=True)
destination = Path(sys.argv[1] if len(sys.argv) > 1 else ".tools/previews")
destination.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="codex-switch-render-") as home:
    service = SwitchService(Path(home), credentials=FixtureCredentials(), track=False)
    service.setup("render-fixture-not-real")
    service.use("api")
    bridge = Bridge(service, testing=True)
    engine, window = load_scene(bridge)
    window.show()
    settle()
    if not window.grabWindow().save(str(destination / "overview.png")):
        raise SystemExit("Offscreen image could not be saved.")
    bridge.openPage.emit("key")
    settle()
    window.grabWindow().save(str(destination / "key.png"))
    bridge.openPage.emit("terminal")
    settle()
    window.grabWindow().save(str(destination / "terminal.png"))
    bridge.openPage.emit("models")
    settle()
    window.grabWindow().save(str(destination / "models-empty.png"))
    from unittest.mock import patch
    service.setup("gateway-fixture", "https://gateway.example/v1")
    entries = [{"id": name, "enabled": False, "context_window": 32768, "reasoning": [], "images": False, "status": "unverified"}
               for name in ("deepseek-flash", "gpt-6.1-sol", "claude-example")]
    with patch("codex_switch.service.discover", return_value=entries):
        service.sync_models()
    bridge.refresh()
    settle()
    bridge.openPage.emit("models")
    settle()
    window.grabWindow().save(str(destination / "models.png"))
    from codex_switch.errors import SwitchError
    bridge._set_notice(bridge._safe_error(SwitchError("Cannot read the model list. Check the API address, certificate and network.")), True)
    settle()
    window.grabWindow().save(str(destination / "models-error.png"))
    bridge.clearNotice()
    bridge.openPage.emit("terminal")
    settle()
    bridge.toggleLanguage()
    settle()
    window.grabWindow().save(str(destination / "terminal-en.png"))
    bridge.toggleCompact()
    settle()
    window.grabWindow().save(str(destination / "mini.png"))
    bridge.shutdown()
print("Isolated offscreen previews saved.")
