# Test Refactor Campaign

## Overview

This campaign reorganizes the test suite into a 3-tier structure (smoke → unit → integration) and fixes all failing tests.

## Branch Structure

```
master
  └── test-refactor-campaign (integration branch)
        ├── test-refactor/smoke-and-structure (Agent 1)
        ├── test-refactor/unit-tests (Agent 2)
        └── test-refactor/integration-tests (Agent 3)
```

## Target Directory Structure

```
tests/
├── smoke/                    # Quick sanity checks (~30 seconds)
│   ├── test_cli_smoke.py
│   └── test_mcp_smoke.py
├── unit/                     # Isolated function tests (~1 minute)
│   ├── test_config.py
│   ├── test_priority.py
│   ├── test_cache.py
│   └── ...
├── integration/              # Cross-component tests (~5 minutes)
│   ├── test_daemon_lifecycle.py
│   ├── test_vault_workflow.py
│   └── test_monitor_to_db.py
├── conftest.py               # Shared fixtures
└── pytest.ini                # Markers configuration
```

## Agent Assignments

### Agent 1: Smoke Tests & Directory Structure
**Branch:** `test-refactor/smoke-and-structure`

**Tasks:**
1. Create `tests/unit/` and `tests/integration/` directories
2. Add `pytest.ini` with markers (`@pytest.mark.smoke`, `@pytest.mark.unit`, `@pytest.mark.integration`)
3. Move existing smoke tests, verify they pass
4. Update `conftest.py` with shared fixtures
5. Add `tests/README.md` documenting test organization

**Files to create/modify:**
- `tests/pytest.ini`
- `tests/README.md`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/conftest.py`

**Success criteria:**
- `pytest tests/smoke/ -v` passes
- Directory structure in place
- Markers configured

---

### Agent 2: Unit Tests
**Branch:** `test-refactor/unit-tests`

**Tasks:**
1. Move pure unit tests to `tests/unit/`
2. Ensure all moved tests pass
3. Add `@pytest.mark.unit` decorator to tests
4. Fix any broken unit tests
5. Target: All tests in `tests/unit/` pass with no external dependencies

**Files to move:**
- `test_config.py` → `tests/unit/`
- `test_priority.py` → `tests/unit/`
- `test_transform_cache.py` → `tests/unit/`
- `test_transform_config.py` → `tests/unit/`
- `test_diff_config.py` → `tests/unit/`
- `test_monitor_config.py` → `tests/unit/`
- `test_vault_config.py` → `tests/unit/`
- `test_uri_utils.py` → `tests/unit/`
- `test_utils.py` → `tests/unit/`
- `test_markdown_parser.py` (if exists)

**Success criteria:**
- `pytest tests/unit/ -v` passes
- No MongoDB/filesystem dependencies in unit tests
- All tests use mocks appropriately

---

### Agent 3: Integration Tests
**Branch:** `test-refactor/integration-tests`

**Tasks:**
1. Move integration-style tests to `tests/integration/`
2. **Fix the 46+ failing daemon tests** (`test_daemon_health.py`, `test_daemon_lifecycle.py`)
3. Add `@pytest.mark.integration` decorator
4. Create proper fixtures for integration tests

**Files to move/fix:**
- `test_daemon_lifecycle.py` → `tests/integration/` (FIX REQUIRED)
- `test_daemon_health.py` → `tests/integration/` (FIX REQUIRED)
- `test_vault_controller_full.py` → `tests/integration/`
- `test_mcp_server.py` → `tests/integration/`
- `test_mcp_bridge.py` → `tests/integration/`

**Critical fixes needed:**
- Daemon tests reference non-existent methods on `WksDaemon` class
- Need to audit `wks/daemon.py` API and update tests accordingly

**Success criteria:**
- `pytest tests/integration/ -v` passes
- Daemon tests actually exercise `daemon.py` code paths
- `daemon.py` coverage improves from 37% to 70%+

---

## Merge Order

1. **Agent 1** merges first (creates directory structure)
2. **Agent 2** merges second (moves unit tests into structure)
3. **Agent 3** merges last (moves integration tests, fixes daemon)
4. **Campaign branch** runs full test suite, then merges to master

## Validation Commands

```bash
# After all merges, run:
pytest tests/smoke/ -v                    # Should pass first
pytest tests/unit/ -v                     # Should pass second  
pytest tests/integration/ -v              # Should pass last
pytest tests/ --cov=wks --cov-report=term # Should show 80%+
```

## Current State (Pre-Campaign)

- **Overall Coverage:** 79.53%
- **Failing Tests:** 46+ (all in daemon tests)
- **Test Organization:** Flat structure in `tests/`
- **Markers:** None configured

