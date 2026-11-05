# Gateway delivery

Suggested commit: feat: add custom API endpoints and opt-in Codex model catalogs

New API users can save one gateway URL/key, discover its model IDs, explicitly enable coding models and configure their capabilities, then apply a Codex picker catalog with a default model. Account model/catalog/reasoning/speed/context settings restore when switching back. Official OpenAI without a custom catalog retains its prior behavior.

Credential-safe GET discovery rejects redirects, bounds response size, and does not execute inference. Endpoint changes require an explicitly entered key; key rotation invalidates model metadata. Model-list presence is labeled unverified. Generic catalogs do not enable speed tiers or infer capabilities from model names. GUI and CLI share the same service.

Validation: 39 unit/integration tests; persistent frozen QML gateway flow; packaged CLI loopback gateway lifecycle; actual Codex 0.166.0-alpha.6 app-server model/list with two custom entries and no inference. Release builds validate Windows and native Apple Silicon/Intel macOS. User credentials/config and Codex process remain untouched.

Limitations: no paid API calls or third-party model acceptance; no full upstream catalog import; generated schema baseline rust-v0.162.1 requires version-specific verification. Manual macOS UI acceptance and Apple notarization remain separate.
