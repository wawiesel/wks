import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._RouteEngineConfig import _RouteEngineConfig, _RouteEngineData
from wks.api.transform.cmd_info import cmd_info


@pytest.mark.transform
def test_cmd_info_engine(tracked_wks_config):
    """Test showing info for a specific engine."""
    result = run_cmd(cmd_info, engine="textpass")
    assert result.success is True
    assert result.output["engine"] == "textpass"
    assert result.output["config"]["type"] == "textpass"

    result_fail = run_cmd(cmd_info, engine="nonexistent")
    assert result_fail.success is False
    assert "not found" in result_fail.result


@pytest.mark.transform
def test_cmd_info_route_engine(tracked_wks_config):
    """Route engine info includes order and fallback policy."""
    config = WKSConfig.load()
    config.transform.engines["default"] = _RouteEngineConfig(
        type="route",
        data=_RouteEngineData(order=["docling_test"], passthrough_text=True, reject_binary=True),
    )
    config.transform.default_engine = "default"
    config.save()

    result = run_cmd(cmd_info, engine="default")
    assert result.success is True
    assert result.output["config"]["type"] == "route"
    assert result.output["config"]["order"] == ["docling_test"]
    assert result.output["config"]["passthrough_text"] is True
    assert result.output["config"]["reject_binary"] is True
