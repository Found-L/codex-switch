# v0.1.2 验证记录

验证环境：Windows 11 x64，Python 3.14.4，PyInstaller 6.22.3，Inno Setup 7.1.1；Codex CLI 0.166.0-alpha.6。发布范围为 Windows 10/11 x64，Windows 10 尚未独立实机验收。

## 自动验证

- 17 项单元/集成测试通过，包括独立 Windows 凭据条目读写、Key 写入失败回滚、保留现有模型与 auth.json、中文/UTF-8 BOM/CRLF、配置竞争检测、第三方提供商保护、Profile 覆盖保护、篡改 endpoint/helper 拒绝切换、全新配置卸载恢复。
- 打包后的 CLI 在中文及空格路径下完成 setup → credential helper → account/API 往返 → uninstall-cleanup，配置及备份中不包含测试 Key。
- 打包 GUI 启动自检直接构造真实界面，确认 Tcl/Tk 运行库可以从分发包加载；不读取用户凭据。
- 安装器在临时安装路径与隔离 CODEX_HOME 中完成安装、用户 PATH 注入、Key 配置、启用 API、卸载恢复账号、删除凭据；PATH 和账号文件保持原值。
- Codex `app-server --strict-config --print-startup-config` 接受工具生成的配置，退出码 0。

## 图形界面

对实际打包 EXE 进行了人工可见的自动点击验收：中文连接总览、英文首次 Key 引导、密码掩码、保存并切换后的成功提示、账号/API 往返、语言切换与终端命令页。修复了较小窗口下底部提示被挤出的问题。

## 验证边界

测试 Key 均为隔离测试占位符，不是有效 API 凭据。没有向模型发送请求，没有进行付费生成，也没有验证任何具体 Key 的额度、模型权限、Ultra/速度档位。严格配置校验不是端到端模型请求验证。

未宣称现有桌面聊天的实际提供商、预热聊天或模型菜单已经热切换。窗口只显示全局配置。未验证其他操作系统、ARM、企业策略或所有旧版 Codex。安装包未做商业代码签名。
