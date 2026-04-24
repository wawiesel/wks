import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp.cmd_list import cmd_list

pytestmark = pytest.mark.mcp


def test_cmd_list_returns_supported_targets():
    """cmd_list should return native-command guidance for supported targets."""
    result = run_cmd(cmd_list)

    assert result.success is True
    assert result.output["count"] == 3
    assert [target["name"] for target in result.output["targets"]] == ["codex", "claude", "gemini"]
    assert result.output["targets"][0]["install_command"] == "codex mcp add wks -- wksm run"
    assert result.output["targets"][0]["uninstall_command"] == "codex mcp remove wks"
    assert "errors" in result.output
    assert "warnings" in result.output
