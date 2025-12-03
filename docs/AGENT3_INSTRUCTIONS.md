# Agent 3: Integration Tests

## Your Mission

Move integration tests to `tests/integration/`, and **critically**, fix the 46+ failing daemon tests.

## Tasks

### 1. Move Integration Tests to tests/integration/

Move these files:
```
tests/test_daemon_lifecycle.py      → tests/integration/
tests/test_daemon_health.py         → tests/integration/
tests/test_daemon_events.py         → tests/integration/
tests/test_vault_controller_full.py → tests/integration/
tests/test_vault_controller.py      → tests/integration/
tests/test_mcp_server.py            → tests/integration/
tests/test_mcp_bridge.py            → tests/integration/
tests/test_mcp_setup.py             → tests/integration/
tests/test_service_controller.py    → tests/integration/
tests/test_wks_service_controller.py → tests/integration/
```

### 2. FIX THE FAILING DAEMON TESTS (Critical!)

**Current state:** 46+ tests failing in `test_daemon_health.py` and `test_daemon_lifecycle.py`

**Root cause:** Tests were written against a different API than what `WksDaemon` actually exposes.

**Your task:**
1. Read `wks/daemon.py` carefully to understand the actual API
2. Update tests to match the real implementation
3. Ensure tests actually exercise the daemon code paths

**Key methods to test in WksDaemon:**
```python
# Check these actually exist and test them:
- __init__()
- start()
- stop()
- run()
- process_events()
- sync_to_mongodb()
- get_health_data()
- prune_old_records()
```

### 3. Add @pytest.mark.integration Decorator
```python
import pytest

@pytest.mark.integration
class TestDaemonLifecycle:
    ...
```

### 4. Create Proper Fixtures

Integration tests need fixtures for:
```python
@pytest.fixture
def mock_mongodb():
    """Mock MongoDB connection for integration tests."""
    ...

@pytest.fixture
def temp_watch_directory(tmp_path):
    """Create a temporary directory with test files."""
    ...

@pytest.fixture
def daemon_config(mock_mongodb, temp_watch_directory):
    """Create a valid daemon configuration."""
    ...
```

### 5. Verify All Integration Tests Pass
```bash
pytest tests/integration/ -v
```

### 6. Verify Daemon Coverage Improved
```bash
pytest tests/integration/test_daemon*.py --cov=wks/daemon --cov-report=term-missing
```
Target: `wks/daemon.py` should go from 37% to 70%+

## Success Criteria

- [ ] All integration tests moved to `tests/integration/`
- [ ] **All 46+ previously failing tests now pass**
- [ ] `pytest tests/integration/ -v` passes
- [ ] `wks/daemon.py` coverage ≥ 70%
- [ ] Tests use proper mocking (no real MongoDB needed)

## Debugging the Daemon Tests

The tests likely fail because they call methods that don't exist. Check:

```bash
# See what methods WksDaemon actually has:
python -c "from wks.daemon import WksDaemon; print([m for m in dir(WksDaemon) if not m.startswith('_')])"
```

Then update the tests to use the real method names and signatures.

## Do NOT

- Touch `tests/smoke/` (Agent 1's area)
- Touch `tests/unit/` (Agent 2's area)
- Delete tests - fix them
- Skip tests with `@pytest.mark.skip` - actually fix them

## Files to Leave in Place

Leave these in the root `tests/` directory (they may be unit tests):
- `test_config.py`
- `test_utils.py`
- `test_uri_utils.py`
- Config-related tests

