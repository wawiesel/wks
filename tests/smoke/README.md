# Smoke Tests

Smoke tests verify that the `wksc` binary is installed and executable from the user's perspective.

## Scope
These tests invoke the actual `wksc` command via subprocesses. They ensure:
1.  The package is installed correctly.
2.  Entry points (`wksc`) are available in the path.
3.  Configuration loading works in a real process environment.
4.  Standard input/output streams are handled correctly.

## Naming Convention
Test files must be named `test_wksc_<domain>.py`.
Examples:
- `test_wksc_monitor.py`
- `test_wksc_mcp.py`
- `test_wksc_smoke.py` (General connection checks)
