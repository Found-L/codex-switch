"""Atomic non-secret state, bound to the user-confirmed API endpoint."""
import json
import os
import tempfile
import hashlib
from .errors import SwitchError

MODEL_KEYS = ("model", "model_catalog_json", "model_reasoning_effort", "service_tier",
              "model_reasoning_summary", "model_verbosity", "model_context_window", "model_auto_compact_token_limit")


def read_state(home):
    path = home / "codex-switch" / "connection.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        transaction = value.pop("_transaction", None)
        if transaction:
            config_path = home / "config.toml"
            digest = hashlib.sha256(config_path.read_bytes() if config_path.exists() else b"").hexdigest()
            if digest == transaction["after"]:
                return value
            if digest == transaction["before"]:
                return transaction["previous"]
            raise SwitchError("Configuration changed during an interrupted save. Restore a matching config backup before switching.")
        return value
    except (ValueError, OSError, KeyError, TypeError):
        raise SwitchError("Codex Switch connection state is unreadable. Restore connection.json before switching.") from None


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".switch-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        from pathlib import Path
        Path(name).unlink(missing_ok=True)


def write_state(home, value):
    atomic_json(home / "codex-switch" / "connection.json", value)
