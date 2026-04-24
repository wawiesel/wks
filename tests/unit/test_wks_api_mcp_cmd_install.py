import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp import cmd_install

pytestmark = pytest.mark.mcp


def test_cmd_install_returns_native_command_for_supported_target():
    """Supported targets should return the native client install command."""
    result = run_cmd(cmd_install.cmd_install, name="codex")

    assert result.success is True
    assert result.output["success"] is True
    assert result.output["name"] == "codex"
    assert result.output["command"] == "codex mcp add wks -- wksm run"
    assert result.output["errors"] == []
    assert result.output["warnings"] != []


def test_cmd_install_rejects_unsupported_target():
    """Unsupported targets should fail with a clear supported-target list."""
    result = run_cmd(cmd_install.cmd_install, name="test")

    assert result.success is False
    assert result.output["success"] is False
    assert result.output["name"] == "test"
    assert result.output["command"] == ""
    assert result.output["errors"] == ["Unsupported MCP target 'test'"]
    assert result.output["warnings"] == ["Supported targets: codex, claude, gemini"]
