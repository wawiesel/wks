"""Unit tests for wks.api.transform.cmd_list."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_list import cmd_list


@pytest.mark.transform
def test_cmd_list_engines(tracked_wks_config):
    """Test listing available transform engines."""
    result = run_cmd(cmd_list)
    assert result.success is True
    assert "Found" in result.result
    assert "textpass" in result.output["engines"]
    assert result.output["engines"]["textpass"]["type"] == "textpass"


@pytest.mark.transform
def test_cmd_list_output_structure(tracked_wks_config):
    """Assert exact output keys, defaults, and empty warnings/errors."""
    result = run_cmd(cmd_list)
    output = result.output

    # Top-level keys must be exactly these
    assert set(output.keys()) == {"engines", "warnings", "errors"}
    assert output["warnings"] == []
    assert output["errors"] == []

    # Each engine entry has exactly "type" and "supported_types"
    for _name, engine in output["engines"].items():
        assert set(engine.keys()) == {"type", "supported_types"}

    # textpass has no supported_types configured -> defaults to ["*"]
    assert output["engines"]["textpass"]["supported_types"] == ["*"]
