import json
import os
from pathlib import Path
import sys
import tomllib

from .config import API_URL, LEGACY, PROVIDER, ConfigFile, default_home, lock, parse, patch
from .credentials import default_credentials, HelperCredentials
from .errors import SwitchError
from .catalog import endpoint, discover, merge_discovery, make_catalog, model_info
from .settings import MODEL_KEYS, read_state, write_state, atomic_json
import hashlib
from copy import deepcopy

MANAGED_NAME = "API (Codex Switch)"


def helper_command():
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            executable = Path(sys.executable).resolve()
            if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
                executable = executable.parent.parent / "Helpers" / "codex-switch"
            return str(executable), []
        return str(Path(sys.executable).with_name("codex-switch.exe")), []
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return str(executable), [str(Path(__file__).resolve().parents[2] / "app_cli.py")]


def registry_path():
    if os.environ.get("CODEX_SWITCH_DATA_HOME"):
        return Path(os.environ["CODEX_SWITCH_DATA_HOME"]) / "homes.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Codex Switch" / "homes.json"
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
        self.helper = helper or helper_command()
        if credentials is not None:
            self.credentials = credentials
        elif sys.platform == "darwin" and getattr(sys, "frozen", False) and Path(sys.executable).parent.name == "MacOS":
            self.credentials = HelperCredentials(self.home, self.helper)
        else:
            self.credentials = default_credentials(self.home, self.helper[0])
        self.track = track

    @staticmethod
    def managed(provider):
        return isinstance(provider, dict) and provider.get("name") in (MANAGED_NAME, "OpenAI API (Codex Switch)")

    def status(self):
        config = parse(self.config.read())
        connection = read_state(self.home)
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
            ready = (key_saved and own.get("base_url", "").rstrip("/") == connection.get("base_url", API_URL)
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
            "base_url": connection.get("base_url", API_URL),
            "api_label": "OpenAI API" if connection.get("base_url", API_URL) == API_URL else "Custom API",
            "models": connection.get("models", []),
            "catalog_enabled": bool(connection.get("catalog")),
            "catalog_dirty": bool(connection.get("catalog_dirty")),
            "catalog_active": config.get("model_catalog_json") == connection.get("catalog") and bool(connection.get("catalog")),
        }

    def _commit(self, original, updated, connection):
        previous = read_state(self.home)
        pending = dict(connection, _transaction={"previous": previous,
                       "before": hashlib.sha256(original).hexdigest(),
                       "after": hashlib.sha256(updated).hexdigest()})
        # The journal lets the next invocation choose old/new state after interruption.
        write_state(self.home, pending)
        try:
            backup = self.config.commit(original, updated)
        except Exception:
            write_state(self.home, previous)
            raise
        try:
            write_state(self.home, connection)
        except OSError:
            # Config is committed; the durable pending state resolves to the new values.
            pass
        return backup

    def _model_settings(self, doc, connection, mode):
        """Restore account values before changing endpoints or leaving the catalog."""
        if "account_settings" in connection:
            if doc.get("model_provider") != PROVIDER or doc.get("model_catalog_json") != connection.get("active_catalog"):
                raise SwitchError("Model catalog changed outside Codex Switch. Restore the managed catalog before switching.")
            connection["api_model"] = doc.get("model", connection.get("api_model"))
            for key in MODEL_KEYS:
                if key in connection["account_settings"]:
                    doc[key] = connection["account_settings"][key]
                else:
                    doc.pop(key, None)
            del connection["account_settings"]
            connection.pop("active_catalog", None)
        if mode == "api" and connection.get("catalog"):
            path = Path(connection["catalog"])
            if not path.is_file() or path.parent != self.home / "codex-switch" / "catalogs":
                raise SwitchError("Managed catalog is missing. Sync and apply the models again.")
            data = json.loads(path.read_text("utf-8"))
            slugs = [m["slug"] for m in data["models"]]
            connection["account_settings"] = {k: deepcopy(doc[k]) for k in MODEL_KEYS if k in doc}
            for key in MODEL_KEYS:
                doc.pop(key, None)
            doc["model_catalog_json"] = str(path)
            chosen = connection.get("api_model")
            doc["model"] = chosen if chosen in slugs else slugs[0]
            entry = next(m for m in data["models"] if m["slug"] == doc["model"])
            if entry.get("default_reasoning_level"):
                doc["model_reasoning_effort"] = entry["default_reasoning_level"]
            connection["active_catalog"] = str(path)

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
            if mode == "api" and state["base_url"] != API_URL and not state["catalog_enabled"]:
                raise SwitchError("Sync, configure and apply gateway models before switching to this API.")
            if mode == "api" and state["catalog_enabled"] and state["catalog_dirty"]:
                raise SwitchError("The model list or settings changed. Apply the updated catalog before switching to API.")
            original = self.config.read()
            before = parse(original)
            connection = read_state(self.home)
            selected_profile = before.get("profiles", {}).get(before.get("profile"), {})
            if connection.get("catalog") and any(k in selected_profile for k in MODEL_KEYS):
                raise SwitchError("The selected profile overrides model settings. Remove these overrides before applying a catalog.")
            requested = state["api_provider"] if mode == "api" else "openai"
            if before.get("model_provider", "openai") == requested and (mode != "api" or not connection.get("catalog") or before.get("model_catalog_json") == connection["catalog"]):
                return {"changed": False, **state}
            expected = deepcopy(before)
            self._model_settings(expected, connection, mode)
            expected["model_provider"] = requested
            def change(doc):
                for key in (*MODEL_KEYS, "model_provider"):
                    if key in expected:
                        doc[key] = expected[key]
                    else:
                        doc.pop(key, None)
            updated = patch(original, change)
            if parse(updated) != expected:
                raise SwitchError("Unrelated configuration changed; nothing was saved.")
            backup = self._commit(original, updated, connection)
            return {"changed": True, "backup": backup, **self.status()}

    def setup(self, key, base_url=None):
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            from .terminal import ensure_stable_installation
            ensure_stable_installation(self.helper[0])
        if key is not None:
            key = key.strip()
            if not key or any(c.isspace() or ord(c) < 32 for c in key) or len(key.encode("utf-8")) > 2560:
                raise SwitchError("API key cannot be empty or contain spaces/control characters.")
        with lock(self.home):
            original = self.config.read()
            expected = parse(original)
            connection = read_state(self.home)
            url = endpoint(base_url if base_url is not None else connection.get("base_url", API_URL))
            changed_endpoint = url != connection.get("base_url", API_URL)
            if changed_endpoint and key is None:
                raise SwitchError("Enter the key for the new API address. A saved key is never reused on another endpoint.")
            reset_models = changed_endpoint or (key is not None and key != self.credentials.read())
            if reset_models:
                self._model_settings(expected, connection, "account")
                if url != API_URL and expected.get("model_provider") == PROVIDER:
                    expected["model_provider"] = "openai"
                for name in ("models", "catalog", "api_model", "catalog_dirty"):
                    connection.pop(name, None)
            connection["base_url"] = url
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
                "name": MANAGED_NAME, "base_url": url, "wire_api": "responses",
                "auth": {"command": command, "args": [*args, "--codex-home", str(self.home), "credential"],
                         "timeout_ms": 15000, "refresh_interval_ms": 300000},
            }
            providers[PROVIDER] = provider

            def change(doc):
                if "model_providers" not in doc:
                    doc["model_providers"] = {}
                doc["model_providers"][PROVIDER] = provider
                if reset_models:
                    for name in MODEL_KEYS:
                        if name in expected:
                            doc[name] = expected[name]
                        else:
                            doc.pop(name, None)
                    if "model_provider" in expected:
                        doc["model_provider"] = expected["model_provider"]

            updated = patch(original, change)
            if parse(updated) != expected:
                raise SwitchError("Unrelated configuration changed; nothing was saved.")
            if self.track:
                register_home(self.home)
            if key is not None:
                self.credentials.write(key)
            try:
                backup = self._commit(original, updated, connection)
            except Exception:
                if key is not None:
                    if previous_key is None:
                        self.credentials.delete()
                    else:
                        self.credentials.write(previous_key)
                raise
            return {"backup": backup, **self.status()}

    def sync_models(self):
        # Release the config lock during network I/O; reject stale results afterward.
        with lock(self.home):
            original = self.config.read()
            connection = read_state(self.home)
            state = self.status()
            if state["api_provider"] != PROVIDER or not state["api_ready"]:
                raise SwitchError("Save the API connection in Codex Switch before synchronizing models.")
            key = self.credential()
        fresh = discover(state["base_url"], key)
        with lock(self.home):
            if self.config.read() != original or self.credentials.read() != key or read_state(self.home) != connection:
                raise SwitchError("Connection changed during synchronization. Retry.")
            connection["models"] = merge_discovery(fresh, connection.get("models", []))
            connection["catalog_dirty"] = True
            write_state(self.home, connection)
        return self.status()

    def reset_models(self):
        with lock(self.home):
            original = self.config.read()
            expected = parse(original)
            connection = read_state(self.home)
            self._model_settings(expected, connection, "account")
            if expected.get("model_provider") == PROVIDER and connection.get("base_url", API_URL) != API_URL:
                expected["model_provider"] = "openai"
            for name in ("models", "catalog", "api_model", "catalog_dirty"):
                connection.pop(name, None)
            def change(doc):
                for name in (*MODEL_KEYS, "model_provider"):
                    if name in expected:
                        doc[name] = expected[name]
                    else:
                        doc.pop(name, None)
            updated = patch(original, change)
            if parse(updated) != expected:
                raise SwitchError("Unrelated settings changed; model reset was stopped.")
            self._commit(original, updated, connection)
        return self.status()

    def configure_model(self, model, enabled, context_window=32768, reasoning=(), images=False):
        model_info(model, context_window, reasoning, images)
        with lock(self.home):
            connection = read_state(self.home)
            match = next((m for m in connection.get("models", []) if m["id"] == model), None)
            if match is None:
                raise SwitchError("Model is not in the latest synchronized list.")
            match.update(enabled=bool(enabled), context_window=context_window, reasoning=list(reasoning), images=bool(images))
            connection["catalog_dirty"] = True
            write_state(self.home, connection)
        return self.status()

    def apply_models(self, default_model=None):
        with lock(self.home):
            state = self.status()
            if state["api_provider"] != PROVIDER or not state["api_ready"] or state["mode"] == "other" or state["profile_override"]:
                raise SwitchError("The managed API connection is not ready, or a profile overrides it.")
            original = self.config.read()
            expected = parse(original)
            profile = expected.get("profiles", {}).get(expected.get("profile"), {})
            if any(k in profile for k in MODEL_KEYS):
                raise SwitchError("The selected profile overrides model settings; catalog was not applied.")
            connection = read_state(self.home)
            catalog = make_catalog(connection.get("models", []))
            if default_model and default_model not in [m["slug"] for m in catalog["models"]]:
                raise SwitchError("Choose an enabled model as the default.")
            content = json.dumps(catalog, ensure_ascii=False, sort_keys=True).encode()
            path = self.home / "codex-switch" / "catalogs" / (hashlib.sha256(content).hexdigest() + ".json")
            atomic_json(path, catalog)
            connection["catalog"] = str(path)
            connection["catalog_dirty"] = False
            if default_model:
                connection["api_model"] = default_model
            if state["mode"] == "api":
                # _model_settings remembers the previous API choice when restoring.
                self._model_settings(expected, connection, "account")
                if default_model:
                    connection["api_model"] = default_model
                self._model_settings(expected, connection, "api")
            def change(doc):
                for name in MODEL_KEYS:
                    if name in expected:
                        doc[name] = expected[name]
                    else:
                        doc.pop(name, None)
            updated = patch(original, change)
            if parse(updated) != expected:
                raise SwitchError("Unrelated settings changed; catalog was not applied.")
            self._commit(original, updated, connection)
        return self.status()

    def remove_api(self):
        if not self.config.path.exists():
            self.credentials.delete()
            return
        with lock(self.home):
            original = self.config.read()
            expected = parse(original)
            connection = read_state(self.home)
            own = expected.get("model_providers", {}).get(PROVIDER)
            if own is not None and not self.managed(own):
                raise SwitchError("Provider ID belongs to another tool; removal was stopped.")
            if own is not None:
                self._model_settings(expected, connection, "account")
                del expected["model_providers"][PROVIDER]
                if expected.get("model_provider") == PROVIDER:
                    expected["model_provider"] = "openai"

                def change(doc):
                    for name in MODEL_KEYS:
                        if name in expected:
                            doc[name] = expected[name]
                        else:
                            doc.pop(name, None)
                    del doc["model_providers"][PROVIDER]
                    if not doc["model_providers"]:
                        # Materialize an empty parent; implicit TOML tables otherwise vanish.
                        doc["model_providers"] = {}
                    if doc.get("model_provider") == PROVIDER:
                        doc["model_provider"] = "openai"

                updated = patch(original, change)
                if parse(updated) != expected:
                    raise SwitchError("Cannot safely remove the managed provider.")
                for name in ("models", "catalog", "api_model", "catalog_dirty"):
                    connection.pop(name, None)
                self._commit(original, updated, connection)
            self.credentials.delete()

    def credential(self):
        key = self.credentials.read()
        if not key:
            raise SwitchError("No API key is stored; open Codex Switch to configure one.")
        return key
