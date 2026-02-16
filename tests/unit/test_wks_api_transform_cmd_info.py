"""Unit tests for wks.api.transform.cmd_info."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_info import cmd_info


@pytest.mark.transform
def test_cmd_info_engine(tracked_wks_config):
    """Test showing info for a specific engine."""
    # 1. Valid engine
    result = run_cmd(cmd_info, engine="textpass")
    assert result.success is True
    assert result.output["engine"] == "textpass"
    assert result.output["config"]["type"] == "textpass"

    # 2. Invalid engine
    result_fail = run_cmd(cmd_info, engine="nonexistent")
    assert result_fail.success is False
    assert "not found" in result_fail.result


@pytest.mark.transform
def test_cmd_info_output_structure(tracked_wks_config):
    """Assert exact output keys and defaults for valid engine info."""
    result = run_cmd(cmd_info, engine="textpass")
    output = result.output

    # Top-level keys
    assert set(output.keys()) == {"engine", "config", "warnings", "errors"}
    assert output["warnings"] == []
    assert output["errors"] == []

    # Config keys
    config = output["config"]
    assert set(config.keys()) == {"type", "supported_types", "options"}
    assert config["supported_types"] == ["*"]
    assert config["type"] == "textpass"


@pytest.mark.transform
def test_cmd_info_not_found_output_structure(tracked_wks_config):
    """Assert error output structure for missing engine."""
    result = run_cmd(cmd_info, engine="nonexistent")
    output = result.output

    assert set(output.keys()) == {"engine", "config", "warnings", "errors"}
    assert output["engine"] == "nonexistent"
    assert output["config"] == {}
    assert output["warnings"] == []
    assert len(output["errors"]) == 1
    assert "nonexistent" in output["errors"][0]
