# macOS 安装与使用

支持 macOS 14 或更新版本。Apple Silicon（M 系列）下载 `macos-arm64.dmg`；Intel Mac 下载 `macos-x64.dmg`。在「关于本机」查看芯片类型。无需安装 Python、Homebrew 或使用管理员权限安装命令。

1. 先安装 Codex；需要使用账号额度时，在 Codex 中登录自己的账号。
2. 从 [Releases](https://github.com/Found-L/codex-switch/releases/latest) 下载对应芯片的 DMG，打开后将 **Codex Switch.app 拖入 Applications**，再从 Applications 打开。
3. 在应用的 API Key 页输入自己的 OpenAI API Key，保存并使用 API。工具不会发送请求验证 Key，也不会替你选模型。
4. 在 Codex 中新建会话。之后通过面板或屏幕顶部菜单栏图标切换账号/API。
5. 需要终端命令时，打开应用「终端」页，点击「安装 / 修复终端命令」，然后重新打开 Terminal、iTerm 或 VS Code 终端。

没有 `/Applications` 写入权限时，可把 App 放入自己的 `~/Applications`。后文的手动命令路径相应替换为实际位置。

这是菜单栏工具，关闭窗口后仍在菜单栏运行，通常不显示 Dock 图标。左键打开/收起面板，右键菜单可切换、配置或退出。快捷键为 ⌘M 收起、⇧⌘M 切换小窗、⌘Q 退出。

## 终端

```bash
codex-switch status
codex-switch setup --use
codex-switch use api
codex-switch use account
codex-switch doctor --json
codex-switch gui
```

Key 通过隐藏输入读取，保存在当前 macOS 用户的登录钥匙串中，不放入命令参数、配置或 shell 历史。打包图形端通过管道委托独立 helper，CLI、Codex 取钥和卸载也使用同一 helper 身份，避免不同程序只能读钥、却无法更新的权限差异。首次访问或更换未签名版本后，macOS 可能请求允许本应用/取钥程序访问钥匙串；请核对名称和路径后操作。锁定的钥匙串需要先解锁。系统授权不能由本工具替你确认。

命令安装位置是 `~/.local/bin/codex-switch`。点击安装会写入标识明确的 PATH 片段到当前 zsh 的 `.zprofile` / `.zshrc`，或 bash 的 `.bash_profile` / `.bashrc`，保留其他内容。已有无关同名命令不会被覆盖；符号链接管理的 shell 配置也不会被自动替换。

如果需要手动安装或修复：

```bash
"/Applications/Codex Switch.app/Contents/Helpers/codex-switch" install-cli
# 不改 shell 配置，仅安装用户命令：
"/Applications/Codex Switch.app/Contents/Helpers/codex-switch" install-cli --no-shell
# 当前终端临时生效：
export PATH="$HOME/.local/bin:$PATH"
```

其他 shell 使用 `--no-shell` 后自行加入 `~/.local/bin`。安装后不要移动应用；移动应用或安装目录后重新安装终端命令，并在 Key 页留空保存以修复取钥路径。不能直接在 DMG 或 App Translocation 临时目录中配置 Key。

自定义配置目录：`codex-switch --codex-home "$HOME/my codex" setup --use`。也支持 `CODEX_HOME`。不同配置目录使用不同钥匙串条目；账号登录、模型与 MCP 配置保持原样。

## 卸载

先运行：

```bash
codex-switch uninstall --yes
# 没有安装终端命令时：
"/Applications/Codex Switch.app/Contents/Helpers/codex-switch" uninstall --yes
```

该操作清理本工具登记目录中的自建提供商和钥匙串条目，移除托管命令及 PATH 片段。正在使用自建 API 提供商的全局配置恢复为 `openai`，原有 Codex 登录、配置备份和外部提供商保留。清理失败时应先解决权限/配置问题，不要先删除应用。

完成后从菜单栏退出本工具，再把应用移到废纸篓。仅移除终端集成可使用 `codex-switch uninstall-cli`，不会删除 API 配置。

## 首次打开、签名与公证

没有 Apple Developer ID 凭据的构建使用 ad-hoc 签名，不等同于 Apple 公证。macOS 可能阻止首次打开；确认来自本仓库 Releases 并检查 SHA-256 后，按 Apple 官方的 [打开来源不明的 Mac App](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac) 流程操作。本项目不会关闭 Gatekeeper、移除下载隔离属性或自动确认系统提示。

构建支持可选 Developer ID 签名与 notarytool 公证。仓库未配置这些凭据时，不应将发布包描述为已公证。完整的签名、公证路径需要在配置凭据后单独验证。

## 开发、构建与发布

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python app_gui.py
# 本机登录钥匙串中仅使用隔离测试条目：
.venv/bin/python scripts/build_macos.py
# CI / 开发验证推荐：创建临时钥匙串并在结束后恢复原设置
.venv/bin/python scripts/macos_ci.py
```

CI 在 `macos-15`（arm64）与 `macos-15-intel`（x86_64）分别原生构建，检查签名完整性、冻结 QML、真实隔离钥匙串与 helper 取钥、挂载 DMG 后复制安装、zsh PATH、切换及卸载保留。不会使用有效 Key 或调用模型。macOS 14 是 Qt wheel 的最低系统要求，当前 CI 运行在 macOS 15；用户侧菜单栏与动画观感仍需 Mac 实机验收。

可选 GitHub Actions secrets：

| Secret | 内容 |
| --- | --- |
| `MACOS_CERTIFICATE_P12` | Developer ID Application 证书与私钥的 P12，Base64 编码 |
| `MACOS_CERTIFICATE_PASSWORD` | P12 密码 |
| `MACOS_NOTARY_KEY` | App Store Connect API 私钥 P8 文本 |
| `MACOS_NOTARY_KEY_ID` | API Key ID |
| `MACOS_NOTARY_ISSUER` | API Issuer ID |

仅配置证书可生成 Developer ID 签名包；证书与三项 notary 参数齐全时，会提交 DMG、公证并 staple / validate。签名私钥只进入 CI 临时钥匙串，完成后删除；应用不附带这些凭据。
