"""Persistent Qt Quick utility window with Windows tray/macOS menu bar lifecycle."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QObject, Property, QEvent, QEventLoop, QMetaObject, QSettings, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QAction, QCursor, QDesktopServices, QFont, QFontDatabase, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __version__
from .config import default_home
from .errors import SwitchError
from .service import SwitchService
from .credentials import home_identity

APP_ID = "FoundL.CodexSwitch"


def resources():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def application(testing=False):
    if testing:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    if os.name == "nt" and not testing:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    QQuickStyle.setStyle("Basic")
    app = QApplication.instance() or QApplication(["CodexSwitch"])
    app.setApplicationName("Codex Switch")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("FoundL")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    if testing and os.name == "nt":
        # The offscreen platform has no Windows system-font database. Register
        # local OS fonts for headless previews without redistributing them.
        font_directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc", "consola.ttf"):
            file = font_directory / filename
            if file.is_file():
                QFontDatabase.addApplicationFont(str(file))
    if sys.platform != "darwin":
        app.setFont(QFont("Segoe UI", 10))
    return app


def app_icon():
    filename = "logo.png" if sys.platform == "darwin" else "codex-switch.ico"
    return QIcon(str(resources() / "assets" / filename))


class Bridge(QObject):
    stateChanged = Signal()
    runtimeChanged = Signal()
    busyChanged = Signal()
    noticeChanged = Signal()
    languageChanged = Signal()
    compactChanged = Signal()
    openPage = Signal(str)
    keySaved = Signal()
    catalogApplied = Signal()
    capabilitiesSaved = Signal()
    windowHidden = Signal()
    _completed = Signal(object)

    def __init__(self, service, testing=False):
        super().__init__()
        self.service, self.testing = service, testing
        self.window = None
        self._anchored = False
        self.tray = None
        self.menu = None
        self._busy = False
        self._refreshing = False
        self._runtime = {"status": "not_inspected", "models": []}
        self._notice, self._is_error = "", False
        self._closing, self._quit_when_idle = False, False
        self.settings = None if testing else QSettings("FoundL", "CodexSwitch")
        self._language = "zh" if testing else self.settings.value("language", "zh")
        self._compact = False if testing else self.settings.value("compact", False, type=bool)
        self._font_family = "Segoe UI Variable Text" if "Segoe UI Variable Text" in QFontDatabase.families() else "Segoe UI"
        families = QFontDatabase.families()
        if sys.platform == "darwin":
            self._font_family = QApplication.font().family()
        candidates = ("PingFang SC", "Heiti SC") if sys.platform == "darwin" else ("Microsoft YaHei UI", "Microsoft YaHei")
        self._chinese_font = next((font for font in candidates if font in families), self._font_family)
        self._state = {"mode": "account", "api_ready": False, "key_saved": False, "profile_override": None}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-config")
        self._completed.connect(self._apply_result)
        self.notice_timer = QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.clearNotice)
        try:
            self._state = service.status()
        except Exception as error:
            self._set_notice(self._safe_error(error), True)
        self.timer = QTimer(self)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self._refresh_if_visible)
        if not testing:
            self.timer.start()

    @Property("QVariantMap", notify=stateChanged)
    def state(self):
        return self._state

    @Property("QVariantMap", notify=runtimeChanged)
    def runtimeState(self):
        return self._runtime

    @Slot()
    def inspectRuntime(self):
        from .runtime import inspect_runtime
        def inspect():
            return inspect_runtime(self.service.home)
        self._submit(inspect, "runtime")

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=noticeChanged)
    def notice(self):
        return self._notice

    @Property(bool, notify=noticeChanged)
    def isError(self):
        return self._is_error

    @Property(str, notify=languageChanged)
    def language(self):
        return self._language

    @Property(bool, notify=compactChanged)
    def compact(self):
        return self._compact

    @Property(bool, constant=True)
    def testingMode(self):
        return self.testing

    @Property(bool, constant=True)
    def isMac(self):
        return sys.platform == "darwin"

    @Property(str, constant=True)
    def version(self):
        return __version__

    @Property(str, constant=True)
    def logoUrl(self):
        return QUrl.fromLocalFile(str(resources() / "assets" / "logo.png")).toString()

    @Property(str, notify=languageChanged)
    def fontFamily(self):
        return self._chinese_font if self._language == "zh" else self._font_family

    def tr_text(self, zh, en):
        return zh if self._language == "zh" else en

    def _safe_error(self, error):
        if not isinstance(error, SwitchError):
            return self.tr_text("操作未完成，请检查连接和本地权限后重试。", "Operation failed. Check the connection and local permissions, then retry.")
        message = str(error)
        translations = {
            "Audio, image, embedding and other non-coding models cannot be added to the Codex menu.": "音频、图像、嵌入等非编程模型不能加入 Codex 菜单。",
            "A selected model is no longer in the synchronized list. Refresh and choose again.": "所选模型已不在最新名单中，请同步后重新选择。",
            "Save the API connection in Codex Switch before synchronizing models.": "请先在「API 配置」中保存接口地址和 Key，再同步模型。",
            "Cannot read the existing API key. Repair the credential helper or save a new API connection.": "无法读取已有 API Key，请检查旧版取钥程序，或在「API 配置」中保存连接。",
            "The legacy API authentication is ambiguous. Save a new API connection first.": "旧版 API 同时配置了多种认证方式，请在「API 配置」中重新保存连接。",
            "The legacy credential helper is invalid. Repair it or save a new API connection.": "旧版取钥程序配置无效，请修复后重试，或在「API 配置」中保存连接。",
            "The legacy API endpoint is not supported. Save a new API connection first.": "此旧版接口暂不支持直接沿用，请在「API 配置」中保存连接。",
            "The API provider changed. Sync and apply the models again.": "API 连接已变化，请重新同步并应用模型目录。",
            "Cannot read the model list. Check the API address, certificate and network.": "无法获取模型名单，请检查 API 地址、证书和网络连接。",
            "No models were returned for this key. Check New API groups and token model limits.": "接口未返回模型，请检查 Key 的分组和模型权限。",
            "Enable at least one coding model before applying the catalog.": "请先勾选至少一个编程模型，再应用目录。",
            "Choose an enabled model as the default.": "请先启用并保存当前模型，再将它设为默认模型。",
            "Connection changed during synchronization. Retry.": "同步期间连接发生变化，请重新同步。",
            "The model list or settings changed. Apply the updated catalog before switching to API.": "模型名单或设置有待应用的更改，请先应用目录，再切到 API。",
            "Context window must be an integer.": "上下文长度必须填写整数。",
            "Context window must be between 4096 and 4000000 tokens.": "上下文长度须在 4096 到 4000000 tokens 之间。",
            "Unsupported or duplicate reasoning level.": "推理档位不受支持或重复，请检查填写内容。",
            "Enter the key for the new API address. A saved key is never reused on another endpoint.": "更换 API 地址时，请输入该地址对应的 Key。",
            "API key cannot be empty or contain spaces/control characters.": "API Key 不能为空，也不能包含空格或控制字符。",
            "Use an HTTPS API base URL without credentials, query or fragment (HTTP only for loopback).": "请填写 HTTPS 接口地址，不要带账号密码、查询参数或 #；HTTP 仅支持本机地址。",
        }
        if self._language == "zh":
            if message.startswith("Model discovery failed (HTTP "):
                code = message.split("HTTP ", 1)[1].split(")", 1)[0]
                return "同步失败（HTTP " + code + "），请检查地址、Key 和模型权限。"
            return translations.get(message, message)
        return message

    def _set_notice(self, text, error=False):
        self._notice, self._is_error = text, error
        self.noticeChanged.emit()
        if text:
            self.notice_timer.start(12000 if error else 5500)

    def _submit(self, operation, kind):
        if self._busy or self._closing or (kind == "refresh" and self._refreshing):
            return
        if kind == "refresh":
            self._refreshing = True
        else:
            self._busy = True
            self.busyChanged.emit()
            self._update_tray()

        def work():
            error = None
            output = None
            try:
                output = operation()
            except Exception as exception:
                error = self._safe_error(exception)
            try:
                state = self.service.status()
            except Exception:
                state = self._state
            return {"kind": kind, "error": error, "state": state, "output": output}

        future = self.pool.submit(work)
        future.add_done_callback(lambda done: self._completed.emit(done.result()))

    @Slot(object)
    def _apply_result(self, result):
        if result["kind"] == "runtime" and isinstance(result.get("output"), dict):
            self._runtime = result["output"]
            self.runtimeChanged.emit()
        if self._state != result["state"]:
            self._state = result["state"]
            self.stateChanged.emit()
        if result["kind"] == "refresh":
            self._refreshing = False
        else:
            self._busy = False
            self.busyChanged.emit()
        self._update_tray()
        if result["error"]:
            self._set_notice(result["error"], True)
        elif result["kind"] in ("switch", "setup"):
            name = self._state.get("api_label", "API") if self._state["mode"] == "api" else self.tr_text("Codex 账号", "Codex account")
            self._set_notice(self.tr_text("配置已切到 " + name + "；已有会话连接未验证。", "Configuration set to " + name + "; existing chat routes are unverified."))
            if result["kind"] == "setup":
                self.keySaved.emit()
                self.openPage.emit("models" if self._state.get("base_url") != "https://api.openai.com/v1" else "connections")
                self._set_notice(self.tr_text("API 已保存。自定义接口请同步并配置模型。", "API saved. Discover and configure models for custom endpoints."))
        elif result["kind"] == "sync-models":
            self._set_notice(self.tr_text("模型名单已更新，请勾选需要的模型后应用。", "Models refreshed. Select the models you want, then apply."))
        elif result["kind"] == "configure-model":
            self._set_notice(self.tr_text("模型设置已保存，请应用目录。", "Model settings saved. Apply the catalog next."))
            self.capabilitiesSaved.emit()
        elif result["kind"] == "apply-models":
            self._set_notice(self.tr_text("目录已写入配置。请完全退出并重启 Codex；尚未验证桌面加载或模型调用。", "Catalog written to config. Fully quit and restart Codex. Desktop loading and inference are unverified."))
            self.catalogApplied.emit()
        elif result["kind"] == "reset-models":
            self._set_notice(self.tr_text("已撤销自定义模型目录，API 配置仍保留。请完全退出并重启 Codex。", "Custom catalog reset. API connection retained. Fully quit and restart Codex."))
        elif result["kind"] == "install-cli":
            self._set_notice(self.tr_text("终端命令已安装，请重新打开终端。", "Terminal command installed. Open a new terminal."))
        if self._quit_when_idle:
            self.quitApp()

    @Slot(str)
    def switchTo(self, mode):
        if self._busy:
            return
        if mode == "api" and not self._state.get("api_ready"):
            if self._compact:
                self.toggleCompact()
            self.openPage.emit("key")
            self.show_window()
            return
        if mode == "api" and self._state.get("base_url") != "https://api.openai.com/v1" and not self._state.get("catalog_enabled"):
            if self._compact:
                self.toggleCompact()
            self.openPage.emit("models")
            self.show_window()
            return
        self._submit(lambda: self.service.use(mode), "switch")

    @Slot(str)
    def saveKey(self, key):
        self.saveConnection(key, self._state.get("base_url", "https://api.openai.com/v1"))

    @Slot(str, str)
    def saveConnection(self, key, base_url):
        if not key.strip() and not self._state.get("key_saved"):
            self._set_notice(self.tr_text("请先输入 API Key。", "Enter an API key first."), True)
            return

        def save():
            self.service.setup(key if key.strip() else None, base_url)
            state = self.service.status()
            if state["base_url"] == "https://api.openai.com/v1" or state["catalog_enabled"]:
                self.service.use("api")

        self._submit(save, "setup")

    @Slot()
    def syncModels(self):
        if not self._state.get("api_ready"):
            self.openPage.emit("key")
            self._set_notice(self.tr_text("请先保存 API 地址和 Key，再同步模型。", "Save the API URL and key before discovering models."), True)
            return
        self._submit(self.service.sync_models, "sync-models")

    @Slot()
    def resetModels(self):
        self._submit(self.service.reset_models, "reset-models")

    @Slot(str, bool, str, str, bool)
    def configureModel(self, model, enabled, context, reasoning, images):
        def save():
            try:
                count = int(context)
            except ValueError:
                raise SwitchError("Context window must be an integer.") from None
            self.service.configure_model(model, enabled, count, [e.strip() for e in reasoning.split(",") if e.strip()], images)
        self._submit(save, "configure-model")

    @Slot(str)
    def applyModels(self, default_model):
        def apply():
            self.service.apply_models(default_model or None)
            self.service.use("api")
        self._submit(apply, "apply-models")

    @Slot(str, str)
    def applySelection(self, selection_json, default_model):
        def apply():
            selected = json.loads(selection_json)
            self.service.apply_models(default_model or None, selected=selected, activate=True)
        self._submit(apply, "apply-models")

    @Slot(str)
    def resetCapabilities(self, model):
        self._submit(lambda: self.service.reset_capabilities(model), "configure-model")

    @Slot()
    def refresh(self):
        self._submit(lambda: None, "refresh")

    def _refresh_if_visible(self):
        if self.window and self.window.isVisible() and not self._busy:
            self.refresh()

    @Slot()
    def toggleLanguage(self):
        self._language = "en" if self._language == "zh" else "zh"
        if self.settings:
            self.settings.setValue("language", self._language)
        self.languageChanged.emit()
        self._update_tray()

    @Slot()
    def toggleCompact(self):
        self._compact = not self._compact
        if self.settings:
            self.settings.setValue("compact", self._compact)
        self.compactChanged.emit()
        self._update_tray()

    @Slot(str)
    def copyText(self, text):
        QApplication.clipboard().setText(text)
        self._set_notice(self.tr_text("命令已复制。", "Command copied."))

    @Slot()
    def installCli(self):
        if sys.platform == "darwin":
            from .terminal import install_cli
            self._submit(lambda: install_cli(self.service.helper[0]), "install-cli")

    @Slot(str)
    def openLink(self, name):
        links = {"key": "https://platform.openai.com/api-keys", "codex": "https://learn.chatgpt.com/docs/quickstart",
                 "help": "https://github.com/Found-L/codex-switch#readme"}
        if name in links:
            QDesktopServices.openUrl(QUrl(links[name]))

    @Slot()
    def clearNotice(self):
        self._set_notice("")

    def attach(self, window):
        self.window = window
        window.activeChanged.connect(self._focus_changed)
        window.setIcon(app_icon())
        if not self.testing and QSystemTrayIcon.isSystemTrayAvailable():
            icon = QApplication.windowIcon()
            if sys.platform == "darwin":
                icon = QIcon(str(resources() / "assets" / "tray-template.png"))
                icon.setIsMask(True)
            self.tray = QSystemTrayIcon(icon, self)
            self.menu = QMenu()
            if sys.platform != "darwin":
                self.menu.setStyleSheet("QMenu {background:#ffffff;color:#242936;border:1px solid #e3e6ed;border-radius:8px;padding:6px;} QMenu::item {padding:7px 20px;border-radius:5px;} QMenu::item:selected {background:#eef0ff;color:#5146d8;} QMenu::separator {height:1px;background:#eceef3;margin:5px;}")
            self.open_action = self.menu.addAction("Open", lambda: self.show_window(anchor=True))
            self.compact_action = self.menu.addAction("Mini", self._tray_compact)
            self.menu.addSeparator()
            self.provider_actions = {}
            for mode in ("account", "api"):
                action = self.menu.addAction(mode)
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, value=mode: self._tray_switch(value))
                self.provider_actions[mode] = action
            self.menu.addSeparator()
            self.key_action = self.menu.addAction("API Key", self._tray_setup)
            self.quit_action = self.menu.addAction("Quit", self.quitApp)
            self._update_tray()
            if sys.platform != "darwin":
                # On macOS a permanently attached menu consumes left clicks.
                self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()

    def _update_tray(self):
        if not self.tray:
            return
        name = self._state.get("api_label", "API") if self._state["mode"] == "api" else self.tr_text("Codex 账号", "Codex account")
        self.tray.setToolTip("Codex Switch · " + name)
        self.open_action.setText(self.tr_text("打开面板", "Open panel"))
        self.compact_action.setText(self.tr_text("迷你窗口" if not self._compact else "完整面板", "Mini window" if not self._compact else "Full panel"))
        for mode, title in (("account", self.tr_text("Codex 账号", "Codex account")), ("api", self._state.get("api_label", "API"))):
            action = self.provider_actions[mode]
            action.setText(title)
            action.setChecked(self._state["mode"] == mode)
            action.setEnabled(not self._busy)
        self.key_action.setText(self.tr_text("配置 API Key", "API key settings"))
        self.quit_action.setText(self.tr_text("退出 Codex Switch", "Quit Codex Switch"))

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context and sys.platform == "darwin":
            self.menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window(anchor=True)
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.hideToTray()
            else:
                self.show_window(anchor=True)

    def _tray_compact(self):
        self.toggleCompact()
        QTimer.singleShot(0, lambda: self.show_window(anchor=True))

    def _tray_switch(self, mode):
        self.switchTo(mode)

    def _tray_setup(self):
        if self._compact:
            self.toggleCompact()
        self.openPage.emit("key")
        QTimer.singleShot(0, lambda: self.show_window(anchor=True))

    def show_window(self, anchor=False):
        if not self.window or self.testing:
            return
        self._anchored = anchor
        if anchor and self.tray:
            rectangle = self.tray.geometry()
            point = rectangle.center() if not rectangle.isEmpty() else QCursor.pos()
            screen = QApplication.screenAt(point) or QApplication.primaryScreen()
            available = screen.availableGeometry()
            self.window.setX(max(available.left(), min(point.x() - self.window.width() // 2, available.right() - self.window.width())))
            desired_y = rectangle.bottom() + 8 if sys.platform == "darwin" else available.bottom() - self.window.height() - 8
            self.window.setY(max(available.top(), min(desired_y, available.bottom() - self.window.height())))
        self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()
        self.refresh()

    def _focus_changed(self):
        if self._anchored and self.window and not self.window.isActive():
            QTimer.singleShot(160, self._dismiss_popover)

    def _dismiss_popover(self):
        if (self._anchored and self.window and not self.window.isActive() and not self._busy
                and not (self.menu and self.menu.isVisible())):
            self.hideToTray()

    @Slot()
    def hideToTray(self):
        if self.window and self.tray and self.tray.isVisible():
            self.windowHidden.emit()
            self.window.hide()
        elif not self.testing:
            self.quitApp()

    @Slot()
    def quitApp(self):
        if self._busy:
            self._quit_when_idle = True
            self._set_notice(self.tr_text("保存完成后退出…", "Quitting after the save finishes…"))
            return
        self._closing = True
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def shutdown(self):
        self._closing = True
        self.timer.stop()
        self.notice_timer.stop()
        if self.tray:
            self.tray.hide()
        self.pool.shutdown(wait=True, cancel_futures=True)


def load_scene(model):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", model)
    engine.load(QUrl.fromLocalFile(str(resources() / "ui" / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("The desktop scene could not be loaded.")
    window = engine.rootObjects()[0]
    model.attach(window)
    return engine, window


def instance_server(home, model):
    identity = hashlib.sha256(home_identity(home).encode()).hexdigest()[:24]
    name = "FoundL-CodexSwitch-" + identity
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(250):
        socket.write(b"show")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return None
    server = QLocalServer(model)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        # Another process may have won the race while this process was starting.
        socket.connectToServer(name)
        if socket.waitForConnected(500):
            socket.write(b"show")
            socket.waitForBytesWritten(500)
            return None
        raise RuntimeError("Cannot open the application activation channel.")

    def receive(client):
        data = bytes(client.readAll()).strip()
        if data == b"status":
            client.write(json.dumps({"version": __version__, "visible": bool(model.window and model.window.isVisible()),
                                     "compact": model.compact, "tray_visible": bool(model.tray and model.tray.isVisible())}).encode())
            client.flush()
        elif data == b"show":
            model.show_window()
        client.disconnectFromServer()

    def accept():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.readyRead.connect(lambda client=connection: receive(client))
            connection.disconnected.connect(connection.deleteLater)
            if connection.bytesAvailable():
                receive(connection)

    server.newConnection.connect(accept)
    return server


def run(home=None):
    app = application()
    model = Bridge(SwitchService(home))
    server = instance_server(model.service.home, model)
    if server is None:
        model.shutdown()
        return
    engine, window = load_scene(model)
    app.aboutToQuit.connect(model.shutdown)
    model.show_window()
    app.exec()
    server.close()


def self_test(report, native=False):
    """Run the real QML scene offscreen using an isolated config and fake key store."""
    result = {"ok": False}
    model = None
    native_service = None
    phase = "startup"
    try:
        if native and (sys.platform != "darwin" or os.environ.get("CODEX_SWITCH_NO_KEYCHAIN_UI") != "1"):
            raise RuntimeError("Native Keychain GUI smoke is restricted to noninteractive macOS tests.")
        app = application(testing=True)

        class MemoryCredentials:
            value = None
            def read(self): return self.value
            def write(self, key): self.value = key
            def delete(self): self.value = None

        with tempfile.TemporaryDirectory(prefix="codex-switch-qt-") as home:
            service = SwitchService(Path(home), credentials=None if native else MemoryCredentials(), track=False)
            if native:
                from .credentials import HelperCredentials
                if not isinstance(service.credentials, HelperCredentials):
                    raise RuntimeError("Packaged GUI must delegate Keychain access to its helper.")
                native_service = service
            model = Bridge(service, testing=True)
            engine, window = load_scene(model)
            window.show()
            app.processEvents()
            names = ("connectionsPage", "keyPage", "terminalPage", "modelsPage", "selectionPill", "apiKeyField", "gatewayModelList")
            objects = {name: window.findChild(QObject, name) for name in names}
            if not all(objects.values()):
                raise RuntimeError("Required persistent controls are missing.")
            if window.findChild(QObject, "modelField") is not None:
                raise RuntimeError("Model selection must remain in Codex.")
            model.openPage.emit("models")
            model.syncModels()
            app.processEvents()
            if model.busy or window.property("page") != "key" or "API 地址" not in model.notice:
                raise RuntimeError("Missing API setup did not show localized navigation guidance.")
            if window.findChild(QObject, "applyModelButton").property("enabled"):
                raise RuntimeError("Empty model lists must not enable apply controls.")
            model.clearNotice()

            def wait_idle():
                loop = QEventLoop()
                timer = QTimer()
                timer.setInterval(10)
                timer.timeout.connect(lambda: loop.quit() if not model.busy else None)
                QTimer.singleShot(8000, loop.quit)
                timer.start()
                loop.exec()
                timer.stop()
                if model.busy or model.isError:
                    raise RuntimeError("Asynchronous UI operation did not complete.")

            phase = "setup-and-switch"
            model.saveKey("qt-fixture-not-real")
            wait_idle()
            if model.state["mode"] != "api": raise RuntimeError("API setup did not switch.")
            model.switchTo("account")
            wait_idle()
            if model.state["mode"] != "account": raise RuntimeError("Account switch did not complete.")
            model.switchTo("api")
            wait_idle()
            for name, original in objects.items():
                if window.findChild(QObject, name) is not original:
                    raise RuntimeError("A state update rebuilt the scene.")
            phase = "page-transitions"
            for page in ("key", "models", "terminal", "connections"):
                samples = []
                loop = QEventLoop()
                sample_timer = QTimer()
                sample_timer.setInterval(8)
                sample_timer.timeout.connect(lambda: samples.append(sum(
                    bool(objects[name].property("visible"))
                    for name in ("connectionsPage", "keyPage", "modelsPage", "terminalPage"))))
                sample_timer.start()
                model.openPage.emit(page)
                QTimer.singleShot(300, loop.quit)
                loop.exec()
                sample_timer.stop()
                if not samples or max(samples) > 1 or not objects[page + "Page"].property("visible"):
                    raise RuntimeError("Page transitions overlap or fail to reveal the destination.")
            model.toggleCompact()
            app.processEvents()
            if window.width() != 372 or window.height() != 302:
                raise RuntimeError("Mini window geometry is incorrect.")
            if "model" in __import__("tomllib").loads(service.config.read().decode()):
                raise RuntimeError("Setup unexpectedly wrote a model.")
            model.toggleCompact()
            app.processEvents()
            # Exercise the actual asynchronous gateway flow without any external request.
            from unittest.mock import patch as mock_patch
            phase = "gateway-setup"
            model.saveConnection("gateway-qt-fixture", "https://gateway.example/v1")
            wait_idle()
            fixture = [{"id": "gateway-coding-model", "enabled": False, "context_window": 32768,
                        "reasoning": [], "images": False, "status": "unverified"},
                       {"id": "gateway-second-model", "enabled": False, "context_window": 32768,
                        "reasoning": [], "images": False, "status": "unverified"},
                       {"id": "gpt-image-1", "enabled": False, "context_window": 32768,
                        "reasoning": [], "images": False, "status": "unverified"}]
            phase = "gateway-models"
            with mock_patch("codex_switch.service.discover", return_value=fixture):
                model.syncModels()
                wait_idle()
            reveal = QEventLoop()
            QTimer.singleShot(350, reveal.quit)
            reveal.exec()
            # Interact with the same draft, search and apply controls used by the UI.
            from PySide6.QtCore import Q_ARG
            picker = objects["modelsPage"]
            picker.setProperty("scope", "all")
            QMetaObject.invokeMethod(picker, "toggle", Qt.DirectConnection, Q_ARG("QVariant", "gateway-coding-model"))
            QMetaObject.invokeMethod(picker, "toggle", Qt.DirectConnection, Q_ARG("QVariant", "gateway-second-model"))
            QMetaObject.invokeMethod(picker, "toggle", Qt.DirectConnection, Q_ARG("QVariant", "gpt-image-1"))
            if len(picker.property("selectedIds").toVariant()) != 2:
                raise RuntimeError("Non-coding model was selectable.")
            picker.setProperty("defaultId", "gateway-second-model")
            search = window.findChild(QObject, "modelSearch")
            search.setProperty("text", "second-model")
            app.processEvents()
            if objects["gatewayModelList"].property("count") != 1:
                raise RuntimeError("Model search did not filter the list.")
            phase = "state-comparison"
            picker.setProperty("scope", "selected")
            search.setProperty("text", "missing-search")
            app.processEvents()
            if objects["gatewayModelList"].property("count") != 0 or len(picker.property("selectedIds").toVariant()) != 2:
                raise RuntimeError("Search results were confused with the selection count.")
            panel = window.findChild(QObject, "modelStatePanel")
            if panel is None or window.findChild(QObject, "runtimeSummary") is None:
                raise RuntimeError("Independent state panels are missing.")
            panel.setProperty("visible", True)
            before = service.config.read()
            # Add the configured model to the local draft, without any config write.
            model._state = dict(model.state, model="gateway-second-model")
            model.stateChanged.emit()
            QMetaObject.invokeMethod(picker, "includeConfigured", Qt.DirectConnection)
            if service.config.read() != before or picker.property("defaultId") != "gateway-second-model":
                raise RuntimeError("Add configured model failed or wrote the draft early.")
            model._state = service.status()
            model.stateChanged.emit()
            panel.setProperty("visible", False)
            with mock_patch("codex_switch.runtime.inspect_runtime", return_value={"status": "unavailable", "models": [], "foreground_model": None, "billing_route_verified": False}):
                model.inspectRuntime()
                wait_idle()
            if model.runtimeState["status"] != "unavailable" or service.config.read() != before:
                raise RuntimeError("Runtime inspection changed config or inferred a live connection.")
            if service.status()["catalog_enabled"] or any(m["enabled"] for m in service.status()["models"]):
                raise RuntimeError("Draft selection wrote configuration before apply.")
            search.setProperty("text", "")
            QMetaObject.invokeMethod(picker, "openDetails", Qt.DirectConnection, Q_ARG("QVariant", "gateway-second-model"))
            app.processEvents()
            from PySide6.QtCore import QPoint, QPointF
            from PySide6.QtTest import QTest
            point = picker.mapToScene(QPointF(23, 161))
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))
            if len(picker.property("selectedIds").toVariant()) != 2:
                raise RuntimeError("Advanced settings allowed clicks through to the model list.")
            window.findChild(QObject, "gatewayContextField").setProperty("text", "65536")
            window.findChild(QObject, "gatewayReasoningField").setProperty("text", "low,high")
            QMetaObject.invokeMethod(window.findChild(QObject, "saveModelButton"), "clicked", Qt.DirectConnection)
            wait_idle()
            window.findChild(QObject, "advancedModelPanel").setProperty("visible", False)
            if len(picker.property("selectedIds").toVariant()) != 2:
                raise RuntimeError("Draft selection was lost while saving capabilities.")
            QMetaObject.invokeMethod(window.findChild(QObject, "applyModelButton"), "clicked", Qt.DirectConnection)
            wait_idle()
            if model.state["model"] != "gateway-second-model" or not model.state["catalog_active"]:
                raise RuntimeError("Gateway catalog was not applied.")
            if sum(bool(m["enabled"]) for m in model.state["models"]) != 2:
                raise RuntimeError("Batch model selection was not saved.")
            model._set_notice(model._safe_error(SwitchError("Cannot read the model list. Check the API address, certificate and network.")), True)
            app.processEvents()
            area = window.findChild(QObject, "pagesArea")
            notice = window.findChild(QObject, "noticeText")
            if area.property("y") + area.property("height") > notice.property("y"):
                raise RuntimeError("Error notice overlaps the page actions.")
            if "无法获取模型名单" not in model.notice:
                raise RuntimeError("Model errors were not localized.")
            model.clearNotice()
            model.switchTo("account")
            wait_idle()
            if model.state["model"] or model.state["catalog_active"]:
                raise RuntimeError("Account model settings were not restored.")
            server = instance_server(service.home, model)
            if server is None or instance_server(service.home, model) is not None:
                raise RuntimeError("Single-instance activation did not work.")
            app.processEvents()
            server.close()
            result = {"ok": True, "version": __version__, "qt": pyside_version,
                      "persistent_controls": True, "async_switching": True,
                      "page_transition_no_overlap": True,
                      "native_keychain": native,
                      "gateway_catalog_flow": True, "search_multi_select": True, "state_comparison": True,
                      "empty_model_guidance": True, "notice_no_overlap": True,
                      "mini_window": True, "single_instance": True, "setup_entry_count": 1}
            model.shutdown()
            window.close()
            engine.deleteLater()
            app.sendPostedEvents(engine, QEvent.DeferredDelete)
            app.processEvents()
            model = None
    except Exception as error:
        result = {"ok": False, "error_type": type(error).__name__, "phase": phase}
    finally:
        if model:
            model.shutdown()
        if native_service:
            try:
                native_service.remove_api()
            except Exception as error:
                result = {"ok": False, "error_type": type(error).__name__, "phase": "native-cleanup"}
    Path(report).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["ok"] else 1
