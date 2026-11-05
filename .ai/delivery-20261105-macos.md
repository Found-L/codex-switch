# macOS delivery

Commit summary: `feat: deliver native macOS account/API switching with Keychain, menu bar and user-local CLI`.

The macOS app and provider helper use one Keychain code identity. GUI secrets travel through pipes; credentials do not enter argv, TOML or backups. Key rotation preserves the access list. Separate arm64/Intel DMGs include the native application, bundled CLI, original ICNS/template artwork and licenses. The terminal page installs a managed launcher and zsh/bash PATH blocks; cleanup preserves account login, backups and unrelated shell contents.

Validation: Windows plus native macOS 15 arm64/x86_64 CI all passed at implementation commit 2209fe6 (run 41982563204). 28 tests, source/frozen QML, actual frozen Mac GUI-to-helper Keychain access, CLI setup/auth/rotation, readonly-DMG refusal, copied installation with Unicode/quotes, shell PATH and safe uninstall were exercised. No model requests were sent.

Distribution: v0.3.0 includes Windows installer/portable ZIP and both macOS DMGs with consolidated checksums. Developer ID signing and notarytool/stapling are optional when repository secrets exist. Current Mac artifacts are ad-hoc signed and unnotarized. User-side menu-bar interactions, system permission dialogs and animation perception on Mac remain manual acceptance items; macOS 14 is the Qt baseline, while CI uses macOS 15.
