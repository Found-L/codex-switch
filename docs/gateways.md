# New API 与自定义 API

v0.4.0 起支持配置 HTTPS Base URL 和对应 Key，适用于 New API、DeepSeek 等兼容 Responses 的接口。HTTP 仅允许本机 loopback。工具保存一个 API 连接；多个供应商由 New API 聚合，用模型 ID 路由，不需要为每家切 Key。

v0.4.1 起，已有指向 OpenAI 官方的 `openai_api` 连接也能直接同步和应用目录，无需重新输入 Key。沿用原来唯一的 command/env/token 认证，不复制密钥、不改写原提供商；取钥程序失败或认证方式冲突时给出明确提示。仅有账号登录时不能查询 API 模型，需配置 API 连接。

## 窗口操作

1. 「API 配置」填写 Base URL 和该地址的 Key，例如 `https://你的网关/v1`。DeepSeek 官方地址按其文档填写 `https://api.deepseek.com`。地址不包含 `/responses` 或 `/models` 后缀。
2. 保存后进入「模型」，点击「同步」。获取 `GET {base_url}/models`；如果是官方 OpenAI 地址，还会尝试查询带客户端版本的官方 Codex 参数目录。不发送编程内容、不执行推理，网关 Key 不会发送到 OpenAI。
3. 使用搜索和「编程候选 / 草稿所选 / 全部」筛选，直接勾选多个模型。明显的音频、图像、嵌入等非编程模型默认隐藏，在「全部」中也不能勾选。名字分类只是浏览提示，不能证明接口兼容。
4. 点模型行的「设默认」，再点击「保存草稿」。选择草稿不会提前修改配置，也不需要逐个保存。已有官方参数的模型自动保留其指令、工具、上下文与档位；未知条目显示「基础模板 · 未验证」。
5. 完全退出并重启 Codex 刷新目录，再新建会话。已有聊天保留原连接；项目配置、外部 `--profile` / `-c`、管理员策略仍可能覆盖全局配置。工具不会重启 Codex。

「草稿所选」指正在编辑的替换目录草稿，保存后在下次启动加载，不是运行中的 Codex 菜单。完全退出桌面进程再启动，仅新建聊天或关闭窗口可能不会重建目录。保存成功只证明配置写入，工具不宣称已验证运行中桌面加载；配置模型不在保存目录内时会提示差异，但不据此判断运行会话异常。点「状态对照」查看全局配置、已保存目录、草稿和只读运行检查；「加入草稿」不会提前写配置。

新同步到的模型默认关闭；同一 ID 的手动覆盖在刷新时保留，网关不再返回的 ID 会从待应用列表移除。同步或修改后需重新应用，现有目录不会被半完成的编辑替换。模型名单查询失败保留原名单和目录；官方参数查询失败仍保留名单，但明确回退为基础模板。同步发现变更后需应用，才允许再次切到该 API。

`/v1/models` 是网关公布的名单，不是逐模型可用性验证。New API 的实际名单可能受版本和管理员设置影响；后端必须在推理时继续校验分组、令牌限制、额度和渠道。模型存在不能证明其 Responses、流式工具调用和多轮能力完整可用，也不能证明别名后面一定是某个厂商。不要把 DeepSeek 重命名成 GPT 来冒充模型。

## 能力信息与限制

普通 OpenAI 格式名单不包含完整 Codex 能力元数据，本工具不会从模型名字或 `owned_by` 猜测上下文或推理能力。官方 OpenAI 地址会使用该 Key 查询 `https://chatgpt.com/backend-api/codex/models?client_version=版本`，仅将官方目录中 `supported_in_api=true` 且可见的条目与当前 API 名单按精确 ID 匹配。匹配结果显示「远端参数 · 未实测」，并优先展示；非匹配别名仍可在「全部」中查看。

官方地址还会在隔离的空配置目录中执行已安装客户端的 `codex debug models --bundled`，补齐远端缺少但当前 API 名单中存在的内置模型，并显示「Codex 内置参数 · API 未验证」。不会读取账号缓存或把这些条目自动勾选，也不会将 OpenAI 内置参数套到网关同名模型。

「远端参数」与「Codex 内置参数」是配置来源，不能证明已经调用成功。只同步目录，不探测模型推理或工具效果。无法匹配的模型使用保守的 32K、仅文本、无推理档位基础模板；这些不是探测结果。New API 别名不会冒用同名 OpenAI 模型的能力元数据。

模型行的 `···` 打开高级参数。仅在确认实际渠道能力后手动覆盖，支持恢复来源默认。上下文是客户端预算，不会扩展服务端上限；图片开关不会赋予模型视觉能力；推理参数须由真实接口支持。留空推理档位时不写全局 `model_reasoning_effort`；可填写 `none,minimal,low,medium,high,xhigh,max` 的受支持子集。对官方模型手动覆盖这些字段时，保留官方指令和工具配置。

基础模板使用通用编程指令和标准函数工具，速度档位和专属模式保持关闭。官方精确匹配条目保留对应版本的官方目录配置，包括其公开档位；实际模式权限、服务等级和计费仍由后端决定。本版尚不支持自定义网关的完整目录导入，也没有逐模型真实推理验证。

目录格式参考 Codex `rust-v0.162.1` 的 `ModelsResponse`，在本机 `0.166.0-alpha.6` 的 app-server `model/list` 验证了多模型、推理档位和空速度档位。其他版本需要单独验证。账户默认目录和未启用自定义目录的官方 OpenAI API 流程维持原行为。

## 账号隔离与撤销

应用 API 目录时暂存账号原有的模型、目录路径、速度、推理、摘要、verbosity 和上下文配置；切回账号或移除 API 时恢复。MCP、插件和 `auth.json` 不修改。未知的外部目录修改会触发保护，工具不会强行覆盖。

「撤销自定义目录」或 `models reset` 会保留 API 地址和系统凭据；自定义接口恢复到账号配置，需重新同步应用后再切 API。官方 OpenAI 地址则可以继续使用默认目录。

更换 API 地址必须重新输入对应 Key，工具不会把上个地址的 Key 自动发往新地址。更换 Key 会清除旧名单和目录，以免沿用旧令牌的权限。HTTPS 证书正常校验；模型查询拒绝重定向、设置超时和 1 MiB 响应上限，错误信息不回显服务器正文。Key 仍只保存在系统凭据库。

## 终端（PowerShell / CMD / Git Bash / macOS zsh/bash）

```text
codex-switch setup --base-url https://你的网关/v1
codex-switch models sync
codex-switch models list
codex-switch models apply --select 模型ID1 模型ID2 --default 模型ID1 --use
# 以下为高级手动覆盖示例，普通选择无需填写参数
codex-switch models configure deepseek-flash --context 65536 --reasoning low,high
codex-switch models configure 另一个模型ID --context 32768
codex-switch models apply --default deepseek-flash --use
codex-switch use account
codex-switch use api
codex-switch models reset
```

上下文和推理参数仅为命令示例，请按实际渠道能力填写。Key 通过隐藏输入或既有 `--key-stdin` 管道输入，不放在命令参数里。同步和设置不发起推理；真实使用时按实际供应商和网关计费。

官方参考：[Codex 模型目录](https://learn.chatgpt.com/docs/model-catalogs)、[New API 模型列表](https://docs.newapi.pro/zh/docs/api/ai-model/models/list/listmodels)、[DeepSeek Responses](https://api-docs.deepseek.com/guides/responses_api/)。
