# NEXT priorities for WKS: A Roadmap of Sorts

## Use URI Consistently Everywhere [P1]

- [ ] Audit all `wks/` source code for string-based path/URI handling
- [ ] Replace all `str` path parameters with `URI` type in API functions
- [ ] Update internal functions to use `URI` instead of `Path` or `str` where appropriate
- [ ] Ensure all database operations use `URI` type for URI fields
- [ ] Update utility functions (`convert_to_uri`, `uri_to_path`, etc.) to work with `URI` type
- [ ] Remove any remaining inline URI string formatting (`f"file://..."`)
- [ ] Add type hints and validation to enforce `URI` usage throughout the codebase

## Implement Diff (bsdiff and Meyers) [P1]

- [ ] Implement bsdiff algorithm for binary diff operations
- [ ] Implement Myers diff algorithm for text diff operations
- [ ] Create `wks/api/diff/` domain with proper API structure
- [ ] Add CLI commands for diff operations
- [ ] Add MCP support for diff operations
- [ ] Write comprehensive tests for diff algorithms
- [ ] Document diff capabilities and use cases

## Fully Implement Requirements Traceability for All Domains [P1]

- [ ] Create requirement files (`qa/reqs/*.yml`) for all domains
- [ ] Add Requirements blocks to all test docstrings
- [ ] Ensure all requirements are linked to tests
- [ ] Update traceability audit to show 100% coverage for all domains
- [ ] Document traceability workflow in CONTRIBUTING.md
- [ ] Automate traceability validation in CI

## Increase Test and Mutation Coverage [P1]

- [ ] Achieve 100% test coverage for all domains
- [ ] Achieve ≥90% mutation score for all domains
- [ ] Implement Subprocess Tracing for coverage
    - Configure `.coveragerc` with `concurrency = multiprocessing`
    - Use `sitecustomize.py` to ensure all child processes are tracked
    - Merge coverage data files before reporting
- [ ] Handle System-Level Error Branches
    - Use FUSE or LD_PRELOAD to simulate IO failures (disk full, hardware errors)
    - Refactor system-heavy modules for dependency injection (FS/Process abstractions)
- [ ] Verify Signal Resilience
    - Send real SIGTERM/SIGINT in tests with proper synchronization
- [ ] Confirm `.coveragerc` has `fail_under = 100` once roadmap items are completed

## Refactor to Strong URI Type (Legacy - Mostly Complete) [P1]

- [x] Establish `URI` value object and update `link show` boundary
- [x] Refactor all API functions to use `URI` type instead of `str`
- [x] Implement canonical existence checks on `URI` (e.g., `uri.path.exists()`) where applicable
- [x] Update `cmd_check`, `cmd_sync`, etc. to enforce `URI` strictness

## Complete 2025-12-04 Campaign [P1]

- [ ] Review MCP domain - determine if installation commands need output schemas
- [ ] Update integration tests to use `wks.cli.*` paths (moved from `wks.api.*.app`)
- [ ] Run full test suite and verify 100% coverage for config, database, monitor, daemon
- [ ] Update API READMEs to document schema-driven approach

## Centralize Configs in Conftest [P1]

- [ ] Audit all tests (especially integration tests like `test_linux_service_install.py`) for hardcoded config dictionaries
- [ ] Replace hardcoded dicts with fixtures from `tests/conftest.py` (e.g. `minimal_config_dict`)
- [ ] Ensure `conftest.py` is the single source of truth for test configuration structures

## MCP/CLI Consistency Review [P1]

- [ ] wksm_monitor (controller needs review)
- [ ] wksm_vault (needs review)
- [ ] wksm_transform (needs review)
- [ ] wksm_cat (needs review)
- [ ] wksm_diff (needs review)
- [ ] Monitor status must call database API, not MongoClient directly

## Refactor Monitor Module [P2]

- [ ] Introduce `Monitor.py` (Facade) and `_AbstractImpl.py`
- [ ] Move domain logic out of `cmd_*.py` into `Monitor` class
- [ ] Ensure `cmd_` files do not access `Database` directly
- [ ] Add `prune_frequency_secs` configuration option

## Test Quality [P2]

- [ ] Revisit test code for readability and simplicity
- [ ] Ensure tests map directly to SPEC.md capabilities

## Link Module Improvements [P3]

- [ ] Implement robust relative path resolution in link check (outside vault context)
- [ ] Implement remote URL validation in link sync (http/https targets)

## Vault Backend Hooks [P3]

- [ ] Implement backend-specific operations in vault sync (e.g., symlink management for Obsidian)
- [ ] Add event collapsing for daemon filesystem watcher (move chains, create+delete pairs)

## MCP Schema Generation [P3]

- [ ] Implement full Typer command parameter parsing in `_get_typer_command_schema.py`
- [ ] Implement index and search commands

## Implement Patterns Capability [P3]

- [ ] Implement patterns capability

## Tutorial Completion [P3]

- [ ] Complete `docs/tutorials/01-walkthrough/walkthrough.md` with Log commands
