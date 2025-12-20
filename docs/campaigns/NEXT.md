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

### Test Coverage

- [ ] Run coverage analysis to identify gaps
- [ ] Confirm `.coveragerc` has `fail_under = 100`
- [ ] Ensure all tests pass

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

- [ ] Implement index and search commands

---

## Priority 4

- [ ] Implement patterns capability

---

## Priority 5

### Tutorial Completion

- [ ] Complete `docs/tutorials/01-walkthrough/walkthrough.md` with Log commands
