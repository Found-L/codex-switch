"""Execute installed native modules with fixture hooks; no activation or inference."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.native import MODULE, SAVED_GATE, adapt, inspect_archive, installation, pinned_assets

info = installation()
assets = inspect_archive(info["archive"], info["version"])
required = {"ipV4", "PAzX", "eWgO", "l2g8"}
modules = {}
with Path(info["archive"]).open("rb") as stream:
    _, header_size, _, length = struct.unpack("<4I", stream.read(16))
    tree = json.loads(stream.read(length))["files"]["webview"]["files"]["assets"]["files"]
    sources = []
    def entries(tree):
        for name, entry in tree.items():
            if "files" in entry:
                yield from entries(entry["files"])
            else:
                yield name, entry
    for name, entry in entries(tree):
        if name.endswith(".js") and "offset" in entry and entry.get("size", 0) <= 20 * 1024 * 1024:
            stream.seek(8 + header_size + int(entry["offset"]))
            source = stream.read(entry["size"]).decode()
            if any(name + '(' in source for name in required):
                sources.append(source)
for source in sources:
    source, _ = adapt(source)
    matches = list(MODULE.finditer(source))
    for index, match in enumerate(matches):
        if match[1] in required:
            start = match.start() + (source[match.start()] in ',{')
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            modules.setdefault(match[1], source[start:end])
if set(modules) != required:
    raise SystemExit("Required installed modules could not be extracted: " + str(required - set(modules)))
execution_asset, _ = pinned_assets(info["version"])
if execution_asset:
    source = assets["/" + execution_asset.removeprefix("webview/")]["body"].decode("utf-8")
    start = source.index(SAVED_GATE)
    modules["__saved"] = source[start:source.index("})},async writeServiceTier", start)]
    start = source.index('let{account:t,requiresOpenaiAuth:__codexSwitchRequiresAuth}=')
    modules["__submit"] = source[start:source.index("})(),d?.usePermissionSelection", start)]
node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for this developer-only check.")
result = subprocess.run([node, str(Path(__file__).with_suffix(".cjs"))],
    input=json.dumps(modules), text=True, capture_output=True, encoding="utf-8", timeout=30)
if result.returncode:
    raise SystemExit(result.stderr)
print(json.dumps({"version": info["version"], "checks": json.loads(result.stdout),
                  "native_ui_verified": False, "paid_requests": 0}))
