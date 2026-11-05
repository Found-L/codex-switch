"""Small bilingual desktop UI. Keys never leave the masked setup form/store."""
import os
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox
import webbrowser

from . import __version__
from .errors import SwitchError
from .service import SwitchService

BG = "#10141d"
CARD = "#1b2230"
LINE = "#2d3749"
TEXT = "#edf2fc"
MUTED = "#98a8bf"
BLUE = "#6b9dff"
GREEN = "#72d6ac"

COPY = {
    "zh": {
        "tag": "你的 Codex，随时切换", "overview": "连接总览", "settings": "API 配置",
        "cli": "终端命令", "help": "使用帮助", "title": "选择你的连接方式",
        "subtitle": "保留账号登录，在账号额度与 API 之间自由切换。",
        "current": "当前配置", "account": "Codex 账号", "api": "OpenAI API",
        "account_desc": "沿用 Codex 中已登录的账号", "api_desc": "使用自己的 Key，API 单独计费",
        "selected": "已选择", "choose": "使用此连接", "configure": "配置 API Key",
        "manage": "管理 API Key", "ready": "已配置", "missing": "待配置", "refresh": "刷新",
        "scope": "切换后请新建会话，已有会话保留原连接。",
        "success": "已切换到 {name}。请在 Codex 中新建会话。",
        "other": "其他提供商", "error": "操作未完成", "close": "关闭",
        "wizard_title": "连接你的 OpenAI API", "wizard_sub": "在这台电脑完成配置，即可从面板或终端切换。",
        "step1": "01   准备好 API Key", "get_key": "打开 OpenAI Key 管理页 ↗",
        "step2": "02   输入 API Key", "key_hint": "仅保存在当前 Windows 用户的凭据管理器中。",
        "keep": "已保存 Key；留空可保留原 Key。", "show": "显示", "hide": "隐藏",
        "step3": "03   初始模型", "model_hint": "仅新配置需要；已有模型设置会保留。",
        "save": "保存并使用 API", "cancel": "取消", "need_key": "请先输入 API Key。",
        "codex_link": "还没有 Codex？打开官方下载说明 ↗",
        "cli_title": "在终端中同样顺手", "cli_sub": "安装后，打开一个新的 PowerShell 或命令提示符窗口。",
        "cli_note": "配置 Key 时会隐藏输入。账号模式仍需先在 Codex 中登录账号。",
        "copied": "命令已复制。", "copy": "复制", "cli_setup": "首次配置", "cli_status": "查看状态",
        "cli_api": "切换 API", "cli_account": "切换账号", "helper_missing": "无法读取配置，请刷新或查看使用帮助。",
        "profile": "选中的 Codex Profile 覆盖了提供商设置，请先移除该覆盖。",
    },
    "en": {
        "tag": "Your Codex. Your connection.", "overview": "Connections", "settings": "API setup",
        "cli": "Terminal", "help": "Help", "title": "Choose your connection",
        "subtitle": "Keep your account signed in. Switch between account credits and API billing.",
        "current": "CURRENT CONFIGURATION", "account": "Codex account", "api": "OpenAI API",
        "account_desc": "Use the account signed in to Codex", "api_desc": "Your API key. Separate API billing.",
        "selected": "Selected", "choose": "Use connection", "configure": "Set up API key",
        "manage": "Manage API key", "ready": "Configured", "missing": "Setup needed", "refresh": "Refresh",
        "scope": "Start a new chat after switching. Existing chats keep their connection.",
        "success": "Switched to {name}. Start a new chat in Codex.",
        "other": "Other provider", "error": "Action failed", "close": "Close",
        "wizard_title": "Connect your OpenAI API", "wizard_sub": "Set up this computer, then switch from the app or terminal.",
        "step1": "01   Get your API key", "get_key": "Open OpenAI API key dashboard ↗",
        "step2": "02   Enter API key", "key_hint": "Stored in Windows Credential Manager for your user only.",
        "keep": "Key saved. Leave blank to keep the existing key.", "show": "Show", "hide": "Hide",
        "step3": "03   Initial model", "model_hint": "Only for a new configuration. Existing model settings are preserved.",
        "save": "Save and use API", "cancel": "Cancel", "need_key": "Enter an API key first.",
        "codex_link": "Need Codex? Open the official download guide ↗",
        "cli_title": "Just as easy in your terminal", "cli_sub": "After installation, open a new PowerShell or Command Prompt window.",
        "cli_note": "API key input is hidden. Account mode requires signing in to Codex first.",
        "copied": "Command copied.", "copy": "Copy", "cli_setup": "First-time setup", "cli_status": "Check status",
        "cli_api": "Use API", "cli_account": "Use account", "helper_missing": "Cannot read configuration. Refresh or see Help.",
        "profile": "The selected Codex profile overrides the provider. Remove that override first.",
    },
}


def label(parent, text, size=11, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    return tk.Button(parent, text=text, command=command, bg=BLUE if primary else "#293448",
                     fg="#101725" if primary else TEXT, activebackground="#8db4ff" if primary else "#35425a",
                     activeforeground="#101725" if primary else TEXT,
                     disabledforeground=MUTED, font=("Segoe UI", 10, "bold"),
                     relief="flat", bd=0, padx=16, pady=10, cursor="hand2", **kwargs)


class App:
    def __init__(self, root, service):
        self.root, self.service = root, service
        self.lang, self.page = "zh", "overview"
        self.state = None
        root.title("Codex Switch")
        root.geometry("900x680")
        root.minsize(860, 660)
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "assets" / "codex-switch.ico"
        if icon.is_file():
            root.iconbitmap(str(icon))
        root.configure(bg=BG)
        root.option_add("*Font", ("Segoe UI", 10))
        self.render()
        if self.state and not self.state["api_ready"] and self.state["mode"] == "account":
            root.after(350, self.setup)

    def t(self, key):
        return COPY[self.lang][key]

    def render(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        sidebar = tk.Frame(self.root, bg="#151b26", width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Canvas(sidebar, width=44, height=44, bg="#151b26", highlightthickness=0)
        brand.pack(anchor="w", padx=22, pady=(26, 12))
        brand.create_oval(2, 2, 42, 42, outline=BLUE, width=2)
        brand.create_text(22, 21, text="⇄", fill=BLUE, font=("Segoe UI", 23, "bold"))
        label(sidebar, "Codex Switch", 16, bold=True).pack(anchor="w", padx=22)
        label(sidebar, self.t("tag"), 9, MUTED).pack(anchor="w", padx=22, pady=(8, 32))
        for key, action in (("overview", lambda: self.navigate("overview")),
                            ("settings", self.setup), ("cli", lambda: self.navigate("cli"))):
            nav = button(sidebar, self.t(key), action)
            nav.configure(anchor="w", bg="#263653" if self.page == key else "#151b26")
            nav.pack(fill="x", padx=12, pady=4)
        bottom = tk.Frame(sidebar, bg="#151b26")
        bottom.pack(side="bottom", fill="x", padx=22, pady=22)
        button(bottom, "English" if self.lang == "zh" else "中文", self.toggle_language).pack(fill="x", pady=(0, 10))
        link = label(bottom, self.t("help") + " ↗", 10, MUTED, cursor="hand2")
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda _: webbrowser.open("https://github.com/Found-L/codex-switch#readme"))
        label(bottom, "v" + __version__, 9, "#61738d").pack(anchor="w", pady=(12, 0))
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True, padx=30, pady=28)
        self.notice = tk.StringVar()
        if self.page == "cli":
            self.render_cli()
        else:
            self.render_overview()

    def navigate(self, page):
        self.page = page
        self.render()

    def toggle_language(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.render()

    def render_overview(self):
        label(self.content, self.t("title"), 23, bold=True).pack(anchor="w")
        label(self.content, self.t("subtitle"), 10, MUTED, wraplength=570, justify="left").pack(anchor="w", pady=(10, 25))
        try:
            self.state = self.service.status()
        except Exception as error:
            self.state = None
            self.show_error(error)
        mode = self.state["mode"] if self.state else "other"
        current = tk.Frame(self.content, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        current.pack(fill="x", pady=(0, 20))
        label(current, self.t("current"), 9, MUTED).pack(anchor="w", padx=22, pady=(18, 10))
        label(current, self.t(mode), 24, BLUE if mode == "api" else GREEN, True).pack(anchor="w", padx=22, pady=(0, 18))
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x")
        cards.columnconfigure((0, 1), weight=1, uniform="card")
        for column, kind in enumerate(("account", "api")):
            selected = mode == kind
            frame = tk.Frame(cards, bg=CARD, highlightbackground=BLUE if selected else LINE,
                             highlightthickness=2 if selected else 1)
            frame.grid(row=0, column=column, sticky="nsew", padx=(0, 7) if column == 0 else (7, 0))
            label(frame, "C" if kind == "account" else "API", 13, GREEN if kind == "account" else BLUE, True).pack(anchor="w", padx=18, pady=(18, 14))
            label(frame, self.t(kind), 14, bold=True).pack(anchor="w", padx=18)
            label(frame, self.t(kind + "_desc"), 9, MUTED, wraplength=210, justify="left", height=3).pack(anchor="w", padx=18, pady=(5, 10))
            missing = kind == "api" and (not self.state or not self.state["api_ready"])
            text = self.t("configure") if missing else self.t("selected") if selected else self.t("choose")
            action = self.setup if missing else lambda value=kind: self.switch(value)
            control = button(frame, text, action, primary=not selected)
            control.pack(fill="x", padx=16, pady=(0, 16))
            if selected and not missing:
                control.configure(state="disabled", bg="#243347")
        row = tk.Frame(self.content, bg=BG)
        row.pack(fill="x", pady=(18, 0))
        button(row, self.t("manage"), self.setup).pack(side="left")
        button(row, self.t("refresh"), self.render).pack(side="right")
        if self.state and self.state["profile_override"]:
            self.notice.set(self.t("profile"))
        label(self.content, "", 10, GREEN, textvariable=self.notice, wraplength=570, justify="left").pack(anchor="w", pady=(14, 0))
        label(self.content, self.t("scope"), 9, MUTED, wraplength=570, justify="left").pack(side="bottom", anchor="w", pady=(12, 0))

    def switch(self, mode):
        try:
            self.service.use(mode)
            self.render()
            self.notice.set(self.t("success").format(name=self.t(mode)))
        except Exception as error:
            self.show_error(error)

    def show_error(self, error):
        text = str(error) if isinstance(error, SwitchError) else self.t("helper_missing")
        messagebox.showerror(self.t("error"), text, parent=self.root)

    def setup(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("settings") + " — Codex Switch")
        dialog.configure(bg=BG)
        dialog.geometry("620x570")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=24)
        label(body, self.t("wizard_title"), 22, bold=True).pack(anchor="w")
        label(body, self.t("wizard_sub"), 10, MUTED, wraplength=560, justify="left").pack(anchor="w", pady=(10, 22))
        label(body, self.t("step1"), 11, bold=True).pack(anchor="w")
        link = label(body, self.t("get_key"), 10, BLUE, cursor="hand2")
        link.pack(anchor="w", pady=(8, 22))
        link.bind("<Button-1>", lambda _: webbrowser.open("https://platform.openai.com/api-keys"))
        label(body, self.t("step2"), 11, bold=True).pack(anchor="w")
        key_row = tk.Frame(body, bg=BG)
        key_row.pack(fill="x", pady=(10, 6))
        key = tk.Entry(key_row, show="•", bg=CARD, fg=TEXT, insertbackground=TEXT,
                       relief="flat", font=("Segoe UI", 12), borderwidth=10)
        key.pack(side="left", fill="x", expand=True)
        visible = tk.BooleanVar(value=False)

        def toggle():
            visible.set(not visible.get())
            key.configure(show="" if visible.get() else "•")
            eye.configure(text=self.t("hide") if visible.get() else self.t("show"))

        eye = button(key_row, self.t("show"), toggle)
        eye.pack(side="right", padx=(8, 0))
        label(body, self.t("key_hint"), 9, MUTED, wraplength=550).pack(anchor="w")
        try:
            state = self.service.status()
        except Exception as error:
            dialog.destroy()
            self.show_error(error)
            return
        keep = state["key_saved"]
        if keep:
            label(body, self.t("keep"), 9, GREEN).pack(anchor="w", pady=(6, 0))
        label(body, self.t("step3"), 11, bold=True).pack(anchor="w", pady=(20, 8))
        model = tk.Entry(body, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", borderwidth=8)
        model.insert(0, state["model"] or "gpt-6.1-sol")
        model.pack(fill="x")
        if state["model"]:
            model.configure(state="disabled", disabledbackground=CARD, disabledforeground=MUTED)
        label(body, self.t("model_hint"), 9, MUTED, wraplength=550).pack(anchor="w", pady=(6, 14))

        def save():
            value = key.get().strip()
            if not value and not keep:
                messagebox.showerror(self.t("error"), self.t("need_key"), parent=dialog)
                return
            try:
                self.service.setup(value if value else None, model.get().strip())
                self.service.use("api")
                key.delete(0, "end")
                dialog.destroy()
                self.page = "overview"
                self.render()
                self.notice.set(self.t("success").format(name=self.t("api")))
            except Exception as error:
                self.show_error(error)

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(4, 12))
        button(actions, self.t("save"), save, primary=True).pack(side="left")
        button(actions, self.t("cancel"), dialog.destroy).pack(side="right")
        download = label(body, self.t("codex_link"), 9, MUTED, cursor="hand2")
        download.pack(anchor="w")
        download.bind("<Button-1>", lambda _: webbrowser.open("https://learn.chatgpt.com/docs/quickstart"))
        key.focus_set()

    def render_cli(self):
        label(self.content, self.t("cli_title"), 23, bold=True).pack(anchor="w")
        label(self.content, self.t("cli_sub"), 10, MUTED, wraplength=570, justify="left").pack(anchor="w", pady=(12, 28))
        for title, command in (("cli_setup", "codex-switch setup --use"), ("cli_status", "codex-switch status"),
                               ("cli_api", "codex-switch use api"), ("cli_account", "codex-switch use account")):
            label(self.content, self.t(title), 10, MUTED).pack(anchor="w", pady=(6, 6))
            row = tk.Frame(self.content, bg=CARD)
            row.pack(fill="x", pady=(0, 10))
            tk.Label(row, text=command, font=("Consolas", 11), bg=CARD, fg=BLUE, padx=14, pady=12).pack(side="left")
            button(row, self.t("copy"), lambda value=command: self.copy(value)).pack(side="right", padx=4)
        label(self.content, self.t("cli_note"), 10, MUTED, wraplength=570, justify="left").pack(anchor="w", pady=14)
        label(self.content, "", 10, GREEN, textvariable=self.notice).pack(anchor="w")

    def copy(self, command):
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        self.notice.set(self.t("copied"))


def run(home=None):
    root = tk.Tk()
    try:
        service = SwitchService(home)
        App(root, service)
        root.mainloop()
    except Exception as error:
        text = str(error) if isinstance(error, SwitchError) else "Cannot start Codex Switch. Check permissions or reinstall."
        messagebox.showerror("Codex Switch", text, parent=root)
        root.destroy()


def self_test(report):
    """Build the real frozen UI without opening a window or accessing user secrets."""
    root = None
    try:
        class NoCredentials:
            def read(self):
                return None

        with tempfile.TemporaryDirectory(prefix="codex-switch-gui-") as home:
            root = tk.Tk()
            root.withdraw()
            App(root, SwitchService(Path(home), credentials=NoCredentials(), track=False))
            root.update_idletasks()
            result = {"ok": True, "version": __version__, "tcl": root.tk.call("info", "patchlevel"),
                      "tk": root.tk.call("package", "provide", "Tk")}
    except Exception as error:
        result = {"ok": False, "error_type": type(error).__name__}
    finally:
        if root is not None:
            root.destroy()
    Path(report).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["ok"] else 1
