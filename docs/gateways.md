# New API 与自定义 API

v0.4.0 起支持配置 HTTPS Base URL 和对应 Key，适用于 New API、DeepSeek 等兼容 Responses 的接口。HTTP 仅允许本机 loopback。工具保存一个 API 连接；多个供应商由 New API 聚合，用模型 ID 路由，不需要为每家切 Key。

v0.4.1 起，已有指向 OpenAI 官方的 `openai_api` 连接也能直接同步和应用目录，无需重新输入 Key。沿用原来唯一的 command/env/token 认证，不复制密钥、不改写原提供商；取钥程序失败或认证方式冲突时给出明确提示。仅有账号登录时不能查询 API 模型，需配置 API 连接。

## 窗口操作

1. 「API 配置」填写 Base URL 和该地址的 Key，例如 `https://你的网关/v1`。DeepSeek 官方地址按其文档填写 `https://api.deepseek.com`。地址不包含 `/responses` 或 `/models` 后缀。
2. 保存后进入「模型」，点击「从 API 同步模型」。只发送携带该 Key 的 `GET {base_url}/models`，不发送编程内容，不执行推理。
3. 逐个选择要使用的编程模型，勾选「将此模型加入 Codex 菜单」。展开能力设置，按真实模型及渠道设置上下文、推理档位、图片能力，然后保存此模型。
4. 选中希望默认使用的**已保存启用**模型，点击「以当前模型为默认并应用」。可以同时启用多家供应商的模型。
5. 重载 Codex 刷新目录，再新建会话。已有聊天保留原连接；项目配置、外部 `--profile` / `-c`、管理员策略仍可能覆盖全局配置。工具不会重启 Codex。

新同步到的模型默认关闭；同一 ID 的已保存设置在刷新时保留，网关不再返回的 ID 会从待应用列表移除。同步或修改后需重新应用，现有目录不会被半完成的编辑替换。同步失败保留原名单和目录。发现变更后会显示「待应用」，应用后才允许再次切到该 API。

`/v1/models` 是网关公布的名单，不是逐模型可用性验证。New API 的实际名单可能受版本和管理员设置影响；后端必须在推理时继续校验分组、令牌限制、额度和渠道。模型存在不能证明其 Responses、流式工具调用和多轮能力完整可用，也不能证明别名后面一定是某个厂商。不要把 DeepSeek 重命名成 GPT 来冒充模型。

## 能力信息与限制

普通 OpenAI 格式名单不包含完整 Codex 能力元数据，本工具不会从模型名字或 `owned_by` 猜测。默认模板为保守的 32K 上下文、仅文本、无推理档位；这些是待用户确认的配置值，不是探测结果。上下文可能需要根据真实模型调低或调高。推理档位留空时不写全局 `model_reasoning_effort`，可填写渠道明确支持的 `none,minimal,low,medium,high,xhigh,max` 子集（首个为默认）。

生成目录使用通用编程指令和标准函数工具，不复制某个 GPT 模型的专用指令，也不宣称已经验证第三方模型的编程效果。自定义目录暂不开放 Fast / Ultrafast / Ultra、多代理专属配置和服务端工具，不自动导入上游私有能力。需要这些能力时，应使用服务商提供并针对该 Codex 版本验证过的完整目录；本版尚无完整目录导入功能。

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
codex-switch models configure deepseek-flash --context 65536 --reasoning low,high
codex-switch models configure 另一个模型ID --context 32768
codex-switch models apply --default deepseek-flash --use
codex-switch use account
codex-switch use api
codex-switch models reset
```

上下文和推理参数仅为命令示例，请按实际渠道能力填写。Key 通过隐藏输入或既有 `--key-stdin` 管道输入，不放在命令参数里。同步和设置不发起推理；真实使用时按实际供应商和网关计费。

官方参考：[Codex 模型目录](https://learn.chatgpt.com/docs/model-catalogs)、[New API 模型列表](https://docs.newapi.pro/zh/docs/api/ai-model/models/list/listmodels)、[DeepSeek Responses](https://api-docs.deepseek.com/guides/responses_api/)。
