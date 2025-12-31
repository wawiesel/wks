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
    assert "test" in result.output["engines"]
    assert result.output["engines"]["test"]["type"] == "test"
