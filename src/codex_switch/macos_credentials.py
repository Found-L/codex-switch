"""macOS login Keychain via Security.framework; secrets never enter argv."""
import ctypes as ct
import os
from pathlib import Path
import sys

from .credentials import target_for
from .errors import SwitchError


class MacOSCredentials:
    NOT_FOUND = -25300
    DUPLICATE = -25299

    def __init__(self, home, trusted_paths=()):
        if sys.platform != "darwin":
            raise SwitchError("macOS Keychain requires macOS.")
        self.target = target_for(home)
        self.trusted_paths = sorted({str(Path(p).resolve()) for p in trusted_paths if p})
        for executable in tuple(self.trusted_paths):
            path = Path(executable)
            if path.parent.name == "Helpers" and path.parent.parent.name == "Contents":
                gui = path.parent.parent / "MacOS" / "Codex Switch"
                if gui.is_file():
                    self.trusted_paths.append(str(gui))
        self.cf = ct.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.security = ct.CDLL("/System/Library/Frameworks/Security.framework/Security")
        signatures = {
            "CFStringCreateWithCString": ([ct.c_void_p, ct.c_char_p, ct.c_uint32], ct.c_void_p),
            "CFDataCreate": ([ct.c_void_p, ct.c_void_p, ct.c_long], ct.c_void_p),
            "CFDataGetLength": ([ct.c_void_p], ct.c_long),
            "CFDataGetBytePtr": ([ct.c_void_p], ct.c_void_p),
            "CFDictionaryCreate": ([ct.c_void_p, ct.c_void_p, ct.c_void_p, ct.c_long, ct.c_void_p, ct.c_void_p], ct.c_void_p),
            "CFArrayCreate": ([ct.c_void_p, ct.c_void_p, ct.c_long, ct.c_void_p], ct.c_void_p),
            "CFRelease": ([ct.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.cf, name)
            function.argtypes, function.restype = args, result
        for name, args in {
            "SecItemCopyMatching": [ct.c_void_p, ct.POINTER(ct.c_void_p)],
            "SecItemAdd": [ct.c_void_p, ct.POINTER(ct.c_void_p)],
            "SecItemUpdate": [ct.c_void_p, ct.c_void_p],
            "SecItemDelete": [ct.c_void_p],
            "SecTrustedApplicationCreateFromPath": [ct.c_char_p, ct.POINTER(ct.c_void_p)],
            "SecAccessCreate": [ct.c_void_p, ct.c_void_p, ct.POINTER(ct.c_void_p)],
        }.items():
            function = getattr(self.security, name)
            function.argtypes, function.restype = args, ct.c_int32
        if os.environ.get("CODEX_SWITCH_NO_KEYCHAIN_UI") == "1":
            function = self.security.SecKeychainSetUserInteractionAllowed
            function.argtypes, function.restype = [ct.c_ubyte], ct.c_int32
            self._check(function(0))

    def _trace(self, operation):
        if os.environ.get("CODEX_SWITCH_NO_KEYCHAIN_UI") == "1" and sys.stderr is not None:
            print("Keychain integration: " + operation, file=sys.stderr, flush=True)

    def _constant(self, name):
        return ct.c_void_p.in_dll(self.security, name).value

    def _callback(self, name):
        return ct.addressof(ct.c_byte.in_dll(self.cf, name))

    def _string(self, text, owned):
        value = self.cf.CFStringCreateWithCString(None, text.encode("utf-8"), 0x08000100)
        if not value:
            raise SwitchError("Cannot prepare a macOS Keychain request.")
        owned.append(value)
        return value

    def _dictionary(self, fields, owned):
        keys = (ct.c_void_p * len(fields))(*(self._constant(k) for k in fields))
        values = (ct.c_void_p * len(fields))(*fields.values())
        result = self.cf.CFDictionaryCreate(None, keys, values, len(fields),
                                           self._callback("kCFTypeDictionaryKeyCallBacks"),
                                           self._callback("kCFTypeDictionaryValueCallBacks"))
        if not result:
            raise SwitchError("Cannot prepare a macOS Keychain request.")
        owned.append(result)
        return result

    def _fields(self, owned):
        fields = {"kSecClass": self._constant("kSecClassGenericPassword"),
                  "kSecAttrService": self._string("FoundL.CodexSwitch.OpenAI", owned),
                  "kSecAttrAccount": self._string(self.target, owned)}
        if os.environ.get("CODEX_SWITCH_NO_KEYCHAIN_UI") == "1":
            # CI must fail rather than waiting for an invisible authorization prompt.
            fields["kSecUseAuthenticationUI"] = self._constant("kSecUseAuthenticationUIFail")
        return fields

    def _release(self, owned):
        for value in reversed(owned):
            self.cf.CFRelease(value)

    def _check(self, status):
        if status:
            raise SwitchError("macOS Keychain operation failed (" + str(status) +
                              "). Unlock the login keychain and allow Codex Switch if prompted.")

    def _access(self, owned):
        applications = []
        # NULL identifies the actual caller. Python.org's macOS launcher path in
        # sys.executable can differ from the process binary checked by Keychain.
        for path in [None, *self.trusted_paths]:
            self._trace("authorize binary")
            application = ct.c_void_p()
            self._check(self.security.SecTrustedApplicationCreateFromPath(path.encode("utf-8") if path else None, ct.byref(application)))
            owned.append(application.value)
            applications.append(application.value)
        values = (ct.c_void_p * len(applications))(*applications)
        array = self.cf.CFArrayCreate(None, values, len(applications), self._callback("kCFTypeArrayCallBacks"))
        if not array:
            raise SwitchError("Cannot authorize the application and credential helper.")
        owned.append(array)
        access = ct.c_void_p()
        self._trace("create access list")
        self._check(self.security.SecAccessCreate(self._string("Codex Switch OpenAI API", owned), array, ct.byref(access)))
        owned.append(access.value)
        return access.value

    def read(self):
        self._trace("read")
        owned = []
        result = ct.c_void_p()
        try:
            fields = self._fields(owned)
            fields.update(kSecReturnData=ct.c_void_p.in_dll(self.cf, "kCFBooleanTrue").value,
                          kSecMatchLimit=self._constant("kSecMatchLimitOne"))
            status = self.security.SecItemCopyMatching(self._dictionary(fields, owned), ct.byref(result))
            if status == self.NOT_FOUND:
                return None
            self._check(status)
            if not result.value:
                raise SwitchError("macOS Keychain returned no credential data.")
            return ct.string_at(self.cf.CFDataGetBytePtr(result), self.cf.CFDataGetLength(result)).decode("utf-8")
        finally:
            if result.value:
                self.cf.CFRelease(result)
            self._release(owned)

    def write(self, key):
        self._trace("write")
        data = key.encode("utf-8")
        if not data or len(data) > 2560:
            raise SwitchError("API key length is invalid.")
        owned = []
        try:
            value = self.cf.CFDataCreate(None, data, len(data))
            if not value:
                raise SwitchError("Cannot prepare a macOS Keychain credential.")
            owned.append(value)
            fields = self._fields(owned)
            query = self._dictionary(fields, owned)
            updates = {"kSecValueData": value, "kSecAttrAccess": self._access(owned)}
            updated = self._dictionary(updates, owned)
            self._trace("update item")
            status = self.security.SecItemUpdate(query, updated)
            if status == self.NOT_FOUND:
                self._trace("add item")
                status = self.security.SecItemAdd(self._dictionary({**fields, **updates}, owned), None)
                if status == self.DUPLICATE:
                    status = self.security.SecItemUpdate(query, updated)
            self._check(status)
        finally:
            self._release(owned)

    def delete(self):
        self._trace("delete")
        owned = []
        try:
            status = self.security.SecItemDelete(self._dictionary(self._fields(owned), owned))
            if status != self.NOT_FOUND:
                self._check(status)
        finally:
            self._release(owned)
