import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp import cmd_uninstall

pytestmark = pytest.mark.mcp


def test_cmd_uninstall_returns_native_command_for_supported_target():
    result = run_cmd(cmd_uninstall.cmd_uninstall, name="claude")

    assert result.success is True
    assert result.output["success"] is True
    assert result.output["name"] == "claude"
    assert result.output["command"] == "claude mcp remove --scope user wks"
    assert result.output["errors"] == []
    assert result.output["warnings"] != []


def test_cmd_uninstall_rejects_unsupported_target():
    result = run_cmd(cmd_uninstall.cmd_uninstall, name="test")

    assert result.success is False
    assert result.output["success"] is False
    assert result.output["name"] == "test"
    assert result.output["command"] == ""
    assert result.output["errors"] == ["Unsupported MCP target 'test'"]
    assert result.output["warnings"] == ["Supported targets: codex, claude, gemini"]
