"""Unit tests for wks.api.daemon.DaemonConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.daemon.DaemonConfig import DaemonConfig


def test_daemon_config_valid():
    cfg = DaemonConfig(sync_interval_secs=10.0)
    assert cfg.sync_interval_secs == 10.0


def test_daemon_config_validation():
    with pytest.raises(ValidationError):
        DaemonConfig(sync_interval_secs=-1.0)


def test_daemon_config_invalid_type():
    with pytest.raises(ValueError, match="daemon config must be a dict"):
        DaemonConfig.model_validate(["not", "a", "dict"])
