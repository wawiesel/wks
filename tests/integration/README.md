# Integration Tests

Integration tests verify the wiring between components, including:
1.  **CLI Wrappers**: Testing `Typer` commands and argument parsing (`test_wks_cli_<domain>.py`).
2.  **MCP Server**: Testing correct registration and execution of MCP tools.
3.  **System Services**: Testing interactions with the OS (e.g., systemd, launchd).

## CLI Integration
We explicitly assert that testing the CLI wrapper logic (using `TyperRunner`) belongs here in Integration. This validates that the CLI layer correctly converts user input into API calls, without necessarily running a fresh subprocess for every check (which is reserved for Smoke tests).

## Naming Convention
- CLI Integration: `test_wks_cli_<domain>.py`
- MCP Integration: `test_mcp_<domain>.py`
- System Integration: `test_system_<domain>.py` (or similar)
