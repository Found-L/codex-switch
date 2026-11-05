# Codex Switch

[English](README.en.md) · 简体中文

Windows / macOS 上的 Codex 账号 / OpenAI API 切换工具。首次配置 Key，之后从窗口或终端切换。保留原有账号登录，无需手工编辑配置文件。

**[下载安装包 / 便携版](https://github.com/Found-L/codex-switch/releases/latest)** · [问题反馈](https://github.com/Found-L/codex-switch/issues)

![Codex Switch 连接总览](docs/images/overview.png)

## 新电脑开始使用

1. 安装 [Codex](https://learn.chatgpt.com/docs/quickstart)。使用账号额度前，先在 Codex 中登录自己的账号。
2. Windows 下载 `windows-x64-setup.exe`；Mac 下载对应芯片的 `macos-arm64.dmg`（M 系列）或 `macos-x64.dmg`（Intel），将 App 拖入 Applications 后打开。支持 Windows 10/11 x64、macOS 14+，无需 Python。
3. 打开 **Codex Switch**，按首次引导创建并输入自己的 [OpenAI API Key](https://platform.openai.com/api-keys)，选择「保存并使用 API」。模型和推理档位在 Codex 中选择，本工具保留模型配置。
4. 在 Codex 中新建会话。以后点击连接卡片即可切回账号或 API。

Key 仅保存在这台电脑、当前用户的 Windows 凭据管理器或 macOS 登录钥匙串中。换电脑后重新输入自己的 Key，不需要复制旧电脑的登录文件。账号额度和 API 分开计费。

窗口支持中文 / English，另有终端命令速查。安装器默认创建桌面入口并加入当前用户 PATH；可在安装时取消。已打开的终端需要重新打开后才能使用新 PATH。

Mac 的完整安装、菜单栏、终端命令、卸载与签名说明见 **[macOS 使用指南](docs/macos.md)**。Mac 在「终端」页点击「安装 / 修复终端命令」后，重新打开终端即可使用。当前无 Developer ID 凭据的 Mac 构建为 ad-hoc 签名，未经过 Apple 公证；首次打开需按指南确认系统提示。

## 窗口与托盘

新版使用 Qt Quick 常驻界面：切换只更新状态，选择滑块和页面淡入淡出，不重新创建窗口。右上角小窗按钮可切换到 **372 × 302** 的迷你窗口；关闭按钮或最小化会收进 Windows 通知区域；Mac 收进屏幕顶部菜单栏。托盘图标可能位于任务栏的「显示隐藏的图标」中，可拖到常显区域。

点击托盘图标打开/收起面板，右键可直接切账号/API、配置 Key 或退出。从托盘打开的面板会在点击别处时收起；从桌面打开的窗口保持显示。重复打开同一配置目录会唤回原窗口。

窗口内快捷键：`Ctrl+M` 收进托盘，`Ctrl+Shift+M` 切换迷你窗口，`Ctrl+Q` 退出。Mac 使用相同的 ⌘M、⇧⌘M、⌘Q 快捷键。无需为切换发送聊天消息。

![迷你窗口](docs/images/mini.png)

截图由真实 QML 界面在隔离配置下离屏渲染。

## 命令行

```powershell
codex-switch setup --use       # 隐藏输入 Key，保存并切到 API
codex-switch status            # 查看当前配置来源
codex-switch use api           # 切到 API
codex-switch use account       # 切到账号
codex-switch doctor --json     # 本地诊断，不输出 Key
codex-switch gui               # 打开界面
```

Windows 的 PowerShell、CMD、Git Bash，以及 Mac 的 zsh/bash 都可以运行这些命令。Windows 安装后需彻底重开原终端软件以刷新 PATH，只新增标签页可能无效。

支持短命令 `codex-switch api` / `codex-switch account`。不要把 Key 作为命令参数或直接写进命令历史。自动化场景可将秘密通过 stdin 传入 `setup --key-stdin --use`；工具没有 `--key 明文` 参数。

默认使用 `CODEX_HOME`，未设置时为 `~/.codex`。自定义目录放在子命令前：

```powershell
codex-switch --codex-home D:\my-codex status
codex-switch --codex-home D:\my-codex setup --use
```

不同配置目录使用不同的系统凭据条目。便携版解压后直接运行 `CodexSwitch.exe`，或在所在目录使用 `.\codex-switch.exe`。**配置后不要移动便携版目录**；如移动，请重新打开 API 配置并保存，以修复取钥程序路径。希望长期使用终端命令时推荐安装版。

## 配置保留与兼容范围

- 切换只修改全局 `config.toml` 的顶层 `model_provider`；已有模型、速度、推理设置、MCP、插件和 `auth.json` 保持不变。
- 首次配置新增独立的 `model_providers.codex_switch_api` 及命令取钥配置。Key 不写入 TOML、日志或备份；如果原配置本来包含其他明文秘密，原配置备份依然属于敏感文件，请留在本机。
- 每次实际修改前，在 `CODEX_HOME/codex-switch/backups` 保存原配置。无变化的切换不重复改写。
- 可沿用先前已配置、指向 OpenAI 官方 API 的 `openai_api` 提供商，不迁移其 Key，也不覆盖它。未知的其他提供商不会被强行替换。
- 不修改模型目录，不伪造模型或模式的可用性。Key 是否有效、项目是否有额度、模型和模式是否支持，以 OpenAI 账户权限及实际请求结果为准。配置完成不代表已经发送请求验证。
- 窗口显示的是**全局配置来源**。已有会话保留原来源；桌面预热会话、模型菜单缓存、项目级配置、CLI `--profile` / `-c` 等覆盖可能影响实际运行来源。必要时重载客户端以刷新菜单。本工具不会重启 Codex。
- 根配置选中的 Profile 如果设置了 `model_provider`，工具会阻止误导性的全局切换，需先处理该覆盖。
- 需要支持官方 [command-backed authentication](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers) 的 Codex 版本。本机兼容基线为 CLI `0.166.0-alpha.6`；不承诺旧版客户端支持。发行包覆盖 Windows 10/11 x64、macOS 14+ Apple Silicon 与 Intel；不支持 Linux，Windows ARM 未验证。

切换和本地诊断不调用模型、不查询网络，不消耗模型 token。工具不附带 Codex 或任何 API Key。它是独立社区工具，与 OpenAI 无隶属关系。

## 卸载

Mac 卸载前先运行 `codex-switch uninstall --yes`，再从菜单栏退出并删除 App；详见 [macOS 使用指南](docs/macos.md#卸载)。

在 Windows 设置中卸载 **Codex Switch**。卸载前会对本工具登记的配置目录移除自建提供商及对应凭据，正在使用自建 API 提供商的全局配置恢复为 `openai`；原 Codex 账号登录和配置备份保留。已有外部 `openai_api` 不由本工具删除。

如目录已迁移、权限变化或配置损坏，安全清理可能阻止卸载；先修复配置或对相应目录运行 `codex-switch --codex-home 目录 remove-api --yes` 后再卸载。便携版删除前也应先运行 `remove-api --yes`，避免保留指向已删除程序的取钥配置。

## 开发与构建

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-build.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python app_gui.py
.\scripts\build.ps1 -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

构建需要 Python 3.14 x64 和 Inno Setup 6/7。`build.ps1 -SkipInstaller` 仅生成便携版。推送 `v*` 标签会在 GitHub Actions 上测试、构建并发布安装包、便携包和 `SHA256SUMS.txt`。当前版本没有购买代码签名证书，可用发布附件中的 SHA-256 检查下载完整性。

macOS 原生构建：`.venv/bin/python scripts/macos_ci.py`，使用临时钥匙串完成构建和安装/卸载验证。可选 Developer ID / 公证 secrets 见 macOS 指南。

测试覆盖格式/编码保留、真实系统凭据读写（隔离测试条目）、失败回滚、并发修改检测、旧提供商兼容和卸载清理；测试不连接真实数据库或发送模型请求。图形界面与打包验收结果见 [验证记录](docs/validation.md)。

## 许可

[MIT](LICENSE)。第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
