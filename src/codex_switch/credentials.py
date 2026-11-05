"""OS credential stores. No plaintext file or environment fallback."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .errors import SwitchError


def home_identity(home):
    identity = str(home.resolve())
    return identity.casefold() if os.name == "nt" else identity


def target_for(home):
    identity = home_identity(home).encode("utf-8")
    return "CodexSwitch/OpenAI/" + hashlib.sha256(identity).hexdigest()[:32]


def credential_store_name():
    return "macOS Keychain" if sys.platform == "darwin" else "Windows Credential Manager"


def default_credentials(home, helper=None):
    if sys.platform == "darwin":
        from .macos_credentials import MacOSCredentials
        return MacOSCredentials(home, trusted_paths=[helper] if helper else [])
    if os.name == "nt":
        return WindowsCredentials(home)
    raise SwitchError("Codex Switch supports Windows and macOS.")


class HelperCredentials:
    """Keep packaged macOS GUI and CLI Keychain operations under one code identity."""
    def __init__(self, home, command):
        self.home = Path(home)
        self.executable, self.prefix = command

    def _call(self, operation, key=None):
        arguments = [self.executable, *self.prefix, "--codex-home", str(self.home), "vault-" + operation]
        result = subprocess.run(arguments, input=key + "\n" if key is not None else None,
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        if result.returncode:
            raise SwitchError("Cannot access macOS Keychain through the helper. Unlock the login keychain and allow codex-switch if prompted.")
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise SwitchError("The credential helper returned an invalid response.") from None
        if not isinstance(data, dict):
            raise SwitchError("The credential helper returned an invalid response.")
        return data

    def read(self):
        data = self._call("read")
        key = data.get("key")
        if key is not None and not isinstance(key, str):
            raise SwitchError("The credential helper returned an invalid credential type.")
        return key

    def write(self, key):
        if self._call("write", key).get("ok") is not True:
            raise SwitchError("The credential helper did not save the key.")

    def delete(self):
        if self._call("delete").get("ok") is not True:
            raise SwitchError("The credential helper did not remove the key.")


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentials:
    def __init__(self, home):
        if os.name != "nt":
            raise SwitchError("Windows 10/11 is required.")
        self.target = target_for(home)
        self.api = ctypes.WinDLL("advapi32", use_last_error=True)
        self.api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
        self.api.CredReadW.restype = wintypes.BOOL
        self.api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        self.api.CredWriteW.restype = wintypes.BOOL
        self.api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.api.CredDeleteW.restype = wintypes.BOOL
        self.api.CredFree.argtypes = [ctypes.c_void_p]

    def read(self):
        pointer = ctypes.POINTER(Credential)()
        if not self.api.CredReadW(self.target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return None
            raise SwitchError("Cannot read Windows Credential Manager.")
        try:
            item = pointer.contents
            return ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-8")
        finally:
            self.api.CredFree(pointer)

    def write(self, key):
        data = key.encode("utf-8")
        if not data or len(data) > 2560:
            raise SwitchError("API key length is invalid.")
        blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        item = Credential()
        item.Type, item.Persist = 1, 2  # Generic, local-machine persistence for this Windows user.
        item.TargetName, item.UserName = self.target, "OpenAI API"
        item.CredentialBlobSize, item.CredentialBlob = len(data), blob
        if not self.api.CredWriteW(ctypes.byref(item), 0):
            raise SwitchError("Cannot save API key in Windows Credential Manager.")

    def delete(self):
        if not self.api.CredDeleteW(self.target, 1, 0) and ctypes.get_last_error() != 1168:
            raise SwitchError("Cannot remove API key from Windows Credential Manager.")
