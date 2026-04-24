# WKS Tests

The test suite is split by responsibility:

- `tests/unit/`: deep service/core and per-command contract coverage
- `tests/integration/`: CLI, MCP, REST, and cross-module wiring
- `tests/smoke/`: installed entry-point checks for `wksc`, `wksm`, and `wksr`

Traceability stays in test docstrings:

```python
def test_cmd_status_success():
    """Status succeeds.

    Requirements:
    - MON-003
    """
```

Run from `venv`:

```bash
venv/bin/pytest
venv/bin/pytest tests/unit/
venv/bin/pytest tests/integration/
venv/bin/pytest tests/smoke/
```
