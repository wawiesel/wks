"""Helper-level tests for MCP server utilities."""

from functools import wraps

from wks.mcp.discover_commands import discover_commands
from wks.mcp.extract_api_function_from_command import extract_api_function_from_command
from wks.mcp.get_app import get_app


def test_extract_api_function_wrapped():
    """extract_api_function_from_command handles wrapped callbacks."""

    def api_func():
        return "ok"

    @wraps(api_func)
    def wrapped():
        return api_func()

    # Wrapped function path - this is the primary pattern used
    assert extract_api_function_from_command(wrapped, None) is api_func


def test_extract_api_function_from_real_module():
    """extract_api_function_from_command finds API functions via module discovery."""
    import wks.cli.monitor as cli_module

    # Create a mock callback with the naming pattern
    def status_cmd():
        pass

    # Test that it finds cmd_status in wks.api.monitor.cmd_status
    result = extract_api_function_from_command(status_cmd, cli_module)
    assert result is not None
    assert result.__name__ == "cmd_status"


def test_get_app_returns_none_for_unknown_domain():
    """get_app should return None when a Typer app is missing."""
    assert get_app("nonexistent") is None
    assert get_app("monitor") is not None


def test_discover_scans_cli_modules():
    """discover_commands should gather commands from factory pattern."""
    commands = discover_commands()
    assert ("monitor", "status") in commands
    assert ("config", "list") in commands
    # Verify we're finding a good number of commands
    assert len(commands) >= 20
