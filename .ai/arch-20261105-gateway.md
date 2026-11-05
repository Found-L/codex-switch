# Gateway model catalogs

Roles are executed sequentially in the main thread, per multi-agent skill guardrails. Implementation is assigned to the implementation role below.

## Architecture / implementation assignment

- catalog.py: GET-only model discovery, pinned origin, no redirects, bounded JSON, explicit opt-in conservative ModelsResponse entries. No vendor inference from names; no inference probe or API key in files/argv.
- settings.py: atomic non-secret connection state and account model-setting snapshot.
- service.py: custom endpoint setup, endpoint/key binding, sync/configure/apply/reset, reversible account settings and immutable hashed catalogs. Retain official OpenAI default behavior unless catalog explicitly enabled.
- GUI/CLI: same service, asynchronous GUI actions; model settings and apply remain separate. No client restarts.
- Validate real local Codex app-server model/list with isolated config; mock HTTP and native isolated credential tests; frozen GUI/CLI and platform builds.

## Boundaries

List presence is not proven compatibility. No automatic capability detection, supplier identity guarantee, full native catalog import or third-party inference validation. Generated templates disable speed tiers. Schema baseline rust-v0.162.1; real local acceptance 0.166.0-alpha.6.
