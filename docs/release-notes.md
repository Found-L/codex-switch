## Codex Switch v0.3.0

- 新增 macOS 14+ Apple Silicon 和 Intel 原生 DMG：拖入 Applications 后引导配置自己的 Key。
- Key 保存在当前用户的 macOS 登录钥匙串；通过 Security.framework 读写，不将秘密放入命令参数或配置文件。
- 新增 Mac 菜单栏模板图标、菜单栏下方弹出面板、苹方字体与 Command 快捷键，继续支持迷你窗口。
- Mac「终端」页一键安装 / 修复 `~/.local/bin/codex-switch` 与 zsh/bash PATH。保留原 shell 内容，不覆盖无关同名命令。
- 新增 Mac `install-cli`、`uninstall-cli`、`uninstall --yes`：卸载前清理自建提供商、钥匙串和终端集成，保留 Codex 账号与备份。
- Windows 原用法保留，PowerShell、CMD、Git Bash 均可使用；安装后请彻底重开原终端以刷新 PATH。
- CI 覆盖 Windows、原生 arm64 / x86_64 Mac、隔离钥匙串、冻结 GUI、DMG 复制安装、取钥、zsh PATH、切换及卸载。

Mac 无 Developer ID 凭据的构建采用 ad-hoc 签名，未经过 Apple 公证；首次打开请按 [macOS 指南](https://github.com/Found-L/codex-switch/blob/main/docs/macos.md) 操作。已接好可选 Developer ID 签名与 notarytool 公证流程，配置仓库凭据后启用。

Native macOS 14+ Apple Silicon/Intel DMGs, login Keychain storage, menu-bar integration, terminal command installation and safe uninstall. Windows remains supported. Mac builds without Developer ID credentials are ad-hoc signed, not Apple-notarized. Models stay configured in Codex; switching itself makes no model requests.
