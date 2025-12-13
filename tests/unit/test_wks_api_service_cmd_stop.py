"""Unit tests for wks.api.service.cmd_stop module.

We prefer not to use mocks in almost every case, but there is not a good way
to test stopping a service except with mocks.

"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import cmd_stop
from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_cmd_stop_not_installed(tracked_wks_config, monkeypatch):
    """Test cmd_stop when service is not installed."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        sync_interval_secs=60.0,
        data={
            "label": "com.test.wks",
            "keep_alive": True,
            "run_at_load": False,
        },
    )
    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {"installed": False}

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "not installed" in result.result.lower()
    assert "errors" in result.output
    assert "warnings" in result.output
