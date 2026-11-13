"""Opt-in native speed UI adapter. Never rewrites the installed Codex bundle.

Only verified client gates are adapted. Account permissions, provider routing,
model selection and server authorization retain their normal implementation.
"""
import base64
import ctypes
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import struct
import subprocess
import threading
import time
from urllib.parse import urlsplit, unquote
from urllib.request import build_opener, ProxyHandler
import xml.etree.ElementTree as ET
import websocket

from .catalog import bundled_metadata, NoRedirect
from .config import API_URL, lock, parse, patch
from .errors import SwitchError
from .settings import MODEL_KEYS, atomic_json, read_state
from .speed import FAST_MODELS, ULTRA_MODELS

LEGACY_VERSION = "26.1029.7803.0"
PREVIOUS_VERSION = "26.1103.3517.0"
CURRENT_VERSION = "26.1106.6628.0"
SUPPORTED_VERSIONS = (LEGACY_VERSION, PREVIOUS_VERSION, CURRENT_VERSION)
PREVIOUS_EXECUTION_ASSET = "webview/assets/async/182735.e33af7cdca.js"
PREVIOUS_ASSET_HASHES = {
    "/assets/async/159406.7576d6a66d.js": "f00daac90cf3f26ad1f033f751ab33a4b240a0310bb960cc05ae0deaf9842c96",
    "/assets/async/182735.e33af7cdca.js": "2ff6c3b6fdf3f05660a3ac0ddd672f57dba25dd7588c194d60cba5b1984067a6",
    "/assets/async/265759.a607bc9dec.js": "105de578277057823f45ac322daf4cfb03145254f89e8dbaf74ffbfee51133c5",
    "/assets/async/29761.678feb9296.js": "dd017aa021e6c3635e7c8ca18bcc58396245005c52d2ad579bf57d37e627be3d",
    "/assets/async/321808.c362f3c7ed.js": "cd6dcde823cb50f337eefc401edc5c30d28f5f3efb43c0e75172a14c35b41ab9",
    "/assets/async/377631.ba30eb7339.js": "e3ada5f0fe2ad729d09cb5f3dee504e2767eee4da82ae788968c827eb0e0e92f",
    "/assets/async/414655.475f85a448.js": "db78945a4db37885f473d2ce5b07e3a03f5c7225fd58a3960de0041a9b3331bb",
    "/assets/async/434155.be55380188.js": "70fb77e2d594e7b89d0649d202588def2830df1353fea83f9efbaadafe0e9fc0",
    "/assets/async/553834.8bcca01908.js": "d6ca69c44e25ae58f9ce2c9ac158e46dde150dd1b0252983ee3cadfc7a6846a7",
    "/assets/async/634175.2a7073aefa.js": "0b185ae720fc881c2861256d87fb4b2a03df3ef329178a337c25f92023f4963a",
    "/assets/async/725998.a29d1f3c16.js": "de74b1c5284539a53b80c45b66114012417d4d79d5bf9c00da58d0dac07db1c4",
    "/assets/async/783456.a3b05bbbc0.js": "f2d60b65162e707ce6871c193c7bb105b8dba82a3b7de72c18724accaaba79e9",
    "/assets/async/884655.c5382cb292.js": "a8c9d3dc7ae976048455217c742f6a123903a79c31addbf4870c2dea650e3ea4",
    "/assets/async/954045.056304beca.js": "9d43ef476e9df02e760fa573508e0386c8afb6f0e113dc9d2cb6937897aa529c",
    "/assets/async/962007.7574ee80e4.js": "f9d34bacbc65ec8d04877f20b4656a4c3b2747bc85cfd3ae46aa2227376e5b64",
}
EXECUTION_ASSET = "webview/assets/async/739301.37a39f26d6.js"
CURRENT_ASSET_HASHES = {
    "/assets/async/150595.08945a16f7.js": "f3bc7d63bacd3eadc0a1d890e0c0a35457a3f605c4d245bdab2cb2b5a2e37604",
    "/assets/async/151215.ae700dbbcb.js": "7990c76b69b673c5706910ffda02a47217364885a731829feb9a1fc1f4c33cd2",
    "/assets/async/184348.76f62e0345.js": "5dbc042aa20eb925566dfbfd70e7b39312bc5c803c7bf4f1c3a6d68760d03879",
    "/assets/async/222624.ceee0263cf.js": "30862c9f2a95db39a667aeb9e0f5266639bc0361f8addae86a9baa2fb27897b8",
    "/assets/async/228368.464209035b.js": "fbd0a13421e8937af0450d2dc4ed801a59e82b45a6c6b170f86c2ff1c711eebc",
    "/assets/async/244404.f80163303b.js": "60371e6a9b999245fb7932771fa7b4dde29bcdedee852961fde97eeac52d05bd",
    "/assets/async/29761.fe962986f8.js": "80ff8d2b831534bbb0e55537d3a63ea5ee9fb6e08ca529394894156535bbe3d4",
    "/assets/async/309546.0078349267.js": "62480977bb708ff9644000a688e163006e3a030a0a25033927eec72d58199388",
    "/assets/async/363454.74e51067fe.js": "baeb96e688ea646495617df61634d41e36dd46046ece703469e00ef3edb76978",
    "/assets/async/390941.0e04fe7f23.js": "3bc600315bbb0b97740b02b3ba739dcd746c9f325f9a7977db6c46a6bde2692c",
    "/assets/async/516636.3f3a73694a.js": "4e6bfc54cd8248683818adf15f36bbeb58ded2406f8ab4623003d5017cf0857c",
    "/assets/async/739301.37a39f26d6.js": "acc2174e4ed3d2068af26c1731f08e8978c853864aea9c0a917ae9d246885058",
    "/assets/async/74254.1ff6ce5850.js": "b21edd6147ad2a8d8283385daa95a031955ace61be2f40013e2ba1d956dcaaca",
    "/assets/async/783456.56be3fdcab.js": "d8ebe435fd6667b1678c752081451d03115303bae497a1a79f9dfb3250612d67",
    "/assets/async/875355.d2e689cf20.js": "8f346a67adc399768f0f9045359f95ad5338c17a9ca2509959e4d33237b4933f",
    "/assets/async/954045.dc6493fd54.js": "e9ad8c382f1c7990124f447633e11f6a07c2926e85da8df5b6063b4027232663",
}
MAX_ASSET = 20 * 1024 * 1024
CATALOG_FIELDS = ("catalog", "active_catalog", "active_provider", "catalog_provider", "api_model", "account_settings", "account_speed", "api_service_tier")
MODULE = re.compile(r"(?:^|[,\{])([A-Za-z0-9_$]{4})\([A-Za-z0-9_$,]*\)\{")
TARGET_MODULE = re.compile(r"(?:^|[,\{])(ipV4|PAzX)\([A-Za-z0-9_$,]*\)\{")
ACCESS = re.compile(r'(?P<a>[\w$]+)\?\.authMethod==="chatgpt"\|\|(?P=a)\?\.authMethod==="personalAccessToken"\|\|(?P=a)\?\.authMethod==="amazonBedrock"')
REQUEST = re.compile(r'if\("chatgpt"!==(?P<a>[\w$]+)&&"personalAccessToken"!==(?P=a)&&"amazonBedrock"!==(?P=a)\)return null;')
SAVED_GATE = ('let n=await e.getAccount({priority:"critical"});return '
              'n.account?.type==="chatgpt"||n.account?.type==="amazonBedrock"')
SUBMIT_GATE = ('let{account:t}=await e.getAccount({priority:"critical"});return '
               't?.type==="chatgpt"||t?.type==="amazonBedrock"?d.serviceTier:null')


def required_labels(version):
    if version not in SUPPORTED_VERSIONS:
        raise SwitchError("This Codex version has not been adapted. Native mode was not enabled.")
    return {"access", "request"} if version == LEGACY_VERSION else {"access", "request", "saved", "submit"}


def pinned_assets(version):
    if version == CURRENT_VERSION:
        return EXECUTION_ASSET, CURRENT_ASSET_HASHES
    if version == PREVIOUS_VERSION:
        return PREVIOUS_EXECUTION_ASSET, PREVIOUS_ASSET_HASHES
    return None, {}


def adapt_execution(source):
    """Modify the two account checks only in a pinned execution asset."""
    if source.count(SAVED_GATE) != 1 or source.count(SUBMIT_GATE) != 1:
        raise SwitchError("Native speed signatures changed; the installed client was not modified.")
    saved = (SAVED_GATE + '||n.account?.type==="apiKey"'
             '||(null==n.account&&!1===n.requiresOpenaiAuth)')
    submit = ('let{account:t,requiresOpenaiAuth:__codexSwitchRequiresAuth}='
              'await e.getAccount({priority:"critical"});return '
              't?.type==="chatgpt"||t?.type==="amazonBedrock"||t?.type==="apiKey"'
              '||(null==t&&!1===__codexSwitchRequiresAuth)?d.serviceTier:null')
    if "__codexSwitchRequiresAuth" in source:
        raise SwitchError("Native speed signatures changed; the installed client was not modified.")
    return source.replace(SAVED_GATE, saved).replace(SUBMIT_GATE, submit), {"saved", "submit"}


def adapt(source):
    """Strict scoped signatures; unknown or ambiguous shapes are never patched."""
    edits, labels = [], set()
    for match in TARGET_MODULE.finditer(source):
        name = match.group(1)
        start = match.start() + (source[match.start()] in ',{')
        next_module = MODULE.search(source, match.end())
        end = next_module.start() + 1 if next_module else len(source)
        body = source[start:end]
        pattern = ACCESS if name == "ipV4" else REQUEST
        matches = list(pattern.finditer(body))
        if len(matches) != 1:
            raise SwitchError("Native speed signatures changed; the installed client was not modified.")
        found = matches[0]
        variable = found.group("a")
        if name == "ipV4":
            replacement = found.group() + f'||{variable}?.authMethod==="apikey"||{variable}?.requiresAuth===!1'
            label = "access"
        else:
            replacement = found.group().replace(")return null;", f'&&"apikey"!=={variable}&&null!=={variable})return null;')
            label = "request"
        edits.append((start + found.start(), start + found.end(), replacement))
        labels.add(label)
    for start, end, replacement in reversed(edits):
        source = source[:start] + replacement + source[end:]
    return source, labels


def inspect_archive(path, version):
    required = required_labels(version)
    execution_asset, hashes = pinned_assets(version)
    assets = {}
    with Path(path).open("rb") as stream:
        header = stream.read(16)
        if len(header) != 16:
            raise SwitchError("The native client archive is invalid.")
        _, header_size, _, length = struct.unpack("<4I", header)
        if not 0 < length <= 32 * 1024 * 1024 or header_size < length:
            raise SwitchError("The native client archive is invalid.")
        document = json.loads(stream.read(length))
        base = 8 + header_size
        def entries(node, prefix=""):
            for name, info in node.get("files", {}).items():
                name = prefix + name
                if "files" in info:
                    yield from entries(info, name + "/")
                elif name.startswith("webview/assets/") and name.endswith(".js") and "offset" in info and not info.get("unpacked"):
                    yield name, info
        for name, info in entries(document):
            if not 0 < info["size"] <= MAX_ASSET:
                continue
            stream.seek(base + int(info["offset"]))
            raw = stream.read(info["size"])
            source = raw.decode("utf-8")
            key = name.removeprefix("webview")
            is_execution = name == execution_asset
            has_target = bool(("ipV4(" in source and re.search(r'(?:^|[,\{])ipV4\(', source))
                              or ("PAzX(" in source and re.search(r'(?:^|[,\{])PAzX\(', source)))
            if hashes and (key in hashes or has_target):
                if hashlib.sha256(raw).hexdigest() != hashes.get(key):
                    raise SwitchError("Native client resource changed; the adapter stopped without modifying installed files.")
            if not (is_execution or has_target):
                continue
            if is_execution:
                changed, labels = adapt_execution(source)
            else:
                changed, labels = adapt(source)
            if labels:
                assets[key] = {"sha256": hashlib.sha256(raw).hexdigest(),
                    "body": changed.encode(), "labels": labels}
    if hashes and set(assets) != set(hashes):
        raise SwitchError("This Codex build has no complete supported native speed adapter.")
    if set().union(*(a["labels"] for a in assets.values())) != required:
        raise SwitchError("This Codex build has no complete supported native speed adapter.")
    return assets


def powershell(script, values=None, timeout=20):
    completed = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
        "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); " + script],
        input=json.dumps(values or {}), text=True, encoding="utf-8", capture_output=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if completed.returncode:
        raise SwitchError("Cannot inspect or launch the native Codex client. No installed files were changed.")
    return json.loads(completed.stdout)


def installation(strict=True):
    if os.name != "nt":
        raise SwitchError("The experimental native adapter currently supports Windows only.")
    info = powershell("$p=Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1; if (!$p) {throw 'missing'}; "
        "@{root=$p.InstallLocation;version=$p.Version.ToString();family=$p.PackageFamilyName;publisher=$p.PublisherId} | ConvertTo-Json -Compress")
    root = Path(info["root"]).resolve()
    if ((strict and info["version"] not in SUPPORTED_VERSIONS) or info["publisher"] != "2p2nqsd0c76g0"
            or root.parent != Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "WindowsApps"):
        raise SwitchError("This Codex version has not been adapted. Native mode was not enabled.")
    manifest = ET.parse(root / "AppxManifest.xml").getroot()
    apps = [a for a in manifest.iter() if a.tag.endswith("}Application") and a.attrib.get("Id") == "App"
            and a.attrib.get("Executable", "").replace("\\", "/") == "app/ChatGPT.exe"]
    if len(apps) != 1:
        raise SwitchError("The native Codex application identity is ambiguous.")
    return {**info, "root": str(root), "aumid": info["family"] + "!" + apps[0].attrib["Id"],
            "archive": str(root / "app/resources/app.asar")}


def desktop_running(info):
    running = powershell("$v=[Console]::In.ReadToEnd() | ConvertFrom-Json; "
        "$p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('ChatGPT.exe','Codex.exe') }); "
        "$b=@($p | Where-Object { !$_.ExecutablePath -or $_.ExecutablePath.StartsWith($v.root+'\\',[StringComparison]::OrdinalIgnoreCase) }); "
        "@{running=($b.Count -gt 0)} | ConvertTo-Json -Compress", info)
    return running["running"]


def require_closed(info):
    if desktop_running(info):
        raise SwitchError("Fully quit Codex first, then launch native speed mode from Codex Switch. Running chats are not closed automatically.")


def enrich_catalog(data):
    result = deepcopy(data)
    if not isinstance(result, dict) or not isinstance(result.get("models"), list):
        raise SwitchError("The active model catalog is invalid.")
    for entry in result["models"]:
        model = entry.get("slug")
        tiers = entry.setdefault("service_tiers", [])
        if not isinstance(tiers, list) or any(not isinstance(t, dict) for t in tiers):
            raise SwitchError("The active model catalog is invalid.")
        if model in FAST_MODELS and not any(t.get("id") in ("priority", "fast") for t in tiers):
            tiers.append({"id": "priority", "name": "Fast", "description": "Faster API processing; higher API price"})
        if model in ULTRA_MODELS and not any(t.get("id") == "ultrafast" for t in tiers):
            tiers.append({"id": "ultrafast", "name": "Ultrafast", "description": "Ultrafast API processing; higher API price"})
    return result


def prepare(service):
    """Separate catalog pointer, reversible and journaled; no default premium opt-in."""
    with lock(service.home):
        state = service.status()
        if state["mode"] != "api" or not state["api_ready"] or state["base_url"] != API_URL or state["profile_override"]:
            raise SwitchError("Native speed currently requires a ready direct OpenAI API connection without profile overrides.")
        if state["speed_enabled"]:
            raise SwitchError("Restore the direct API connection before enabling native speed mode.")
        original = service.config.read()
        doc = parse(original)
        profile = doc.get("profiles", {}).get(doc.get("profile"), {})
        if any(key in profile for key in MODEL_KEYS):
            raise SwitchError("The selected profile overrides model settings. Remove these overrides before applying a catalog.")
        connection = read_state(service.home)
        previous = doc.get("model_catalog_json")
        native = connection.get("native_speed")
        if native and native.get("catalog") != previous:
            raise SwitchError("The model catalog changed outside native mode; no configuration was overwritten.")
        if previous:
            path = Path(previous)
            if path.stat().st_size > 1024 * 1024:
                raise SwitchError("The active model catalog is too large.")
            data = json.loads(path.read_text("utf-8"))
        else:
            data = {"models": list(bundled_metadata(API_URL).values())}
        data = enrich_catalog(data)
        if state["model"] not in [m.get("slug") for m in data["models"]]:
            raise SwitchError("Sync and apply a catalog containing the current model before using native speed.")
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
        destination = service.home / "codex-switch" / "catalogs" / ("native-" + digest + ".json")
        atomic_json(destination, data)
        if "native_speed" not in connection:
            connection["native_speed"] = {"previous_catalog": previous,
                "connection_before": {k: deepcopy(connection[k]) for k in CATALOG_FIELDS if k in connection}}
        connection["native_speed"]["catalog"] = str(destination)
        if "account_settings" not in connection:
            connection["account_settings"] = {k: deepcopy(doc[k]) for k in MODEL_KEYS if k in doc}
            if "account_speed" in connection:
                account_speed = connection.pop("account_speed")
                if "service_tier" in account_speed:
                    connection["account_settings"]["service_tier"] = account_speed["service_tier"]
                else:
                    connection["account_settings"].pop("service_tier", None)
        connection.update(catalog=str(destination), active_catalog=str(destination),
            active_provider=state["provider"], catalog_provider=state["api_provider"], api_model=state["model"])
        updated = patch(original, lambda d: d.update(model_catalog_json=str(destination)))
        service._commit(original, updated, connection)


def restore(service):
    with lock(service.home):
        original = service.config.read()
        connection = read_state(service.home)
        native = connection.pop("native_speed", None)
        if not native:
            return
        doc = parse(original)
        active = doc.get("model_catalog_json") == native["catalog"]
        account = (doc.get("model_provider", "openai") == "openai" and "account_settings" not in connection
                   and connection.get("catalog") == native["catalog"])
        if not active and not account:
            raise SwitchError("The model catalog changed outside native mode; no configuration was overwritten.")
        previous = native.get("previous_catalog")
        def change(d):
            if not active:
                return
            if previous is None:
                d.pop("model_catalog_json", None)
            else:
                d["model_catalog_json"] = previous
        for field in CATALOG_FIELDS:
            if account and field in ("account_settings", "account_speed", "active_catalog", "active_provider"):
                continue
            if field in native.get("connection_before", {}):
                connection[field] = native["connection_before"][field]
            else:
                connection.pop(field, None)
        service._commit(original, patch(original, change), connection)


def report(service):
    info = installation()
    assets = inspect_archive(info["archive"], info["version"])
    return {"version": info["version"], "compatible": True, "asset_count": len(assets),
            "labels": sorted(required_labels(info["version"])), "native_menu_verified": False}


def runtime_path(service):
    return service.home / "codex-switch" / "native-runtime.json"


def request_path(service):
    return service.home / "codex-switch" / "native-request.json"


def process_running(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def runtime_status(service):
    """A recorded interception is historical evidence, never a live UI assertion."""
    try:
        path = runtime_path(service)
        if path.stat().st_size > 8192:
            return {"phase": "unknown"}
        value = json.loads(path.read_text("utf-8"))
        if not isinstance(value, dict):
            return {"phase": "unknown"}
        alive = process_running(value.get("host_pid"))
        phase = value.get("phase", "unknown")
        if phase in ("starting", "waiting_for_exit", "attached", "active") and not alive:
            phase = "closed"
        return {**value, "phase": phase, "host_alive": alive,
                "historical_record": True, "native_menu_verified": False}
    except (OSError, ValueError):
        return {"phase": "not_started"}


def wait_for_active(service, process, nonce, timeout=40, allow_pending=False):
    """Confirm activation, or return an explicitly requested pending state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = json.loads(runtime_path(service).read_text("utf-8"))
            if isinstance(value, dict) and value.get("nonce") == nonce:
                if value.get("phase") == "error":
                    raise SwitchError(value.get("message", "Native startup failed."))
                if value.get("phase") == "active":
                    return value
                if allow_pending and value.get("phase") in ("waiting_for_exit", "starting"):
                    return value
                if value.get("phase") == "closed":
                    raise SwitchError("Codex closed before the native speed adapter finished loading.")
        except (OSError, ValueError):
            pass
        if process.poll() is not None:
            break
        time.sleep(.1)
    raise SwitchError("Native speed modules were not confirmed. Check native status before retrying; no running chat was closed.")


def launch(service):
    if service.home != (Path.home() / ".codex").resolve():
        raise SwitchError("Native launch currently supports the default Codex home only.")
    info = installation()
    inspect_archive(info["archive"], info["version"])
    state = service.status()
    if state["speed_enabled"]:
        from .speed import select
        select(service, "off")
        state = service.status()
    if state["mode"] != "api" or not state["api_ready"] or state["base_url"] != API_URL or state["profile_override"]:
        raise SwitchError("Native speed currently requires a ready direct OpenAI API connection without profile overrides.")
    with lock(service.home / "codex-switch" / "native-launch"):
        recorded = runtime_status(service)
        if recorded.get("host_alive") and recorded.get("phase") in ("waiting_for_exit", "starting", "attached", "active"):
            return recorded
        nonce = secrets.token_hex(16)
        atomic_json(request_path(service), {"nonce": nonce, "provider": state["provider"],
                    "version": info["version"], "at": time.time()})
        command, prefix = service.helper
        process = subprocess.Popen([command, *prefix, "--codex-home", str(service.home), "native-host", "--nonce", nonce],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"), creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        return wait_for_active(service, process, nonce, allow_pending=True)


def cancel_launch(service):
    with lock(service.home / "codex-switch" / "native-launch"):
        state = runtime_status(service)
        if state.get("host_alive") and state.get("phase") in ("attached", "active"):
            raise SwitchError("Fully quit Codex before disabling the running native adapter.")
        request_path(service).unlink(missing_ok=True)


def launch_requested(service, nonce):
    try:
        path = request_path(service)
        if path.stat().st_size > 8192:
            return False
        request = json.loads(path.read_text("utf-8"))
        state = service.status()
        return (request.get("nonce") == nonce and state["mode"] == "api"
                and state["provider"] == request.get("provider") and state["api_ready"]
                and state["base_url"] == API_URL and not state["profile_override"] and not state["speed_enabled"])
    except (OSError, ValueError, AttributeError):
        return False


def wait_for_exit(service, info, nonce, status, timeout=3600):
    """Queue one explicit native launch without closing any existing chat."""
    deadline = time.monotonic() + timeout
    waiting = False
    while True:
        if not launch_requested(service, nonce):
            status("cancelled")
            return False
        if not desktop_running(info):
            return True
        if not waiting:
            status("waiting_for_exit", version=info["version"])
            waiting = True
        if time.monotonic() >= deadline:
            raise SwitchError("Native launch timed out while waiting for Codex to quit. Enable it again when ready.")
        time.sleep(1)


ACTIVATE = r'''
$v=[Console]::In.ReadToEnd() | ConvertFrom-Json;
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[ComImport,Guid("2e941141-7f97-4756-ba1d-9decde894a3d"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ISwitchActivation {
 [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id,[MarshalAs(UnmanagedType.LPWStr)] string args,uint options,out uint pid);
 [PreserveSig] int ActivateForFile(string id,IntPtr items,string verb,out uint pid);
 [PreserveSig] int ActivateForProtocol(string id,IntPtr items,out uint pid);
}
[ComImport,Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")] class SwitchActivation {}
public class SwitchLauncher {
 public static uint Launch(string id,string args) {uint pid; var app=(ISwitchActivation)new SwitchActivation();
 Marshal.ThrowExceptionForHR(app.ActivateApplication(id,args,0,out pid)); return pid;}
}
'@;
$taskPid=[SwitchLauncher]::Launch($v.aumid,$v.arguments);
Start-Sleep -Milliseconds 200;
$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskPid);
if (!$p -or !$p.ExecutablePath -or !$p.ExecutablePath.StartsWith($v.root+'\',[StringComparison]::OrdinalIgnoreCase) -or !$p.CommandLine.Contains($v.arguments)) {throw 'ownership'};
@{pid=$taskPid} | ConvertTo-Json -Compress
'''


def local_ws(url, port):
    parsed = urlsplit(url)
    if (parsed.scheme != "ws" or parsed.hostname != "127.0.0.1" or parsed.port != port
            or not parsed.path.startswith("/devtools/") or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise SwitchError("Native debugging endpoint was not a verified loopback target.")
    return url


class CDP:
    def __init__(self, url, port):
        self.timeout_error = websocket.WebSocketTimeoutException
        self.ws = websocket.create_connection(local_ws(url, port), timeout=2, suppress_origin=True, http_no_proxy=["127.0.0.1"])
        self.counter = 0
        self.replies = {}
        self.events = queue.Queue(maxsize=512)
        self.mutex = threading.Lock()
        self.closed = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while not self.closed:
                try:
                    value = json.loads(self.ws.recv())
                except (TimeoutError, self.timeout_error):
                    continue
                if "id" in value:
                    with self.mutex:
                        reply = self.replies.get(value["id"])
                    if reply:
                        reply.put_nowait(value)
                elif value.get("method") == "Fetch.requestPaused":
                    # Network.enable is needed for cache control, but its many
                    # notifications are not consumed by the adapter. Enqueuing
                    # them can overflow the bounded queue during a page reload.
                    self.events.put_nowait(value)
        except Exception:
            self.closed = True

    def call(self, method, params=None):
        with self.mutex:
            self.counter += 1
            identifier = self.counter
            response = queue.Queue(maxsize=1)
            self.replies[identifier] = response
        try:
            self.ws.send(json.dumps({"id": identifier, "method": method, "params": params or {}}))
            value = response.get(timeout=6)
            if "error" in value:
                raise SwitchError("Native adapter protocol failed; menu activation is unverified.")
            return value.get("result", {})
        finally:
            with self.mutex:
                self.replies.pop(identifier, None)

    def close(self):
        self.closed = True
        self.ws.close()


def wait_for_document(client, timeout=25):
    """Do not reload while Electron is still performing its initial navigation."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not client.closed:
        try:
            response = client.call("Runtime.evaluate", {
                "expression": 'location.protocol === "app:" && document.readyState === "complete"',
                "returnByValue": True,
            })
            if response.get("result", {}).get("value") is True:
                return
        except (SwitchError, queue.Empty):
            if client.closed:
                break
            # The execution context can disappear during the initial navigation.
        time.sleep(.2)
    raise SwitchError("Native client did not finish loading; the menu remains unverified.")


def asset_key(url):
    parsed = urlsplit(url)
    if parsed.scheme != "app" or parsed.netloc != "-" or parsed.query or parsed.fragment:
        return None
    path = unquote(parsed.path)
    return path.removeprefix("/webview") if path.startswith(("/assets/", "/webview/assets/")) else None


def intercept(client, event, assets):
    params = event["params"]
    identifier = params["requestId"]
    resource = assets.get(asset_key(params["request"]["url"]))
    if not resource:
        client.call("Fetch.continueRequest", {"requestId": identifier})
        return set()
    response = client.call("Fetch.getResponseBody", {"requestId": identifier})
    raw = base64.b64decode(response["body"], validate=True) if response.get("base64Encoded") else response["body"].encode()
    if hashlib.sha256(raw).hexdigest() != resource["sha256"]:
        client.call("Fetch.continueRequest", {"requestId": identifier})
        raise SwitchError("Native client resource changed; the adapter stopped without modifying installed files.")
    headers = [h for h in params.get("responseHeaders", []) if h["name"].lower() not in ("content-length", "content-encoding", "etag")]
    client.call("Fetch.fulfillRequest", {"requestId": identifier, "responseCode": params.get("responseStatusCode", 200),
        "responseHeaders": headers, "body": base64.b64encode(resource["body"]).decode()})
    return resource["labels"]


def host(service, nonce):
    clients = {}
    status_lock = threading.Lock()
    last_phase = "starting"
    def status(phase, **values):
        nonlocal last_phase
        with status_lock:
            if last_phase == "error" or (last_phase == "active" and phase == "attached"):
                return
            last_phase = phase
            atomic_json(runtime_path(service), {"phase": phase, "nonce": nonce, "host_pid": os.getpid(),
                "at": time.time(), "native_menu_verified": False, **values})
    try:
        info = installation()
        assets = inspect_archive(info["archive"], info["version"])
        expected_labels = required_labels(info["version"])
        if not wait_for_exit(service, info, nonce, status):
            return
        status("starting", version=info["version"])
        if installation()["version"] != info["version"]:
            raise SwitchError("Codex changed while waiting. Enable native speeds again for the current version.")
        require_closed(info)
        prepare(service)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        args = f"--remote-debugging-port={port} --remote-debugging-address=127.0.0.1"
        owned = powershell(ACTIVATE, {**info, "arguments": args})
        opener = build_opener(ProxyHandler({}), NoRedirect)
        deadline = time.monotonic() + 25
        attached = False
        while True:
            try:
                with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                    targets = json.loads(response.read(1024 * 1024))
                if not isinstance(targets, list):
                    raise ValueError()
            except (OSError, ValueError):
                if time.monotonic() > deadline:
                    if not attached:
                        raise SwitchError("No supported native renderer appeared. Native menu activation is unverified.")
                    break
                time.sleep(.2)
                continue
            for target in targets:
                if target.get("type") != "page" or not target.get("url", "").startswith("app://-/"):
                    continue
                identifier = target["id"]
                if identifier in clients:
                    continue
                client = CDP(target["webSocketDebuggerUrl"], port)
                clients[identifier] = client
                status("attached", app_pid=owned["pid"], version=info["version"], native_menu_verified=False)
                def run(c=client):
                    try:
                        c.call("Network.enable")
                        c.call("Network.setCacheDisabled", {"cacheDisabled": True})
                        wait_for_document(c)
                        c.call("Fetch.enable", {"patterns": [{"urlPattern": "app://-/*", "resourceType": "Script", "requestStage": "Response"}]})
                        c.call("Page.reload", {"ignoreCache": True})
                        labels = set()
                        startup_deadline = time.monotonic() + 30
                        while not c.closed:
                            if last_phase != "active" and labels != expected_labels and time.monotonic() > startup_deadline:
                                raise SwitchError("Native speed modules did not finish loading. Enable the adapter again after quitting Codex.")
                            try:
                                event = c.events.get(timeout=1)
                            except queue.Empty:
                                continue
                            if event.get("method") == "Fetch.requestPaused":
                                labels.update(intercept(c, event, assets))
                                if labels == expected_labels:
                                    status("active", app_pid=owned["pid"], version=info["version"], observed_labels=sorted(labels))
                    except Exception as error:
                        message = str(error) if isinstance(error, SwitchError) else "Native runtime adaptation failed. Close Codex to remove the session adapter."
                        status("error", message=message)
                        try:
                            c.call("Fetch.disable")
                        except Exception:
                            pass
                    finally:
                        c.close()
                threading.Thread(target=run, daemon=True).start()
                attached = True
            if attached and all(c.closed for c in clients.values()):
                break
            if not attached and time.monotonic() > deadline:
                raise SwitchError("No supported native renderer appeared. Native menu activation is unverified.")
            deadline = time.monotonic() + 4 if attached else deadline
            time.sleep(.4)
        status("closed")
    except Exception as error:
        message = str(error) if isinstance(error, SwitchError) else "Native startup failed; installed files were not modified."
        status("error", message=message)
    finally:
        for client in clients.values():
            client.close()
        try:
            if json.loads(request_path(service).read_text("utf-8")).get("nonce") == nonce:
                request_path(service).unlink(missing_ok=True)
        except (OSError, ValueError, AttributeError):
            pass
