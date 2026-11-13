# Fast / Ultrafast 与桌面菜单

Ultra 是推理强度，Fast / Ultrafast 是速度档位，互相独立。

## 0.8.4：使用原生菜单（实验性）

「API 配置」页 →「API 速度 · Standard / Fast / Ultrafast」→「启用 Codex 的 Fast / Ultrafast」；也可从连接页右上角「Fast / Ultrafast」进入。点击后会等待您完全退出 Codex，再自动启动一次并加载速度模块，等待期间可取消。面板分别显示等待、启动、已加载、失败和已结束；目录已准备或普通启动不会被显示为已加载。目前仅适配 Windows Codex **26.1029.7803.0、26.1103.3517.0、26.1106.6628.0**、默认 `~/.codex`、已配置好的直连 OpenAI API。New API、自定义网关和 macOS 暂不支持这项原生适配。

Codex 升级到未适配的版本后，Switch 会拒绝原生适配；仅切到 API 或保存 Key 不会恢复速度菜单。0.8.3 补齐 26.1106.6628.0 的资源路径和固定哈希，并继续支持前两个版本。

账号模式完全使用 Codex 自己的速度菜单，Switch 不显示账号速度入口。先在 Switch 切到 API；模型目录有待应用的更改时先应用。原生启用入口会先恢复此前的备用转发为 OpenAI API 直连，然后安排启动。保存当前工作并完全退出 Codex，等待自动重开，再在 Codex 的模型菜单中选择速度。普通方式启动不会启用适配，Switch 会等待用户退出，最长一小时；切回账号或更换提供商会取消等待。适配通过只监听本机的调试端口在内存中调整客户端模块；不改写安装包、不伪装 ChatGPT 登录。每个相关资源均检查固定哈希，同时处理速度设置读取和会话提交中的 API 过滤。关闭 Codex 后内存适配结束；再次使用需从此入口启用。

启动会等待必需适配模块加载；这只证明模块接入，不证明前台菜单已显示、API Key 获得加价档位权限或上游按该档位计费。Ultrafast 限 gpt-6.1-sol / gpt-6-astra，gpt-6.1-terra 支持 Fast，但不能推断为支持 Ultrafast。

运行时本机其他程序可能访问调试端口并控制该 Codex 会话，只应在可信设备使用；关闭 Codex 会结束该调试会话。

模型目录单独保存并可撤销。Fast 对应 priority，Ultrafast 仅为 gpt-6.1-sol / gpt-6-astra 添加；其他已确认支持 Fast 的模型只添加 Fast。未知模型不添加档位，原有目录声明保留。仍沿用 Codex 的模型选择、工作区限制及请求实现；服务端对 Key、模型、地区和项目的实际授权不变。不会自动选择加价档位。

退出 Codex 后，在 Switch 点「撤销原生适配」，可恢复先前目录，再正常打开 Codex。原生适配与备用转发互斥。更新模型目录会替换原生目录，下次需重新从原生入口启动；新版本客户端若未适配会拒绝启动适配。账号模式可正常切回，并恢复其模型设置。

```text
codex-switch native inspect    # 只读检查本机版本和资源签名
codex-switch native launch     # 安排启用；等待 Codex 退出后自动启动
codex-switch native cancel     # 取消等待，不关闭正在运行的会话
codex-switch native status     # 历史运行记录，不是实时菜单或计费证明
codex-switch native off        # 完全退出 Codex 后恢复目录
```

验证范围：已执行 26.1103.3517.0 安装包中提取的菜单、请求和会话设置代码片段，覆盖 API/账号、工作区限制及不同速度档位；新版安装的 Codex 后端也已向本地模拟接口验证 Standard、Fast（priority）、Ultrafast（ultrafast）。隔离数据目录下的真实 Codex 桌面进程已完成页面加载，并观察到四类目标模块均被接入。正式启动入口和真实前台菜单仍待验收，因此入口保留「实验性」标识。

2026-11-07 在本机已配置的 OpenAI API 上，另做了两次真实、计费的短测试：直接请求 `gpt-6.1-sol` 的 `ultrafast` 得到 `ultrafast` 响应，使用 9 个输入 token、5 个输出 token；隔离的已安装 Codex 后端使用当前 API 模型目录，发出的请求档位及服务端实际档位也均为 `ultrafast`，使用 15,143 个输入 token、5 个输出 token。第二次通过临时本机代理观察档位，并将最大输出限制为 48 token；模型、输入、工具和档位没有改写。测试不证明其他 Key 的权限，也不证明当前桌面窗口已开启适配或已显示菜单；实际费用以服务端账单为准。

## 原生入口的限制与备用转发

OpenAI API 支持某个速度档位，并不代表 Codex 桌面端会显示对应入口。2026-11-05 检查的 Windows Codex 26.1029.7803.0 桌面端，在速度权限检查中仅允许 ChatGPT、personal access token 和 Amazon Bedrock 登录方式；API Key 登录返回空速度权限，菜单因而隐藏。模型目录已声明 Fast 时也受此限制。添加 `features.fast_mode=true` 无法绕过客户端的登录方式判断，未配置此开关也不能被诊断为唯一原因。其他客户端或后续版本需要重新核实。

备用本机转发仅保留在命令行，普通界面的三个转发按钮已移除。它会将提供商改为 `codex_switch_speed`；原有 `openai_api` 会话会因此出现「模型提供商不匹配」，必须使用新建的转发会话。原生启用入口会恢复直连并保留原有 OpenAI API 提供商。备用转发目前仅支持直连 OpenAI API；New API、自定义网关暂不启用。账号模式仍使用 Codex 原生菜单。

首次通过命令行选择 Standard / Fast / Ultrafast 会添加独立的本机连接，需完全退出并重启 Codex，再新建 API 会话。之后通过命令行切速会影响这条连接的后续请求，无须每次重启。执行 `codex-switch speed off` 后也需重启加载直连配置。已有直连会话不会自动改走转发。

终端支持 `codex-switch speed default`、`codex-switch speed fast`、`codex-switch speed ultrafast` 和 `codex-switch speed off`。Fast / Ultrafast 费用更高，默认关闭；不支持的模型会被拒绝，不会自动降档或重试。Ultrafast 目前限 gpt-6.1-sol / gpt-6-astra；Fast 也按已确认的模型列表限制。

本机转发监听 127.0.0.1，仅接收带独立本机凭据的 Responses HTTP 请求。上游 Key 从系统凭据库或原有配置读取，不写入新转发配置，也不作为本机凭据交给 Codex。提示词和回答会在内存中转发，不保存到磁盘；实际请求仍按原 API 连接的网络代理设置发送给 OpenAI。转发不支持 WebSocket，不能承诺获得 WebSocket 的延迟收益。compact 请求原样转发，不添加其协议未声明的速度字段。

早期缺少模型档位声明的测试中，客户端的 `serviceTier: null` 导致配置速度没有传到请求。补齐目录后，本机后端已能原生传递 priority / ultrafast；不能据早期现象判断后端不支持 Ultrafast。备用转发会对 Responses 请求明确写入 `service_tier`：Standard 对应 default，Fast 对应 fast，Ultrafast 对应 ultrafast。已用安装的 Codex 后端 → 本机转发 → 本地模拟上游验证三个值，不调用付费接口。

`codex-switch status --json` 的 `speed_observed` 只记录服务端报告的档位、模型和时间。它不证明前台会话身份；实际处理可能受上游权限、区域和限额影响，以响应与账单为准。`doctor` / `status --json` 同时保留配置诊断。上述真实 OpenAI 计费验证使用隔离的临时代理，不代表备用转发已在真实桌面验收；macOS 转发运行链路尚未在本机验收。

切换账号/API 时分别保留速度配置。没有自定义目录的直连 API，保存已明确选择的档位，并仅在模型匹配且档位已确认受支持时恢复；账号原有速度配置在切回时还原。自定义 API 目录下，只有已明确选择且目录声明的档位才恢复（`fast` 与 `priority` 视为别名）；不把账号的付费速度偏好自动带入 API，不自动开启加价档位。更换端点或 Key 会清理旧 API 的速度偏好。功能开关保持原样。已打开聊天的速度可能由会话自身覆盖，配置并不证明实际档位。

网关还需要正确转发 `service_tier`，上游模型、项目权限和区域需要支持。目录元数据不能证明这些条件成立。不要为显示按钮而修改 Codex 程序包或伪装账号认证方式。

单独改配置无法恢复上述版本的 API 菜单；0.8.1 提供实验性运行时适配。本机转发继续作为可选备用入口。账号模式仍受模型、套餐和工作区权限限制。

官方参考：

- [Codex 速度设置](https://learn.chatgpt.com/docs/agent-configuration/speed)
- [API Fast mode](https://developers.openai.com/api/docs/guides/priority-processing)
- [API Ultrafast](https://developers.openai.com/api/docs/guides/ultrafast-mode)

## 原生菜单与社区实现的区别

2026-11-05 补充核查：不能把「本机版本不能通过配置恢复菜单」扩大为「客户端界面无法实现」。社区已有显示原生速度入口的实现，但应区分以下路径：

- [codexfast-windows 的功能说明](https://github.com/Kiana-ZY/codexfast-windows/blob/main/docs/feature-scope.md)：通过启动时的 CDP 运行时补丁暴露原有速度菜单，并修补速度参数的请求路径；文档明确说明不修改磁盘上的 app.asar。这是非官方兼容性改造，其 Fast 支持不等于当前版本的 Ultrafast 已验证。
- [codex-desktop-linux 的 API Key Service Tier](https://github.com/ilysenko/codex-desktop-linux/blob/main/linux-features/api-key-service-tier/README.md)：给 API Key 主机提供 Fast 控件；其说明明确保持合成的 Ultrafast 权限关闭，不能据此宣称 Windows 的三档菜单已经可用。
- [CC Switch issue 3034](https://github.com/farion1231/cc-switch/issues/3034)：讨论保留 ChatGPT 登录、将自定义提供商凭据与账号凭据分离，避免破坏依赖登录状态的桌面功能。这是特定版本的社区记录，不能单独证明本机三档入口生效。Codex Switch 本身已保留用户 auth.json，不能直接归因为切换器覆盖账号登录。

原生入口应按当前模型声明的档位、提供商能力、Key/项目权限及客户端能力共同决定；不能给全部模型强行添加三个档位。社区实现未在本机执行。Switch 的适配独立实现，只针对上述版本和范围；模块验证与后端模拟请求通过不等于真实桌面验收通过。
