"""Unit tests for wks.api.transform.cmd_list."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._RouteEngineConfig import _RouteEngineConfig, _RouteEngineData
from wks.api.transform.cmd_list import cmd_list


@pytest.mark.transform
def test_cmd_list_engines(tracked_wks_config):
    """Test listing available transform engines."""
    result = run_cmd(cmd_list)
    assert result.success is True
    assert "Found" in result.result
    assert result.output["default_engine"] == "textpass"
    assert "textpass" in result.output["engines"]
    assert result.output["engines"]["textpass"]["type"] == "textpass"


@pytest.mark.transform
def test_cmd_list_includes_route_policy(tracked_wks_config):
    """Route engines expose ordered policy in list output."""
    config = WKSConfig.load()
    config.transform.engines["default"] = _RouteEngineConfig(
        type="route",
        data=_RouteEngineData(order=["docling_test"], passthrough_text=True, reject_binary=True),
    )
    config.transform.default_engine = "default"
    config.save()

    result = run_cmd(cmd_list)
    assert result.success is True
    assert result.output["engines"]["default"]["type"] == "route"
    assert result.output["engines"]["default"]["order"] == ["docling_test"]
    assert result.output["engines"]["default"]["passthrough_text"] is True
    assert result.output["engines"]["default"]["reject_binary"] is True
