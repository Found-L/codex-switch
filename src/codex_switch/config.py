"""Preserve TOML comments, encoding and other settings; back up before writes."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import time
import tomllib

import tomlkit

from .errors import SwitchError

PROVIDER = "codex_switch_api"
LEGACY = "openai_api"
API_URL = "https://api.openai.com/v1"


def default_home():
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeError:
        raise SwitchError("config.toml must use UTF-8; no changes were made.") from None


def parse(raw):
    try:
        return tomllib.loads(decode(raw))
    except tomllib.TOMLDecodeError:
        raise SwitchError("config.toml has invalid TOML; repair it before switching.") from None


def patch(raw, change):
    text = decode(raw)
    try:
        document = tomlkit.parse(text)
        change(document)
        updated = tomlkit.dumps(document)
    except (ValueError, TypeError, KeyError, tomlkit.exceptions.TOMLKitError):
        raise SwitchError("Cannot safely update config.toml; no changes were made.") from None
    # Normalize newly inserted lines to the existing document's newline style.
    if "\r\n" in text:
        updated = updated.replace("\r\n", "\n").replace("\n", "\r\n")
    encoded = updated.encode("utf-8")
    return (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + encoded


@contextmanager
def lock(home):
    import msvcrt
    state = home / "codex-switch"
    state.mkdir(parents=True, exist_ok=True)
    with (state / "config.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + 5
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SwitchError("Another switch is in progress; retry shortly.") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class ConfigFile:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.path = self.home / "config.toml"

    def read(self):
        return self.path.read_bytes() if self.path.exists() else b""

    def commit(self, original, updated):
        if original == updated:
            return None
        parse(updated)
        if self.read() != original:
            raise SwitchError("Config changed in another program; refresh and retry.")
        backups = self.home / "codex-switch" / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / (str(time.time_ns()) + ".toml")
        backup.write_bytes(original)
        fd, name = tempfile.mkstemp(prefix=".codex-switch-", dir=self.home)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            if self.read() != original:
                raise SwitchError("Config changed in another program; no overwrite was performed.")
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
        return str(backup)
