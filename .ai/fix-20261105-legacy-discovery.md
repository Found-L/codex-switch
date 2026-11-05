# Legacy model discovery hotfix

Observed: installed status selected openai_api, api_ready=true, managed_key=false. The discovery service nevertheless rejected every provider except codex_switch_api. The UI enabled the action based on api_ready, then rendered the English exception over its bottom action.

Implementation: resolve an existing official-OpenAI legacy credential using its unique configured command, environment key or inline token. No shell interpolation or helper stderr is exposed, no credentials are copied into managed storage, and the external provider table remains untouched. Model catalog snapshots track their provider so legacy account roundtrips and cleanup are reversible. Discovery still rejects redirects and performs no inference. New/custom endpoints continue requiring an explicitly entered key.

UI: localized actionable errors, explicit empty-list guidance, no inactive blank form, reserved notice space. Guardrails: legacy endpoints remain restricted to the official API URL, auth ambiguity fails closed, and synchronization rechecks config/auth identity before writing results.

Validation: 42 tests; persistent QML/frozen smoke includes empty-state navigation and notification geometry. Live installed lookup uses the existing legacy helper only for GET model discovery, with configuration/login digests checked separately.
