# Next Steps

## Priority 1

### Complete 2025-12-04 Campaign

- [ ] Review MCP domain - determine if installation commands need output schemas
- [ ] Update integration tests to use `wks.cli.*` paths (moved from `wks.api.*.app`)
- [ ] Run full test suite and verify 100% coverage for config, database, monitor, daemon
- [ ] Update API READMEs to document schema-driven approach

### Centralize Configs in Conftest

- [ ] Audit all tests (especially integration tests like `test_linux_service_install.py`) for hardcoded config dictionaries
- [ ] Replace hardcoded dicts with fixtures from `tests/conftest.py` (e.g. `minimal_config_dict`)
- [ ] Ensure `conftest.py` is the single source of truth for test configuration structures

### MCP/CLI Consistency Review

- [ ] wksm_monitor (controller needs review)
- [ ] wksm_vault (needs review)
- [ ] wksm_transform (needs review)
- [ ] wksm_cat (needs review)
- [ ] wksm_diff (needs review)
- [ ] Monitor status must call database API, not MongoClient directly

### Test Coverage Roadmap to 100%

- [x] Achieve 80%+ coverage for `daemon`, `transform`, `monitor`, and `vault`
- [ ] Implement Subprocess Tracing
    - Configure `.coveragerc` with `concurrency = multiprocessing`
    - Use `sitecustomize.py` to ensure all child processes are tracked
    - Merge coverage data files before reporting
- [ ] Handle System-Level Error Branches
    - Use FUSE or LD_PRELOAD to simulate IO failures (disk full, hardware errors)
    - Refactor system-heavy modules for dependency injection (FS/Process abstractions)
- [ ] Verify Signal Resilience
    - Send real SIGTERM/SIGINT in tests with proper synchronization
- [ ] Confirm `.coveragerc` has `fail_under = 100` once roadmap items are completed

---

## Priority 2

### Refactor Monitor Module

- [ ] Introduce `Monitor.py` (Facade) and `_AbstractImpl.py`
- [ ] Move domain logic out of `cmd_*.py` into `Monitor` class
- [ ] Ensure `cmd_` files do not access `Database` directly
- [ ] Add `prune_frequency_secs` configuration option

### Test Quality

- [ ] Revisit test code for readability and simplicity
- [ ] Ensure tests map directly to SPEC.md capabilities

---

## Priority 3

### Implement Diff and Transform CLI/MCP

- [ ] Create `wks/api/diff/app.py` and expose via CLI
- [ ] Create `wks/api/transform/app.py` and expose via CLI

### Link Module Improvements

- [ ] Implement robust relative path resolution in link check (outside vault context)
- [ ] Implement remote URL validation in link sync (http/https targets)

### Vault Backend Hooks

- [ ] Implement backend-specific operations in vault sync (e.g., symlink management for Obsidian)
- [ ] Add event collapsing for daemon filesystem watcher (move chains, create+delete pairs)

### MCP Schema Generation

- [ ] Implement full Typer command parameter parsing in `_get_typer_command_schema.py`

- [ ] Implement index and search commands

---

## Priority 4

- [ ] Implement patterns capability

---

## Priority 5

### Tutorial Completion

- [ ] Complete `docs/tutorials/01-walkthrough/walkthrough.md` with Log commands
