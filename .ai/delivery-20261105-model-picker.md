# Model picker delivery

Problem: a raw list mixed audio, image and embedding models with coding candidates, and the UI asked users to provide capability settings without an authoritative source.

Result: a styled searchable multi-select picker with draft selections, default model and atomic apply/activate. Obvious non-coding names are hidden by default and blocked in the service. Unknown aliases remain accessible under All. Known official OpenAI metadata is fetched with the same API identity and client version, intersected by exact visible API-supported IDs, and preserved. Gateway credentials are never sent to OpenAI. Basic templates and manual overrides are explicitly labeled unverified; manual capability settings live in an advanced panel with restore-default support.

Validation: 47 service/integration tests; real QML search, drafts, batch apply, advanced edits, click-through protection and existing account/mini/notice behavior. Actual isolated Codex 0.166.0-alpha.6 app-server accepted the current 3 matching visible official entries and 2 custom templates with matching reasoning metadata. Only authenticated GET directory requests used the existing API credential, with no inference. Counts are a snapshot, not a hard-coded model allowlist.

Suggested commit: feat: add searchable model selection and official capability metadata

Limitations: no third-party inference compatibility guarantee, arbitrary gateway catalog import or desktop menu hot-refresh proof. The active user model/catalog is not changed by installation or discovery; selections take effect only on explicit apply.
