"""Validation edge cases for DaemonConfig and platform data models."""

import pytest

from wks.api.daemon.DaemonConfig import DaemonConfig

pytestmark = pytest.mark.daemon


def test_daemon_config_validation_errors():
    with pytest.raises(ValueError, match="daemon config must be a dict"):
        DaemonConfig.model_validate("not-a-dict")

    with pytest.raises(ValueError, match="daemon.type is required"):
        DaemonConfig.model_validate({"data": {}, "sync_interval_secs": 0.1})

    with pytest.raises(ValueError, match="Unknown daemon type"):
        DaemonConfig.model_validate({"type": "unknown", "data": {}, "sync_interval_secs": 0.1})

    with pytest.raises(ValueError, match="daemon.data is required"):
        DaemonConfig.model_validate({"type": "test", "sync_interval_secs": 0.1})


def test_darwin_data_validation_errors():
    with pytest.raises(ValueError, match="Configuration validation error"):
        DaemonConfig(type="darwin", sync_interval_secs=1.0, data={"label": "", "log_file": "daemon.log", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="reverse DNS"):
        DaemonConfig(type="darwin", sync_interval_secs=1.0, data={"label": "notdns", "log_file": "daemon.log", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="log file path cannot be empty"):
        DaemonConfig(type="darwin", sync_interval_secs=1.0, data={"label": "com.test.app", "log_file": "", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="must be relative"):
        DaemonConfig(type="darwin", sync_interval_secs=1.0, data={"label": "com.test.app", "log_file": "/abs/log", "keep_alive": True, "run_at_load": False})
