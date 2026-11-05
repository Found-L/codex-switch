import json
import os
from pathlib import Path
import sys
import tomllib

from .config import API_URL, LEGACY, PROVIDER, ConfigFile, default_home, lock, parse, patch
from .credentials import WindowsCredentials
from .errors import SwitchError

MANAGED_NAME = "OpenAI API (Codex Switch)"


def helper_command():
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).with_name("codex-switch.exe")), []
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return str(executable), [str(Path(__file__).resolve().parents[2] / "app_cli.py")]


def registry_path():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexSwitch" / "homes.json"


def registered_homes():
    try:
        values = json.loads(registry_path().read_text("utf-8"))
        return [Path(p).resolve() for p in values if isinstance(p, str)]
    except (OSError, ValueError, TypeError):
        return []


def register_home(home):
    path = registry_path()
    with lock(path.parent):
        homes = sorted(set([str(home), *(str(p) for p in registered_homes())]))
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(homes, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)


class SwitchService:
    def __init__(self, home=None, credentials=None, helper=None, track=True):
        self.config = ConfigFile(home or default_home())
        self.home = self.config.home
        self.credentials = credentials if credentials is not None else WindowsCredentials(self.home)
        self.helper = helper or helper_command()
        self.track = track

    @staticmethod
    def managed(provider):
        return isinstance(provider, dict) and provider.get("name") == MANAGED_NAME

    def status(self):
        config = parse(self.config.read())
        providers = config.get("model_providers", {})
        current = config.get("model_provider", "openai")
        own = providers.get(PROVIDER)
        legacy = providers.get(LEGACY, {})
        key_saved = False
        if own is not None:
            api_id = PROVIDER
            key_saved = self.managed(own) and bool(self.credentials.read())
            command, prefix = self.helper
            auth = own.get("auth", {}) if isinstance(own, dict) else {}
            ready = (key_saved and own.get("base_url", "").rstrip("/") == API_URL
                     and own.get("wire_api") == "responses"
                     and auth.get("command") == command
                     and auth.get("args") == [*prefix, "--codex-home", str(self.home), "credential"]
                     and Path(command).is_file()
                     and not any(k in own for k in ("env_key", "experimental_bearer_token", "requires_openai_auth")))
        else:
            api_id = LEGACY if legacy.get("base_url", "").rstrip("/") == API_URL and not legacy.get("requires_openai_auth") else PROVIDER
            ready = api_id == LEGACY and (bool(legacy.get("auth", {}).get("command")) or bool(legacy.get("env_key")) or bool(legacy.get("experimental_bearer_token")))
        mode = "account" if current == "openai" else "api" if current in (PROVIDER, LEGACY) else "other"
        profile = config.get("profile")
        override = config.get("profiles", {}).get(profile, {}).get("model_provider") if profile else None
        return {
            "mode": mode, "provider": current, "api_provider": api_id,
            "api_ready": bool(ready), "managed_key": self.managed(own), "key_saved": key_saved,
            "model": config.get("model", ""), "codex_home": str(self.home),
            "config_exists": self.config.path.exists(),
            "profile_override": override, "model_requests": 0,
        }

    def use(self, mode):
        if mode not in ("api", "account"):
            raise SwitchError("Choose api or account.")
        with lock(self.home):
            state = self.status()
            if state["mode"] == "other":
                raise SwitchError("Another provider is selected; switch it manually before using this tool.")
            if state["profile_override"]:
                raise SwitchError("The selected Codex profile overrides model_provider. Remove that override first.")
            if mode == "api" and not state["api_ready"]:
                raise SwitchError("Configure an API key first: codex-switch setup")
            original = self.config.read()
            before = parse(original)
            requested = state["api_provider"] if mode == "api" else "openai"
            if before.get("model_provider", "openai") == requested:
                return {"changed": False, **state}
            updated = patch(original, lambda doc: doc.__setitem__("model_provider", requested))
            expected = dict(before, model_provider=requested)
            if parse(updated) != expected:
                raise SwitchError("Unrelated configuration changed; nothing was saved.")
            backup = self.config.commit(original, updated)
            return {"changed": True, "backup": backup, **self.status()}

    def setup(self, key, initial_model="gpt-6.1-sol"):
        if key is not None:
            key = key.strip()
            if not key or any(c.isspace() or ord(c) < 32 for c in key) or len(key.encode("utf-8")) > 2560:
                raise SwitchError("API key cannot be empty or contain spaces/control characters.")
        if initial_model and any(c.isspace() for c in initial_model):
            raise SwitchError("Model ID cannot contain whitespace.")
        with lock(self.home):
            original = self.config.read()
            expected = parse(original)
            providers = expected.setdefault("model_providers", {})
            if PROVIDER in providers and not self.managed(providers[PROVIDER]):
                raise SwitchError("Provider ID codex_switch_api is already in use; nothing was overwritten.")
            previous_key = self.credentials.read()
            if key is None and not previous_key:
                raise SwitchError("Enter an API key first.")
            command, args = self.helper
            if not Path(command).is_file():
                raise SwitchError("Credential helper is missing. Reinstall Codex Switch.")
            provider = {
                "name": MANAGED_NAME, "base_url": API_URL, "wire_api": "responses",
                "auth": {"command": command, "args": [*args, "--codex-home", str(self.home), "credential"],
                         "timeout_ms": 15000, "refresh_interval_ms": 300000},
            }
            providers[PROVIDER] = provider
            if "model" not in expected and initial_model:
                expected["model"] = initial_model

            def change(doc):
                if "model_providers" not in doc:
                    doc["model_providers"] = {}
                doc["model_providers"][PROVIDER] = provider
                if "model" not in doc and initial_model:
                    doc["model"] = initial_model

            updated = patch(original, change)
            if parse(updated) != expected:
                raise SwitchError("Unrelated configuration changed; nothing was saved.")
            if self.track:
                register_home(self.home)
            if key is not None:
                self.credentials.write(key)
            try:
                backup = self.config.commit(original, updated)
            except Exception:
                if key is not None:
                    if previous_key is None:
                        self.credentials.delete()
                    else:
                        self.credentials.write(previous_key)
                raise
            return {"backup": backup, **self.status()}

    def remove_api(self):
        if not self.config.path.exists():
            self.credentials.delete()
            return
        with lock(self.home):
            original = self.config.read()
            expected = parse(original)
            own = expected.get("model_providers", {}).get(PROVIDER)
            if own is not None and not self.managed(own):
                raise SwitchError("Provider ID belongs to another tool; removal was stopped.")
            if own is not None:
                del expected["model_providers"][PROVIDER]
                if expected.get("model_provider") == PROVIDER:
                    expected["model_provider"] = "openai"

                def change(doc):
                    del doc["model_providers"][PROVIDER]
                    if not doc["model_providers"]:
                        # Materialize an empty parent; implicit TOML tables otherwise vanish.
                        doc["model_providers"] = {}
                    if doc.get("model_provider") == PROVIDER:
                        doc["model_provider"] = "openai"

                updated = patch(original, change)
                if parse(updated) != expected:
                    raise SwitchError("Cannot safely remove the managed provider.")
                self.config.commit(original, updated)
            self.credentials.delete()

    def credential(self):
        key = self.credentials.read()
        if not key:
            raise SwitchError("No API key is stored; open Codex Switch to configure one.")
        return key
