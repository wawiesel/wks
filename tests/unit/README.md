## Unit Tests for WKS API

This directory contains unit tests for the `wks/api/*/` modules. These tests focus on testing individual public functions and classes in isolation.

There should be 100% coverage of any public function/class in unit tests.

Public functions/classes do not start with an underscore.

Don't monkey patch unnecessarily. For most testing, we should be using a special environment variable WKS_HOME which points to a tmp dir or something. We can do things like try to write to a directory that doesn't exist or other things instead of monkey patching.

### Scope

- **Unit tests**: Test individual public functions/classes from `wks/api/*/` modules
- **Integration tests** (`tests/integration/`): Test higher-level CLI and MCP layers
- **Smoke tests** (`tests/smoke/`): Test end-to-end workflows


### Import Rules

**CRITICAL**: Never import non-public functions or classes (those starting with `_`).

✅ **Allowed**:
```python
from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.calculate_priority import calculate_priority
from wks.api.monitor.MonitorConfig import MonitorConfig
```

❌ **Forbidden**:
```python
from wks.api.monitor._PriorityConfig import _PriorityConfig  # NO!
from wks.api.monitor._calculate_underscore_multiplier import _calculate_underscore_multiplier  # NO!
```

If you need to test behavior that depends on private classes, use public APIs or create test fixtures that construct the necessary objects through public interfaces.

### File-Level Granularity and Naming

Tests strictly follow a **1-to-1 source file to test file correspondence**.
- **Naming Convention**: `test_wks_api_<package>_<module>.py` corresponds exactly to `wks/api/<package>/<module>.py`.
- **Strict Mapping**: Every test file must verify the behavior of exactly one source file.
- **Exception**: `__init__.py` files are considered private implementation details (e.g., tailored for schema registration) and do NOT require corresponding test files.

All test cases for a given function/class (including edge cases, error paths, etc.) belong in the same 1-to-1 test file.

### Configuration and Shared Code

**All configuration data and shared utilities for unit tests must be centralized in `conftest.py`.**

Every unit test needs configuration data (WKS config dicts, mock configs, etc.). To avoid duplication and ensure consistency:

- ✅ **Use fixtures from `conftest.py`**: `minimal_config_dict`, `wks_home`, `mock_config`, etc.
- ✅ **Extend existing fixtures**: Create new fixtures that build on `minimal_config_dict` for specific test needs
- ❌ **Don't define config dicts in test files**: Avoid duplicating config structures across test files

**Available fixtures:**
- `minimal_config_dict`: Minimal valid WKS configuration (all required fields)
- `wks_home`: Sets up `WKS_HOME` environment variable and writes config file
- `mock_config`: Mock `WKSConfig` instance for testing
- `config_with_mcp`: Config dict with MCP section
- `config_with_monitor_priority`: Config dict with monitor priority directories

**Example:**
```python
def test_something(wks_home, minimal_config_dict):
    # wks_home provides WKS_HOME env and config.json file
    # minimal_config_dict provides the config structure
    config = WKSConfig.load()
    # ... test code
```

### Coverage Requirement

Every public function in `wks/api/*/` must have unit tests in this directory. Public functions are those that:
- Do not start with `_`
- Are exported from API modules
- Are intended to be used by CLI/MCP layers
