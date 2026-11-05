"""Run the macOS build with a disposable default Keychain, restoring it in finally."""
import base64
import os
import platform
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tempfile


def security(*args):
    result = subprocess.run(["/usr/bin/security", *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("macOS CI Keychain step failed: " + args[0])
    return result.stdout.strip()


def main():
    if sys.platform != "darwin":
        raise SystemExit("macOS is required.")
    expected = os.environ.get("EXPECTED_ARCH")
    if expected and platform.machine() != expected:
        raise SystemExit("macOS runner architecture does not match its release asset.")
    previous_default = shlex.split(security("default-keychain", "-d", "user"))
    previous_list = shlex.split(security("list-keychains", "-d", "user"))
    with tempfile.TemporaryDirectory(prefix="codex-switch-ci-") as temporary:
        keychain = Path(temporary) / "fixture.keychain-db"
        password = secrets.token_urlsafe(32)
        created = False
        try:
            security("create-keychain", "-p", password, keychain)
            created = True
            security("set-keychain-settings", "-lut", "21600", keychain)
            security("unlock-keychain", "-p", password, keychain)
            security("list-keychains", "-d", "user", "-s", keychain, *previous_list)
            security("default-keychain", "-d", "user", "-s", keychain)
            environment = dict(os.environ)
            certificate = environment.pop("MACOS_CERTIFICATE_P12", "")
            certificate_password = environment.pop("MACOS_CERTIFICATE_PASSWORD", "")
            if certificate:
                p12 = Path(temporary) / "identity.p12"
                p12.write_bytes(base64.b64decode(certificate, validate=True))
                p12.chmod(0o600)
                security("import", p12, "-k", keychain, "-P", certificate_password, "-T", "/usr/bin/codesign")
                security("set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", password, keychain)
                identities = security("find-identity", "-v", "-p", "codesigning", keychain)
                identity = re.search(r'([A-Fa-f0-9]{40})\s+"Developer ID Application:', identities)
                if not identity:
                    raise RuntimeError("The certificate does not contain a Developer ID Application identity.")
                environment["MACOS_SIGN_IDENTITY"] = identity.group(1)
            elif certificate_password:
                raise RuntimeError("MACOS_CERTIFICATE_PASSWORD was provided without a certificate.")
            subprocess.run([sys.executable, "scripts/build_macos.py"], env=environment, check=True)
        finally:
            if previous_default:
                security("default-keychain", "-d", "user", "-s", previous_default[0])
            security("list-keychains", "-d", "user", "-s", *previous_list)
            if created:
                security("delete-keychain", keychain)


if __name__ == "__main__":
    main()
