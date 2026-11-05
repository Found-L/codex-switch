# Model picker refinement

Implementation role assigned to the current agent. Review and delivery remain sequential in this thread.

- Replace the raw ComboBox with a styled, bounded searchable multi-select list. Keep a local draft, a default selection and one explicit apply operation; don't write config for every checkbox.
- Classify names as coding candidates, unknown aliases, or obvious non-coding families. Classification is a UI hint, never proof of compatibility. Block obvious non-coding entries from generated menus, retain unknown aliases in the all-model view.
- For the official OpenAI endpoint only, optionally retrieve the authenticated, version-matched Codex catalog and preserve exact-ID metadata/instructions. Never send gateway credentials to OpenAI. Fail gracefully to an explicitly labeled basic template; no hard-coded model capability tables.
- Move manual capability overrides into a separate advanced view with source labels and restore-auto support. Keep ordinary selection free of numeric inputs.
- Validate exclusions, token/provider identity isolation, metadata preservation and batch config rollback. Test the actual QML controls, actual Codex catalog reading, frozen builds and clean platform installs. Upgrade the local app without modifying the active model/catalog until the user applies selections.
