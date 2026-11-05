import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__
from .errors import SwitchError
from .credentials import credential_store_name
from .service import SwitchService, registered_homes, helper_command, registry_path


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Switch Codex account/API configuration without model requests.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--codex-home", type=Path, help="Codex configuration directory (default: CODEX_HOME or ~/.codex)")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "doctor"):
        commands.add_parser(command).add_argument("--json", action="store_true")
    commands.add_parser("runtime", help="Read an existing local server's catalog; never start a model turn")
    commands.add_parser("use").add_argument("mode", choices=("api", "account"))
    for mode in ("api", "account"):
        commands.add_parser(mode, help="Shortcut for use " + mode)
    setup = commands.add_parser("setup", help="Securely enter an API key; never pass it as a command argument")
    setup.add_argument("--use", action="store_true", help="Switch to API after setup")
    setup.add_argument("--key-stdin", action="store_true", help="Read key from redirected stdin (not shell history)")
    setup.add_argument("--base-url", help="HTTPS API base URL, including /v1 when required; default keeps the saved endpoint")
    models = commands.add_parser("models", help="Discover and configure gateway models without inference requests")
    model_commands = models.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("sync")
    model_commands.add_parser("list")
    model_commands.add_parser("reset", help="Remove the managed catalog; keep the saved API connection")
    configure = model_commands.add_parser("configure")
    configure.add_argument("model")
    configure.add_argument("--disable", action="store_true")
    configure.add_argument("--context", type=int, default=32768)
    configure.add_argument("--reasoning", default="", help="Comma-separated levels supported by this route; empty sends no reasoning effort")
    configure.add_argument("--images", action="store_true")
    apply_models = model_commands.add_parser("apply")
    apply_models.add_argument("--default", dest="default_model")
    apply_models.add_argument("--select", nargs="+", help="Replace the menu selection, keeping automatic capability metadata")
    apply_models.add_argument("--use", action="store_true")
    commands.add_parser("gui", help="Open the desktop application")
    install = commands.add_parser("install-cli", help="macOS: install a user-local terminal command and PATH integration")
    install.add_argument("--no-shell", action="store_true", help="Install the launcher without editing shell startup files")
    commands.add_parser("uninstall-cli", help="macOS: remove managed terminal integration")
    uninstall = commands.add_parser("uninstall", help="macOS: detach managed providers/keys and terminal integration before deleting the app")
    uninstall.add_argument("--yes", action="store_true")
    commands.add_parser("credential", help=argparse.SUPPRESS)
    for action in ("read", "write", "delete"):
        commands.add_parser("vault-" + action, help=argparse.SUPPRESS)
    commands.add_parser("uninstall-cleanup", help=argparse.SUPPRESS)
    remove = commands.add_parser("remove-api", help="Remove this tool's provider/key; preserve Codex account login")
    remove.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in ("install-cli", "uninstall-cli", "uninstall"):
            if sys.platform != "darwin":
                raise SwitchError("These integration commands are for macOS. Use Windows Settings for Windows uninstallation.")
            from .terminal import install_cli, uninstall_cli
            if args.command == "install-cli":
                install_cli(helper_command()[0], configure_shell=not args.no_shell)
                print("Terminal command installed in ~/.local/bin. Open a new terminal.")
                return 0
            if args.command == "uninstall":
                if not args.yes and (not sys.stdin.isatty() or input("Detach managed providers/keys and terminal integration? [y/N] ").lower() != "y"):
                    return 1
                for home in set([SwitchService(args.codex_home).home, *registered_homes()]):
                    SwitchService(home).remove_api()
                registry_path().unlink(missing_ok=True)
            uninstall_cli()
            print("Managed integration removed. Account login and configuration backups are preserved.")
            return 0
        if args.command == "gui":
            if getattr(sys, "frozen", False):
                if sys.platform == "darwin":
                    executable = Path(sys.executable).resolve().parent.parent / "MacOS" / "Codex Switch"
                else:
                    executable = Path(sys.executable).with_name("CodexSwitch.exe")
                command = [str(executable)]
                if args.codex_home:
                    command += ["--codex-home", str(args.codex_home)]
                subprocess.Popen(command, **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}))
            else:
                executable = Path(sys.executable)
                if executable.name.lower() == "python.exe":
                    executable = executable.with_name("pythonw.exe")
                command = [str(executable), str(Path(__file__).resolve().parents[2] / "app_gui.py")]
                if args.codex_home:
                    command += ["--codex-home", str(args.codex_home)]
                subprocess.Popen(command, **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}))
            return 0
        if args.command == "uninstall-cleanup":
            for home in set([SwitchService(args.codex_home).home, *registered_homes()]):
                SwitchService(home).remove_api()
            return 0
        service = SwitchService(args.codex_home)
        if args.command == "runtime":
            from .runtime import inspect_runtime
            print(json.dumps(inspect_runtime(service.home), ensure_ascii=False, indent=2))
            return 0
        if args.command == "models":
            if args.model_command == "sync":
                service.sync_models()
            elif args.model_command == "configure":
                service.configure_model(args.model, not args.disable, args.context,
                                        [e.strip() for e in args.reasoning.split(",") if e.strip()], args.images)
            elif args.model_command == "apply":
                service.apply_models(args.default_model, selected=args.select, activate=args.use)
                print("Catalog saved. Fully quit and restart Codex to refresh its model menu. Compatibility has not been tested.")
            elif args.model_command == "reset":
                service.reset_models()
            print(json.dumps(service.status()["models"], ensure_ascii=False, indent=2))
            return 0
        if args.command.startswith("vault-"):
            if sys.stdout.isatty():
                raise SwitchError("Internal credential protocol requires redirected output.")
            if args.command == "vault-read":
                response = {"key": service.credentials.read()}
            elif args.command == "vault-write":
                if sys.stdin.isatty():
                    raise SwitchError("Internal credential input must be redirected.")
                key = sys.stdin.read(2561).strip()
                if not key or any(c.isspace() or ord(c) < 32 for c in key) or len(key.encode("utf-8")) > 2560:
                    raise SwitchError("API key length or characters are invalid.")
                service.credentials.write(key)
                response = {"ok": True}
            else:
                service.credentials.delete()
                response = {"ok": True}
            print(json.dumps(response), flush=True)
            return 0
        if args.command == "credential":
            if sys.stdout.isatty():
                raise SwitchError("Internal credential helper; output to an interactive terminal is disabled.")
            print(service.credential(), flush=True)
            return 0
        if args.command in ("status", "doctor"):
            result = service.status()
            if args.command == "doctor":
                result["codex_cli_found"] = bool(shutil.which("codex"))
                result["helper_installed"] = Path(service.helper[0]).is_file()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("Current configuration: " + result["mode"] + " (" + result["provider"] + ")")
                print("API configured: " + ("yes" if result["api_ready"] else "no"))
                print("Codex home: " + result["codex_home"])
                if result["profile_override"]:
                    print("Warning: selected profile overrides model_provider.")
                if args.command == "doctor":
                    print("Codex CLI: " + ("found" if result["codex_cli_found"] else "not found; desktop-only use is possible"))
            return 0
        if args.command == "setup":
            if args.key_stdin:
                if sys.stdin.isatty():
                    raise SwitchError("--key-stdin requires redirected input.")
                key = sys.stdin.read(2561)
            else:
                if not sys.stdin.isatty():
                    raise SwitchError("Use --key-stdin for redirected input.")
                key = getpass.getpass("API key for the configured endpoint (hidden): ")
            service.setup(key, args.base_url)
            print("API key saved in " + credential_store_name() + ".")
            if args.use:
                service.use("api")
                print("Switched to API. Start a new Codex chat; existing chats keep their provider.")
            return 0
        if args.command == "remove-api":
            if not args.yes and (not sys.stdin.isatty() or input("Remove managed API provider/key? [y/N] ").lower() != "y"):
                return 1
            service.remove_api()
            print("Managed API provider/key removed; Codex account login preserved.")
            return 0
        mode = args.mode if args.command == "use" else args.command
        service.use(mode)
        print("Configuration: " + mode + ". Start a new Codex chat; existing chats keep their provider.")
        return 0
    except SwitchError as error:
        print("Error: " + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError):
        print("Error: Local configuration operation failed; no credential contents are displayed.", file=sys.stderr)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
    except Exception:
        print("Error: Operation failed. Repair the local configuration or reinstall Codex Switch.", file=sys.stderr)
    return 1
