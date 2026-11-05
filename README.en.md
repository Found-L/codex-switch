# Codex Switch

English · [简体中文](README.md)

A small Windows app and CLI for switching Codex between an existing account login and your own OpenAI API key.

**[Download the installer / portable ZIP](https://github.com/Found-L/codex-switch/releases/latest)**

## Get started

1. Install [Codex](https://learn.chatgpt.com/docs/quickstart). Sign in to Codex first if you want to use account credits.
2. Install `CodexSwitch-VERSION-windows-x64-setup.exe`. Windows 10/11 x64; no Python or administrator access required.
3. Open **Codex Switch**, enter your own [OpenAI API key](https://platform.openai.com/api-keys), then select **Save and use API**. Existing model settings are preserved; new configurations can specify an initial model.
4. Start a new Codex chat. Use the connection cards to switch back later. The UI includes an English/Chinese toggle.

Keys are kept in Windows Credential Manager, scoped to your Windows user and Codex configuration directory. Enter your own key again on another computer. Account credits and API usage have separate billing.

## Terminal

Open a new terminal after installation:

```powershell
codex-switch setup --use
codex-switch status
codex-switch use api
codex-switch use account
codex-switch doctor --json
codex-switch gui
```

`setup` hides keyboard input. Do not pass secrets in command arguments or shell history. Automation can use redirected stdin with `setup --key-stdin --use`. Custom homes: `codex-switch --codex-home D:\my-codex status`. The `CODEX_HOME` environment variable is respected.

The portable ZIP needs no installation. Extract it and run `CodexSwitch.exe` or `.\codex-switch.exe`. Do not move its directory after setup: the provider uses an absolute helper path. Re-save API setup after moving it.

## Behavior and limits

Switching updates the top-level provider in global `config.toml`. Setup adds a separately named `codex_switch_api` provider using official [command-backed authentication](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers). Existing account login, `auth.json`, models, speed settings, MCP and catalogs are preserved. Config backups are local to `CODEX_HOME/codex-switch/backups`. Never share backups of a preexisting configuration that may contain other secrets.

Existing official-OpenAI `openai_api` configurations can be reused without migrating credentials. Other providers are not forcibly replaced. A selected profile overriding `model_provider` blocks global switching.

The UI shows global configuration, not the billing route of an already running chat. Existing chats, desktop prewarming/catalog caches, project configs and explicit CLI overrides can differ. Reload Codex if a full menu refresh is needed. The app does not terminate Codex.

Setup is local and does not send requests to verify API access. Model availability, modes, quota and key validity depend on the OpenAI project. No model list is fabricated or filtered. Switching itself makes no network/model requests. Requires a Codex build supporting command-backed provider authentication; local baseline: CLI `0.166.0-alpha.6`. Only Windows 10/11 x64 is supported in this release.

The per-user installer adds an optional desktop shortcut and user PATH entry. Uninstallation first detaches this tool's managed provider, switches a managed active API config back to `openai`, and removes its keys for registered homes. Account login and local backups remain; external legacy providers are left intact. For portable builds, run `codex-switch remove-api --yes` before deleting files. If permissions/config errors prevent safe cleanup, repair the affected home before uninstalling.

This is an independent community tool, not an OpenAI product. It bundles neither Codex nor API keys. Release binaries are not code-signed; SHA-256 checksums are provided.

## Build

Use Python 3.14 x64 and Inno Setup 6/7:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-build.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\scripts\build.ps1 -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

Tagging `v*` runs Windows CI tests/builds and publishes installer, portable ZIP and checksums. See [validation](docs/validation.md), [MIT license](LICENSE), and [third-party notices](THIRD_PARTY_NOTICES.md).
