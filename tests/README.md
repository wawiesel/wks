# WKS Tests
- `tests/unit/`: deep service/core and per-command contract coverage
- `tests/integration/`: CLI, MCP, REST, and cross-module wiring
- `tests/smoke/`: installed entry-point checks for `wksc`, `wksm`, and `wksr`
- Keep command-level test mapping.
- Keep requirement trace blocks only where they are actually used.
- Run from `venv`, starting with `venv/bin/pytest`.
