# State sources and draft isolation

Global configuration, saved API catalog, editable selection, and desktop runtime were conflated. State comparison now exposes these separately; the default draft comes from the saved API default rather than whichever model an external GUI wrote to the global config. Saved catalogs remain visible in account mode. Search-empty states report the draft count and offer clearing.

The optional runtime reader attaches exclusively through the installed client's app-server proxy. It never starts its own server or sends turn/start; only initialize, model/list and thread/loaded/list are allowed. The output whitelists model IDs/count and marks foreground model/billing unknown. Current Windows default control access is unavailable. No desktop runtime integration is falsely claimed.

54 tests plus QML self-test passed, including draft-only adoption, independent runtime failures, private data exclusion and partial catalog handling. User config/login and current selection must be preserved during installation.
