## Codex Switch v0.5.0

- 模型页改为有界的搜索、多选列表，支持「编程候选 / 已选择 / 全部」、默认模型和一次应用，移除原来的长下拉框。
- 明显的音频、绘图、嵌入等非编程模型默认过滤，界面和后端均禁止加入；未知别名保留在「全部」。分类仅为浏览提示，不表示已验证兼容。
- 官方 OpenAI API 自动尝试读取同一 Key、对应 Codex 版本的官方模型目录，仅精确匹配可见且支持 API 的条目，保留原生指令、工具及参数；绝不把网关 Key 发往 OpenAI。
- 区分「官方参数 · 未实测」「基础模板 · 未验证」和手动覆盖。普通选择无需填写能力参数；高级参数移至模型行 `···`，支持恢复默认。
- 增加 CLI `models apply --select 模型1 模型2 --default 模型1 --use`；批量选择失败整体回滚，不提前保存半成品。

Searchable multi-select model picker, non-coding filters, exact authenticated official OpenAI metadata and advanced-only capability overrides. No model inference is performed. Custom gateways use clearly labeled unverified basic templates. Reload Codex after applying.

## Codex Switch v0.4.1

- 修复已有 `openai_api` 显示连接可用、点击同步却要求重新保存 Key 的问题。指向 OpenAI 官方的旧版连接可直接沿用已有 command/env/token 认证，同步不会复制密钥或重写提供商配置。
- 旧版提供商也支持应用/撤销模型目录与账号设置恢复；卸载时保留原提供商及其凭据。
- 空模型页新增连接/同步引导，隐藏空选择框与保存/应用按钮；中文界面补齐同步相关错误翻译。
- 修复底部错误提示压住应用按钮的问题，冻结 GUI 自检增加空列表和提示布局检查。

Fix legacy OpenAI API discovery without re-entering credentials, empty-state guidance, Chinese error messages and overlapping notices. No model inference is performed during discovery.

## Codex Switch v0.4.0

- API 配置支持自定义 HTTPS Base URL，可接 New API、多供应商网关和 DeepSeek 等兼容 Responses 的接口。
- 新增「模型」页：同步名单、逐模型启用与能力设置、默认模型、应用目录及撤销；CLI 同步支持 `models sync/list/configure/apply/reset`。
- 同步只 GET 模型名单，不发送推理请求；新模型默认关闭，所有网关模型均标明兼容性未验证。通用目录不开放 Fast / Ultrafast / Ultra，不从别名猜厂商或能力。
- API 目录与账号模型设置隔离，切回账号恢复原模型、目录、速度、推理及上下文；MCP、插件和账号登录保留。
- 地址变更要求重新输入对应 Key，Key 变更清除旧名单；模型查询拒绝重定向、保留 TLS 校验与响应大小限制。
- 模型目录在本机 Codex `0.166.0-alpha.6` app-server 完成实际读取验证，无模型调用。首次应用和更新目录后请重载 Codex 刷新菜单。

Windows/macOS custom API endpoints and opt-in gateway model catalogs. Discovery is GET-only, capability metadata is user-configured, inference compatibility is untested, and account settings restore when switching back. Reload Codex for catalog changes. Mac builds without Developer ID credentials remain ad-hoc signed, not notarized.

完整说明：[New API 与模型同步](https://github.com/Found-L/codex-switch/blob/main/docs/gateways.md)。

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
