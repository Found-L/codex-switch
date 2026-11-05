## Codex Switch v0.2.0

- 重做为 Qt Quick 界面：常驻控件、异步保存、滑块与淡入淡出过渡，静默刷新不再闪动保存状态。
- 新增迷你窗口、Windows 系统托盘、托盘菜单切换与重复启动唤回。关闭窗口收进托盘，右键菜单可退出。
- 统一原创多尺寸图标、安装器和快捷方式的 Windows 应用标识。
- API Key 配置整合到同一面板，移除「初始模型」字段及 CLI `setup --model`；保留原模型配置，模型和推理档位在 Codex 中选择。
- 终端命令继续可用。界面运行库随包附带，无需安装 Python。

快捷键：Ctrl+M 收进托盘，Ctrl+Shift+M 切换小窗，Ctrl+Q 退出。托盘图标可能藏在 Windows 任务栏的隐藏图标中。

切换后请新建 Codex 会话，已有会话保留原来源。API 权限与额度以自己的 OpenAI 项目为准；不发送付费请求验证。

Persistent Qt Quick UI with animated transitions, asynchronous configuration changes, a mini window, native Windows tray switching and single-instance activation. New application icon throughout. API setup preserves model settings; choose models in Codex. Windows 10/11 x64.
