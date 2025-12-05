## Unit Tests for WKS API

This directory contains unit tests for the `wks/api/*/` modules. These tests focus on testing individual public functions and classes in isolation.

### Scope

- **Unit tests**: Test individual public functions/classes from `wks/api/*/` modules
- **Integration tests** (`tests/integration/`): Test higher-level CLI and MCP layers
- **Smoke tests** (`tests/smoke/`): Test end-to-end workflows

### Naming Convention

Unit tests for API functions follow this pattern:

```
test_wks_api_<package>_<function>.py
```

Where:
- `<package>` is the API package name (e.g., `monitor`, `vault`, `transform`)
- `<function>` is the public function name (e.g., `explain_path`, `calculate_priority`, `cmd_status`)

Examples:
- `test_wks_api_monitor_explain_path.py` - tests `wks.api.monitor.explain_path`
- `test_wks_api_monitor_calculate_priority.py` - tests `wks.api.monitor.calculate_priority`
- `test_wks_api_monitor_cmd_status.py` - tests `wks.api.monitor.cmd_status`

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

### File-Level Granularity

Given the extreme file-level granularity in `wks/api/*/` (one function per file), unit tests are organized at the **file level** rather than deeper granularity. Each public function in `wks/api/*/` gets its own test file following the naming convention above.

All test cases for a given function (including edge cases, error paths, and special scenarios like Windows drive handling) belong in the same test file. There's no need for subdirectories or additional file-level organization beyond the `test_wks_api_<package>_<function>.py` pattern.

### Coverage Requirement

Every public function in `wks/api/*/` must have unit tests in this directory. Public functions are those that:
- Do not start with `_`
- Are exported from API modules
- Are intended to be used by CLI/MCP layers

