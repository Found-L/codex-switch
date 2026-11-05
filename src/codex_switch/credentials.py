"""Per-Windows-user credentials. No plaintext file or environment fallback."""
import ctypes
from ctypes import wintypes
import hashlib
import os

from .errors import SwitchError


def target_for(home):
    identity = str(home.resolve()).casefold().encode("utf-8")
    return "CodexSwitch/OpenAI/" + hashlib.sha256(identity).hexdigest()[:32]


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
