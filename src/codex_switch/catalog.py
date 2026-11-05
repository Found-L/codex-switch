"""Credential-safe model discovery and explicit, conservative Codex catalogs.

No inference requests are made. A listed model is never marked as tested.
Catalog wire baseline: openai/codex rust-v0.162.1 ModelsResponse.
"""
from copy import deepcopy
import json
import re
import shutil
import subprocess
import os
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

from .errors import SwitchError
from .config import API_URL

MAX_BYTES = 1024 * 1024
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def classification(model):
    """Name hints for browsing, not detection of server capabilities."""
    name = model.lower()
    if re.search(r"(^|[-_/.])(audio|tts|realtime|transcribe|transcription|translate|whisper|embedding|embeddings|moderation|moderations|image|images|dall-e|sora|rerank|reranker)([-_/.]|$)", name):
        return "excluded"
    if re.search(r"(^|[/_-])(gpt-[456]|o[134](?:[-/]|$)|chat-latest|chatgpt|codex|claude|deepseek|qwen|glm|kimi|codestral|devstral|code|coding|minimax|gemini)", name):
        return "candidate"
    return "other"


def official_metadata(base_url, key):
    """Optional authoritative catalog. Never disclose gateway keys to OpenAI."""
    if base_url != API_URL:
        return {}, "not_applicable"
    executable = shutil.which("codex")
    if not executable:
        return {}, "client_not_found"
    try:
        import os
        version = subprocess.run([executable, "--version"], capture_output=True, timeout=4,
                                 **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        match = re.search(rb"codex-cli (\d+\.\d+\.\d+)", version.stdout)
        if not match:
            return {}, "client_not_found"
        url = "https://chatgpt.com/backend-api/codex/models?client_version=" + match[1].decode()
        request = Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
        with build_opener(NoRedirect).open(request, timeout=12) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or key.encode("utf-8") in raw:
            return {}, "unavailable"
        data = json.loads(raw)
        entries = data.get("models") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return {}, "unavailable"
        result = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("slug"), str) or not entry.get("supported_in_api") or entry.get("visibility") != "list":
                continue
            messages = entry.get("model_messages") or {}
            levels = entry.get("supported_reasoning_levels")
            if (not isinstance(entry.get("supported_reasoning_levels"), list)
                    or not isinstance(entry.get("truncation_policy"), dict)
                    or any(not isinstance(r, dict) or r.get("effort") not in EFFORTS for r in levels)
                    or not all(k in entry for k in ("display_name", "shell_type", "priority", "support_verbosity", "experimental_supported_tools"))
                    or not (isinstance(entry.get("base_instructions"), str)
                            or isinstance(messages, dict) and isinstance(messages.get("instructions_template"), str))):
                continue
            result[entry["slug"]] = entry
        return result, "available" if result else "unavailable"
    except HTTPError as error:
        status = "unavailable_http_" + str(error.code)
        error.close()
        return {}, status
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired):
        return {}, "unavailable"


def bundled_metadata(base_url):
    """Read this client's static defaults in an empty home; never reuse account caches.

    Only official routes may inherit OpenAI's instructions. A bundled entry is
    a versioned template, not proof of access for the current API key.
    """
    if base_url != API_URL:
        return {}
    executable = shutil.which("codex")
    if not executable:
        return {}
    try:
        with tempfile.TemporaryDirectory(prefix="codex-switch-bundled-") as home:
            env = dict(os.environ, CODEX_HOME=home)
            for name in ("OPENAI_API_KEY", "CODEX_API_KEY"):
                env.pop(name, None)
            result = subprocess.run([executable, "debug", "models", "--bundled"],
                                    capture_output=True, timeout=8, env=env, cwd=home,
                                    **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        if result.returncode or len(result.stdout) > MAX_BYTES:
            return {}
        data = json.loads(result.stdout)
        return {m["slug"]: m for m in data.get("models", [])
                if isinstance(m, dict) and isinstance(m.get("slug"), str)
                and m.get("visibility") == "list" and m.get("supported_in_api")
                and isinstance(m.get("supported_reasoning_levels"), list)}
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired):
        return {}


def enrich_models(models, entries, bundled=None):
    bundled = bundled or {}
    for model in models:
        entry = entries.get(model["id"]) or bundled.get(model["id"])
        model["category"] = classification(model["id"])
        # Exact official ID only. Aliases and gateway entries keep basic metadata.
        if entry and model["category"] != "excluded":
            model["official_entry"] = deepcopy(entry)
            model["metadata_source"] = "official" if model["id"] in entries else "bundled"
            if not model.get("manual_capabilities"):
                model["context_window"] = entry.get("context_window") or 32768
                model["reasoning"] = [r["effort"] for r in entry["supported_reasoning_levels"]]
                model["images"] = "image" in entry.get("input_modalities", [])
            model["category"] = "candidate"
        else:
            if model.get("official_entry") and not model.get("manual_capabilities"):
                model.update(context_window=32768, reasoning=[], images=False)
            model.pop("official_entry", None)
            model.pop("metadata_source", None)
            if (entries or bundled) and model["category"] != "excluded":
                model["category"] = "other"
        if model["category"] == "excluded":
            model["enabled"] = False
    return models


def endpoint(value):
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")))
        if (not valid or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port == 0
                or any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError()
    except ValueError:
        raise SwitchError("Use an HTTPS API base URL without credentials, query or fragment (HTTP only for loopback).") from None
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def discover(base_url, key):
    """GET only, one trusted origin, bounded response, no server error body echoed."""
    request = Request(endpoint(base_url) + "/models", headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with build_opener(NoRedirect).open(request, timeout=12) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise SwitchError("Model list exceeds 1 MiB.")
        data = json.loads(raw)
    except HTTPError as error:
        code = error.code
        error.close()
        raise SwitchError("Model discovery failed (HTTP " + str(code) + "). Check the endpoint and token permissions.") from None
    except (URLError, OSError, UnicodeError, ValueError):
        raise SwitchError("Cannot read the model list. Check the API address, certificate and network.") from None
    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list) or len(entries) > 2000:
        raise SwitchError("Expected an OpenAI-format model list with a data array (maximum 2000 entries).")
    result = {}
    for entry in entries:
        model = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(ord(c) < 32 for c in model):
            raise SwitchError("The gateway returned an invalid model ID.")
        # No guesses from names or owned_by: aliases can route to any upstream.
        result[model] = {"id": model, "enabled": False, "context_window": 32768,
                         "reasoning": [], "images": False, "status": "unverified"}
    if not result:
        raise SwitchError("No models were returned for this key. Check New API groups and token model limits.")
    return list(result.values())


def model_info(model, context_window, reasoning=(), images=False):
    if isinstance(context_window, bool) or not isinstance(context_window, int) or not 4096 <= context_window <= 4000000:
        raise SwitchError("Context window must be between 4096 and 4000000 tokens.")
    if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise SwitchError("Invalid model ID.")
    if not isinstance(reasoning, (list, tuple)) or any(e not in EFFORTS for e in reasoning) or len(set(reasoning)) != len(reasoning):
        raise SwitchError("Unsupported or duplicate reasoning level.")
    instructions = ("You are a coding assistant. Follow the user's instructions and repository guidance. "
                    "Use the provided tools to inspect and change files. Verify changes and report limitations honestly.")
    return {"slug": model, "display_name": model, "description": "Gateway model; compatibility not verified",
            "default_reasoning_level": reasoning[0] if reasoning else None,
            "supported_reasoning_levels": [{"effort": e, "description": e} for e in reasoning],
            "shell_type": "unified_exec", "visibility": "list", "supported_in_api": True,
            "priority": 0, "additional_speed_tiers": [], "service_tiers": [], "default_service_tier": None,
            "availability_nux": None, "upgrade": None, "base_instructions": instructions,
            "model_messages": {"instructions_template": instructions},
            "supports_reasoning_summary_parameter": False, "default_reasoning_summary": "none",
            "support_verbosity": False, "default_verbosity": None, "apply_patch_tool_type": None,
            "truncation_policy": {"mode": "tokens", "limit": 10000},
            "context_window": context_window, "effective_context_window_percent": 90,
            "experimental_supported_tools": [], "input_modalities": ["text", "image"] if images else ["text"]}


def make_catalog(candidates):
    models = []
    for model in candidates:
        if not model["enabled"]:
            continue
        if classification(model["id"]) == "excluded" or model.get("category") == "excluded":
            raise SwitchError("Audio, image, embedding and other non-coding models cannot be added to the Codex menu.")
        if model.get("official_entry"):
            entry = deepcopy(model["official_entry"])
            entry.update(visibility="list", upgrade=None)
            if model.get("manual_capabilities"):
                override = model_info(model["id"], model["context_window"], model["reasoning"], model["images"])
                for field in ("context_window", "supported_reasoning_levels", "input_modalities"):
                    entry[field] = override[field]
                if entry.get("default_reasoning_level") not in model["reasoning"]:
                    entry["default_reasoning_level"] = override["default_reasoning_level"]
        else:
            entry = model_info(model["id"], model["context_window"], model["reasoning"], model["images"])
        models.append(entry)
    if not models:
        raise SwitchError("Enable at least one coding model before applying the catalog.")
    return {"models": models}


def merge_discovery(fresh, previous):
    old = {m["id"]: m for m in previous}
    result = [deepcopy(old.get(m["id"], m)) for m in fresh]
    for model in result:
        if "manual_capabilities" not in model and not model.get("official_entry") and (model.get("context_window", 32768) != 32768 or model.get("reasoning") or model.get("images")):
            model["manual_capabilities"] = True
    return result
