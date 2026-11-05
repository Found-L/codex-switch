## Codex Switch v0.2.1

- 页面切换改为先淡出再淡入，消除 Key、连接与终端页面在过渡中叠字的问题。
- 中文界面明确使用微软雅黑字体，修复标题意外回退到宋体。
- 去除越过圆角的装饰背景，保持四角形状一致。
- 增加过渡采样自检：切换期间最多只显示一个页面，并确认目标页面可见。

保留 v0.2.0 的迷你窗口、托盘切换、单实例唤回和终端命令。模型与推理档位仍在 Codex 中选择。切换后请新建 Codex 会话。

Page transitions now fade out before fading in, preventing overlapping text. Consistent Chinese sans-serif fonts and rounded corners. Adds transition visibility checks. Windows 10/11 x64.
