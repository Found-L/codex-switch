"""Credential-safe model discovery and explicit, conservative Codex catalogs.

No inference requests are made. A listed model is never marked as tested.
Catalog wire baseline: openai/codex rust-v0.162.1 ModelsResponse.
"""
from copy import deepcopy
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

from .errors import SwitchError

MAX_BYTES = 1024 * 1024
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


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
    models = [model_info(m["id"], m["context_window"], m["reasoning"], m["images"]) for m in candidates if m["enabled"]]
    if not models:
        raise SwitchError("Enable at least one coding model before applying the catalog.")
    return {"models": models}


def merge_discovery(fresh, previous):
    old = {m["id"]: m for m in previous}
    return [deepcopy(old.get(m["id"], m)) for m in fresh]
