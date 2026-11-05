# Catalog loading correction

Observed: the running desktop retained its eight built-in options despite a saved one-entry custom catalog. The global model had also changed to a model absent from that catalog. Official remote metadata returned only three visible exact matches and incorrectly relegated current built-ins to basic templates.

Fix: supplement exact official API list matches using the installed client's bundled catalog in an empty home; never infer API access or import account caches. Label bundled and remote sources separately. Detect saved-catalog/configured-model mismatch. Replace activation claims with startup-only loading guidance: fully quit and restart the desktop. Selection is a replacement catalog, not a live desktop mirror.

Validation: 50 tests and source QML checks passed. Isolated app-server accepted nine bundled entries and the actual saved one-entry catalog, with no inference. Running-desktop reload is intentionally unverified; no user Codex restart or selection changes.
