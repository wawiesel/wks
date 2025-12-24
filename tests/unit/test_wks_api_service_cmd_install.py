"""Unit tests for wks.api.service.cmd_install module.

We prefer not to use mocks in almost every case, but there is not a good way
to test installing a service except with mocks.

"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import cmd_install
from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_cmd_install_success(tracked_wks_config, monkeypatch):
    """Test cmd_install with successful installation."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={  # type: ignore
            "label": "com.test.wks",
            "keep_alive": True,
            "run_at_load": False,
        },
    )  # type: ignore
    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.install_service.return_value = {
        "success": True,
        "label": "com.test.wks",
        "plist_path": "/path/to/plist",
    }

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output
