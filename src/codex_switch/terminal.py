"""Managed, per-user macOS CLI integration without administrator privileges."""
import os
from pathlib import Path
import shlex
import tempfile

from .errors import SwitchError

LAUNCHER_MARKER = "#!/bin/sh\n# Managed by Codex Switch\n"
BEGIN = "# BEGIN Codex Switch PATH"
END = "# END Codex Switch PATH"
PATH_BLOCK = (BEGIN + '\ncase ":$PATH:" in\n'
              '  *":$HOME/.local/bin:"*) ;;\n'
              '  *) export PATH="$HOME/.local/bin:$PATH" ;;\n'
              'esac\n' + END + '\n')
SHELL_FILES = (".zprofile", ".zshrc", ".bash_profile", ".bashrc")


def _read(path):
    if path.is_symlink():
        raise SwitchError("Refusing to replace a symlink: " + str(path) + ". Use install-cli --no-shell for managed dotfiles.")
    return path.read_text("utf-8") if path.exists() else None


def _without_block(text):
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if not starts and not ends:
        return text
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise SwitchError("The Codex Switch PATH block is incomplete; repair it before continuing.")
    return "".join(lines[:starts[0]] + lines[ends[0] + 1:])


def _atomic_write(path, text, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".codex-switch-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _apply(changes):
    applied = []
    try:
        for path, original, updated, mode in changes:
            if original == updated:
                continue
            if _read(path) != original:
                raise SwitchError("Terminal configuration changed in another program; retry after saving it.")
            if updated is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, updated, mode)
            applied.append((path, original, mode))
    except (OSError, SwitchError):
        for path, original, mode in reversed(applied):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, original, mode)
        raise


def install_cli(helper, home=None, shell=None, configure_shell=True):
    helper = Path(helper).resolve()
    if (not helper.is_file() or helper.name != "codex-switch"
            or helper.parent.name != "Helpers" or helper.parent.parent.name != "Contents"):
        raise SwitchError("Install CLI from the packaged Codex Switch.app first.")
    if str(helper).startswith("/Volumes/") or "/AppTranslocation/" in str(helper):
        raise SwitchError("Copy Codex Switch.app to Applications before installing its command.")
    home = Path(home or Path.home())
    launcher = home / ".local" / "bin" / "codex-switch"
    previous = _read(launcher)
    if previous is not None and not previous.startswith(LAUNCHER_MARKER):
        raise SwitchError("An unrelated codex-switch command exists in ~/.local/bin; it was not replaced.")
    command = LAUNCHER_MARKER + "exec " + shlex.quote(str(helper)) + ' "$@"\n'
    changes = [(launcher, previous, command, 0o755)]
    if configure_shell:
        shell = Path(shell or os.environ.get("SHELL", "/bin/zsh")).name
        if shell not in ("zsh", "bash"):
            raise SwitchError("Automatic PATH setup supports zsh/bash. Use install-cli --no-shell and add ~/.local/bin to PATH.")
        for name in (SHELL_FILES[:2] if shell == "zsh" else SHELL_FILES[2:]):
            path = home / name
            original = _read(path)
            text = _without_block(original or "")
            separator = "" if not text or text.endswith("\n") else "\n"
            updated = text + separator + PATH_BLOCK
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
            changes.append((path, original, updated, mode))
    _apply(changes)
    return str(launcher)


def uninstall_cli(home=None):
    home = Path(home or Path.home())
    launcher = home / ".local" / "bin" / "codex-switch"
    changes = []
    if os.path.lexists(launcher):
        # Unrelated commands, including user symlinks, belong to their owner.
        if not launcher.is_symlink():
            text = _read(launcher)
            if text.startswith(LAUNCHER_MARKER):
                changes.append((launcher, text, None, 0o755))
    for name in SHELL_FILES:
        path = home / name
        if path.exists() and not path.is_symlink():
            original = _read(path)
            updated = _without_block(original)
            changes.append((path, original, updated, path.stat().st_mode & 0o777))
    _apply(changes)
