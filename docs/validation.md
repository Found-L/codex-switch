# v0.3.0 验证范围

流水线：[Desktop builds](https://github.com/Found-L/codex-switch/actions/workflows/release.yml)。发布任务依赖 Windows、macOS arm64 和 macOS x86_64 三个构建全部成功。

## 通用与 Windows

- 28 项服务、凭据管道与终端集成测试：格式/编码保留、失败回滚、并发配置保护、模型与 auth.json 保留、系统凭据隔离读写、CLI 安装幂等、shell 内容保留、无关同名命令保护及写入失败回滚。Mac 跳过 1 项 Windows 路径专用测试。
- 真实 QML 离屏自检：异步 Key 配置与切换、控件对象不重建、没有模型字段、页面每 8 ms 采样不重叠、372 × 302 小窗和单实例协议。
- Windows 冻结 GUI、CLI 取钥与切换、Inno 安装/卸载、PATH 与登录文件保留。
- 此前在 Windows 安装版已实机点击小窗、展开、关闭隐藏、重复唤回及隔离配置的账号/API 往返。托盘图标与菜单点击没有自动化验收。

## macOS

原生 runner：macOS 15 Apple Silicon 与 Intel。macOS 14 是 Qt wheel 最低要求，尚未在 macOS 14 单独实机验收。

- CI 创建随机密码的临时默认钥匙串；结束后恢复原默认/搜索列表并删除测试钥匙串。测试进程禁止授权弹窗，权限错误会失败而不是等待人工输入。
- Security.framework 原生 Keychain 读写；打包图形端通过管道委托同一 helper 身份执行存取、更新与删除，不把 Key 放入 argv、TOML、备份或 shell 历史。
- 冻结 GUI 的 QML/插件与页面自检，独立打包 CLI 的 Keychain/helper 往返。
- 生成 ICNS、菜单栏模板图标、分别编译 arm64 / x86_64、检查 app 的深层代码签名完整性。
- 挂载实际 DMG，复制 App 到带中文、空格和单引号的隔离路径，卸载镜像后配置 Key；检查 helper 的真实绝对路径、zsh 登录/交互 PATH、命令切换、卸载、登录保留，以及 图形端管道存钥到 CLI 取钥、更新和卸载的完整往返。

## 边界

自动测试只使用占位 Key，不调用付费模型、不验证真实额度/模型/速度权限。未重启用户的 Codex。窗口显示全局配置，不能证明已有聊天或菜单缓存热切换。

当前没有提供 Apple Developer ID / notary 凭据的包是 ad-hoc 签名，不能称为 Apple 公证。可选签名、公证脚本需要配置真实凭据后单独验证。Mac 用户侧菜单栏点击、系统首次打开提示、钥匙串授权弹窗和动画观感尚无人工实机验收；CI 不替代这些项目。
