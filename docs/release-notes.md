Codex Switch 首个 Windows 10/11 x64 版本：

- 中文 / English 图形界面，首次引导配置 API Key。
- 账号 / OpenAI API 切换，保留现有 Codex 账号登录。
- Windows 凭据管理器存储 Key，不写入配置文件。
- `codex-switch setup/status/use/doctor/gui` 终端命令。
- 当前用户安装器、可选 PATH 和桌面入口；另附便携 ZIP。
- 修改前备份配置，卸载时安全移除本工具的提供商和凭据。

首次使用请先安装 Codex，账号模式需先登录。窗口表示全局配置来源；切换后新建会话，已有聊天保持原来源，缓存菜单必要时重载客户端。实际模型权限与计费以 OpenAI 账户为准。

Download the **setup.exe** for installation, or the **portable.zip** for portable use. No Python installation is needed. Binaries are unsigned; checksums are included. The tool performs local setup only and does not verify access by sending paid model requests.
