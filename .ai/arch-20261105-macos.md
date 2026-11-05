# macOS delivery

Implementation is assigned to the current agent, followed by review, documentation and release verification in the same thread.

Reuse the configuration service, persistent QML scene and CLI. Add Security.framework Keychain storage (no secret command arguments), POSIX file locks, native bundle/helper discovery and per-platform application-data paths. Keep Windows credential targets and behavior compatible. The packaged GUI delegates all Keychain access through pipes to the same helper binary used for CLI setup, auth and uninstall, avoiding separate ACL owners for read versus update/delete. Source development uses the Python caller identity.

Package separate Apple Silicon and Intel applications for macOS 14+, matching the Qt wheel baseline. A DMG contains the application and an Applications link. The application installs a managed user-local terminal launcher and shell PATH block without replacing unrelated files. Uninstallation detaches managed providers/keys and removes only managed terminal integration; account login and backups remain.

Windows and both macOS architectures must pass service tests, frozen GUI checks, native credential/helper roundtrips and installer lifecycle checks before tag publication. macOS CI uses an isolated temporary Keychain and homes. Add optional Developer ID signing/notarization when repository secrets exist; identify ad-hoc builds honestly otherwise. Native visual acceptance on a user's Mac remains separate from CI.
