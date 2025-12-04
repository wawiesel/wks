# Agent 1 Goal: Fix Formatting and Basic Linting

**Agent:** Agent 1
**Branch:** `agent1-formatting`
**Status:** 🟡 PENDING ASSIGNMENT

---

## Objective

Fix all auto-fixable formatting and basic linting issues to establish a clean baseline before enabling additional rules.

## Tasks

### 1. Fix Formatting Issues
- Run `ruff format` to fix all formatting issues
- Ensure all files are properly formatted
- Verify no formatting changes break functionality

### 2. Fix Basic Linting Errors (Current Rules: E, F, I, B)

Fix the following categories of errors:

#### Unused Variables (F841)
- Remove or use unused variables in:
  - `tests/integration/test_vault_controller_full.py:202` - `mock_vault_class`
  - `tests/test_cli_main.py:44` - `exit_code`
  - `tests/test_git_vault_watcher.py:95` - `new_file`
  - `tests/test_git_vault_watcher.py:224` - `changes`
  - `tests/test_transform.py:475` - `computed_key`
  - `tests/test_vault_git_watcher_extended.py:95` - `new_file`
  - `tests/test_vault_git_watcher_extended.py:224` - `changes`
  - `tests/test_vault_indexer.py:179` - `records`
  - `tests/test_vault_symlinks.py:269` - `result`
  - `tests/unit/test_file_url_conversion.py:59` - `mongo_client`
  - `tests/unit/test_file_url_conversion.py:158` - `records`
  - `tests/unit/test_transform_config.py:38` - `cache_config`
  - `wks/transform/engines.py:82` - `result`
  - `wks/vault/obsidian.py:148` - `new_rel_legacy`

#### Unused Loop Variables (B007)
- Rename unused loop variables to `_` in:
  - `tests/integration/test_vault_controller_full.py:138` - `for i in range(50)`
  - `tests/integration/test_vault_controller_full.py:168` - `for i in range(8)`
  - `tests/integration/test_vault_controller_full.py:174` - `for i in range(2)` (needs fix for undefined `i`)

#### Ambiguous Variable Names (E741)
- Rename ambiguous variable `l` to `label` in:
  - `tests/test_wks_display_service.py:73, 74, 98, 111`

#### Unused Imports (F401)
- Remove unused import in:
  - `wks/display/cli.py:9` - `from rich import print as rprint`

#### Line Length Violations (E501)
- Break long lines (>120 chars) in:
  - `wks/db_helpers.py:25, 30, 51, 65, 92`
  - `wks/mcp_server.py:152, 191, 284`
  - `wks/monitor/config.py:39, 44, 49, 54, 59, 64, 69, 80, 86, 97, 102, 107, 137`
  - `wks/monitor/controller.py:55, 183`
  - `wks/monitor/status.py:27, 31, 35, 106`
  - `wks/vault/config.py:38, 43, 48, 53, 64, 70, 109`

#### Exception Handling (B904)
- Add `from err` or `from None` to exception raises in:
  - `wks/config.py:111, 134`
  - `wks/daemon.py:958, 960`
  - `wks/mcp_server.py:317`

## Success Criteria

- [ ] All files pass `ruff format --check`
- [ ] All files pass `ruff check` with current rules (E, F, I, B)
- [ ] All tests still pass (694 tests)
- [ ] No functionality changes (only formatting/linting fixes)

## Branch Strategy

1. Create branch from `2025-12-03_linting-baseline`
2. Make fixes
3. Run tests to verify
4. Create PR targeting `2025-12-03_linting-baseline`
5. Wait for Orchestrator review and merge

## Notes

- Use `ruff format --fix` and `ruff check --fix` where possible
- For line length, prefer breaking at logical points (e.g., after commas, before operators)
- For exception handling, use `raise ... from err` when the original exception context is important, `raise ... from None` when it's not
