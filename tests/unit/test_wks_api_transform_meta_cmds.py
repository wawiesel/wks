"""Tests for transform cmd_list and cmd_info."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.transform.cmd_info import cmd_info
from wks.api.transform.cmd_list import cmd_list


@pytest.mark.transform
def test_cmd_list_engines(tracked_wks_config):
    """Test listing available transform engines."""
    result = run_cmd(cmd_list)
    assert result.success is True
    assert "Found" in result.result
    assert "test" in result.output["engines"]
    assert result.output["engines"]["test"]["type"] == "test"


@pytest.mark.transform
def test_cmd_info_engine(tracked_wks_config):
    """Test showing info for a specific engine."""
    # 1. Valid engine
    result = run_cmd(cmd_info, engine="test")
    assert result.success is True
    assert result.output["engine"] == "test"
    assert result.output["config"]["type"] == "test"

    # 2. Invalid engine
    result_fail = run_cmd(cmd_info, engine="nonexistent")
    assert result_fail.success is False
    assert "not found" in result_fail.result
