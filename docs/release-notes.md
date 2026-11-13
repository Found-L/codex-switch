## Codex Switch v0.8.4

- 修复普通速度按钮启用备用转发后，提供商变为 `codex_switch_speed`、已有 OpenAI API 会话报「模型提供商不匹配」的问题。普通界面移除转发选速按钮，原生启用保留原有 API 提供商。
- 原生启用支持等待 Codex 完全退出后自动启动一次，可取消等待；切换账号或提供商后取消待执行的启动。
- 显示等待、启动、模块已加载和失败等实际状态。后台适配进程结束后，旧记录不再显示为已加载；模块未完整加载会报告失败。
- 优化原生资源检查，保留全部固定哈希校验，减少启用前的等待。
- 隔离的真实 Codex 26.1106.6628.0 进程已观察到四类模块实际被拦截，未发送付费请求；现有用户窗口的菜单显示仍需启用后确认。

Preserve the existing API provider, remove confusing relay speed buttons, and queue native activation until Codex exits. Show live adapter process state and stop treating old records as loaded modules.

## Codex Switch v0.8.3

- 补齐 Windows Codex 26.1106.6628.0 的 API 原生速度适配，核对 16 个相关资源的固定哈希；保留此前两个版本的兼容性。
- 「API 配置」页新增明确的「API 速度 · Standard / Fast / Ultrafast」入口，连接页入口也直接显示 Fast / Ultrafast。
- 原生速度仍需先完全退出 Codex，再通过 Switch 的原生速度按钮启动；普通启动不会启用内存适配。账号速度继续由 Codex 管理。

Support the pinned Windows Codex 26.1106.6628.0 resources and make API speed controls accessible from the API configuration page. Native menu visibility requires launching Codex through the adapter.

## Codex Switch v0.8.2

- 账号模式不显示 Switch 速度入口，继续由 Codex 原生界面管理账号速度；API 模式提供原生速度启动入口。
- 原生启动等待所有必需模块加载完成，连接窗口后发生的加载错误不再被当作成功；模块加载成功仍不代表菜单和实际 API 权限已验证。
- 修复直连 API 未配置模型目录时，账号与 API 的速度设置互相串用；显式设置的 API 档位只在模型支持且匹配时恢复。切回账号恢复原有值，不自动启用加价档位。
- 明确提示需先完全退出 Codex，再从 Switch 启动原生 API 速度适配；选择速度仍在 Codex 模型菜单中完成。

Keep account speed in Codex, isolate account/API tiers without a catalog, and wait for native adapter modules before reporting startup. A live menu and paid API entitlement remain unverified.

## Codex Switch v0.8.1

- 实验性原生速度菜单适配 Windows Codex 26.1103.3517.0，补齐 API 速度读取及会话提交检查；新版相关客户端资源均核对固定哈希。
- 重载桌面时忽略无关网络通知，避免适配器事件队列溢出。模型档位、工作区限制和服务端授权继续各自生效。
- 等待 Codex 首次页面加载完成后再重载并启用适配，避免打断桌面启动；已在隔离的 Codex 进程验证四个目标模块均被接入。
- 在完整和迷你面板的标题旁显示当前版本号，便于确认安装是否成功。
- 速度设置面板直接显示启动失败和操作结果，避免提示被面板遮住。
- 通过隔离单元测试、安装包模块模拟与本机后端的 Standard / Fast / Ultrafast 请求检查；未调用付费 API。真实桌面菜单和实际计费仍待用户重启后验收。

Add experimental native speed support for the verified Windows Codex build, including its session tier checks. Local fixture tests pass; live desktop and billing remain unverified.

## Codex Switch v0.6.0

- 模型页新增「状态对照」，分别显示全局配置、已保存目录、编辑草稿及独立的运行检查；明确配置差异不等于正在运行的会话异常。
- 草稿默认值与配置模型分离，模型行标记已保存/配置项；可一键把配置模型加入草稿，保存前不写配置。账号模式下仍可查看已保存的 API 目录。
- 「目录所选」改为「草稿所选」，空搜索显示实际勾选数量并提供清除入口；保存按钮明确会写入目录并切到 API。
- 新增连接页只读检查与 `codex-switch runtime`：仅代理连接现有本机进程，读取模型 ID 与已加载会话数量；不可接入时显示未知。不会新建 app-server、启动推理或根据配置推断前台会话/计费连接。
- 改善冻结 GUI 失败诊断，报告出错阶段；54 项测试与源码 QML 自检通过。

Separate configuration, saved catalogs, drafts and optional existing-server snapshots. No foreground chat model or billing route is inferred. No model inference is performed.

## Codex Switch v0.5.1

- 修复远端 Codex 元数据缺项时，当前客户端自带模型从候选列表消失的问题。仅对官方 OpenAI 地址，将当前 Key 名单与已安装 Codex 的可见内置条目精确匹配；保留原生指令和参数，并区分远端、内置与基础模板来源。
- 将「已选择」改为「目录所选」，明确它是启动时替换的目录，不是当前桌面菜单。写入成功不再显示为已生效，明确要求完全退出并重启 Codex。
- 检测当前配置模型不在保存目录内的情况，持续显示不一致提示；不会自动选择模型、重启 Codex 或修改账号登录。
- 50 项回归测试通过；隔离 app-server 读取当前 9 个可见内置条目及用户保存的单模型目录成功，无模型推理请求。桌面重启后的菜单仍需用户验收，工具不会把隔离验证冒充运行中桌面验证。

Fix missing built-in model candidates and misleading catalog activation claims. Fully quit and restart Codex after saving. API access and inference remain untested.

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
