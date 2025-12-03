# Agent 2: Unit Tests

## Your Mission

Move pure unit tests to `tests/unit/` and ensure they all pass with proper isolation (no external dependencies).

## Tasks

### 1. Identify Unit Tests
Unit tests are tests that:
- Test a single function or class in isolation
- Use mocks for all external dependencies (DB, filesystem, network)
- Run fast (<100ms each)
- Have no side effects

### 2. Move Tests to tests/unit/

Move these files (create subdirectories as needed):
```
tests/test_config.py           → tests/unit/test_config.py
tests/test_wks_config.py       → tests/unit/test_wks_config.py
tests/test_priority.py         → tests/unit/test_priority.py (if exists)
tests/test_uri_utils.py        → tests/unit/test_uri_utils.py
tests/test_utils.py            → tests/unit/test_utils.py
tests/test_diff_config.py      → tests/unit/test_diff_config.py
tests/test_diff.py             → tests/unit/test_diff.py
tests/test_monitor_config.py   → tests/unit/test_wks_monitor_config.py
tests/test_transform_config.py → tests/unit/test_transform_config.py
tests/test_transform_cache.py  → tests/unit/test_transform_cache.py (if exists)
tests/test_display_formats.py  → tests/unit/test_display_formats.py
tests/test_file_url_conversion.py → tests/unit/test_file_url_conversion.py
```

### 3. Fix Any Import Issues
After moving, update any relative imports that break.

### 4. Add @pytest.mark.unit Decorator
Add to each test class or function:
```python
import pytest

@pytest.mark.unit
class TestConfigLoading:
    ...
```

### 5. Verify All Unit Tests Pass
```bash
pytest tests/unit/ -v
```

### 6. Verify No External Dependencies
Run unit tests with network/DB disabled:
```bash
pytest tests/unit/ -v --tb=short
```

## Success Criteria

- [ ] All identified unit tests moved to `tests/unit/`
- [ ] `pytest tests/unit/ -v` passes (100% of moved tests)
- [ ] No MongoDB connections in unit tests
- [ ] No real filesystem operations in unit tests
- [ ] All tests properly mocked

## Do NOT

- Touch `tests/smoke/` (Agent 1's area)
- Touch `tests/integration/` (Agent 3's area)
- Touch daemon tests (`test_daemon_*.py`) - those are integration tests
- Touch vault controller tests - those are integration tests
- Delete any tests - only move them

## Files to Leave in Place

These should NOT be moved (they are integration tests for Agent 3):
- `test_daemon_*.py`
- `test_vault_controller*.py`
- `test_mcp_server.py`
- `test_mcp_bridge.py`
- `test_service_controller.py`

