from functools import wraps

from wks.mcp.discover_commands import discover_commands
from wks.mcp.extract_api_function_from_command import extract_api_function_from_command
from wks.mcp.get_app import get_app


def test_extract_api_function_wrapped():
    def api_func():
        return "ok"

    @wraps(api_func)
    def wrapped():
        return api_func()

    assert extract_api_function_from_command(wrapped, None) is api_func


def test_extract_api_function_from_real_module():
    import wks.cli.monitor as cli_module

    def status_cmd():
        pass

    result = extract_api_function_from_command(status_cmd, cli_module)
    assert result is not None
    assert result.__name__ == "cmd_status"


def test_get_app_returns_none_for_unknown_domain():
    assert get_app("nonexistent") is None
    assert get_app("monitor") is not None


def test_discover_scans_cli_modules():
    commands = discover_commands()
    assert ("monitor", "status") in commands
    assert ("config", "list") in commands
    assert len(commands) >= 20
