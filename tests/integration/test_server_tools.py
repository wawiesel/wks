"""Helper-level tests for MCP server utilities."""

import types
from functools import wraps
from unittest.mock import patch

import pytest

import wks.mcp.discover_commands as discover_commands_module
from wks.mcp.discover_commands import discover_commands
from wks.mcp.extract_api_function_from_command import extract_api_function_from_command
from wks.mcp.get_app import get_app


def test_extract_api_function_patterns():
    """extract_api_function_from_command handles wrapped and wrapper callbacks."""
    def api_func():
        return "ok"

    @wraps(api_func)
    def wrapped():
        return api_func()

    module = types.SimpleNamespace(cmd_sample=api_func)

    # Wrapped function path
    assert extract_api_function_from_command(wrapped, module) is api_func

    # Wrapper that delegates to cmd_* in module
    def sample_command():
        return api_func()

    sample_command.__name__ = "sample_command"
    assert extract_api_function_from_command(sample_command, module) is api_func

    # No match returns None
    assert extract_api_function_from_command(lambda: None, module) is None


def test_get_app_returns_none_for_unknown_domain():
    """get_app should return None when a Typer app is missing."""
    assert get_app("nonexistent") is None
    assert get_app("monitor") is not None


def test_discover_scans_cli_modules(monkeypatch):
    """discover_commands should gather commands and tolerate broken modules."""
    original_import = discover_commands_module.importlib.import_module

    def flaky_import(name):
        if name.endswith("get_typer_command_schema"):
            raise RuntimeError("boom")
        return original_import(name)

    monkeypatch.setattr(discover_commands_module.importlib, "import_module", flaky_import)

    commands = discover_commands()
    assert ("monitor", "status") in commands
    assert ("config", "list") in commands
