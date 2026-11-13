"""Prove packaged QML resources/plugins, persistent controls and async switching work."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="codex-switch-gui-report-") as temporary:
    report = Path(temporary) / "result.json"
    native = "--native-keychain" in sys.argv[2:]
    # The native fixture also verifies the macOS Keychain and signed helper.
    timeout = 90 if native else 30
    result = subprocess.run([str(Path(sys.argv[1]).resolve()), "--self-test-keychain" if native else "--self-test", str(report)], timeout=timeout)
    if not report.is_file():
        raise SystemExit("Frozen GUI self-test did not complete.")
    data = json.loads(report.read_text("utf-8"))
    if result.returncode or not data.get("ok"):
        raise SystemExit("Frozen GUI startup failed: " + str(data.get("error_type")) + "; phase=" + str(data.get("phase", "unknown")))
    assert data["persistent_controls"] and data["async_switching"] and data["mini_window"]
    assert data["page_transition_no_overlap"]
    assert data["gateway_catalog_flow"]
    assert data["empty_model_guidance"] and data["notice_no_overlap"]
    assert data["search_multi_select"]
    assert data["state_comparison"]
    assert data["speed_help_read_only"]
    assert data["api_config_speed_entry"]
    assert data["native_launch_queue"]
    assert data["native_provider_preserved"]
    assert data["native_speed_entry"]
    assert data["version_visible"]
    assert data["native_keychain"] == native
    print("Packaged Qt " + data["qt"] + " GUI passed: persistent scene, async switching, mini window.")
