"""Validation edge cases for ServiceConfig and platform data models."""

import pytest

from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_daemon_config_validation_errors():
    with pytest.raises(ValueError, match="service config must be a dict"):
        ServiceConfig.model_validate("not-a-dict")

    with pytest.raises(ValueError, match="service.type is required"):
        ServiceConfig.model_validate({"data": {}, "sync_interval_secs": 0.1})

    with pytest.raises(ValueError, match="Unknown service type"):
        ServiceConfig.model_validate({"type": "unknown", "data": {}, "sync_interval_secs": 0.1})

    with pytest.raises(ValueError, match="service.data is required"):
        ServiceConfig.model_validate({"type": "test", "sync_interval_secs": 0.1})


def test_darwin_data_validation_errors():
    with pytest.raises(ValueError, match="Configuration validation error"):
        ServiceConfig(type="darwin", sync_interval_secs=1.0, data={"label": "", "log_file": "daemon.log", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="reverse DNS"):
        ServiceConfig(type="darwin", sync_interval_secs=1.0, data={"label": "notdns", "log_file": "daemon.log", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="log file path cannot be empty"):
        ServiceConfig(type="darwin", sync_interval_secs=1.0, data={"label": "com.test.app", "log_file": "", "keep_alive": True, "run_at_load": False})

    with pytest.raises(ValueError, match="must be relative"):
        ServiceConfig(type="darwin", sync_interval_secs=1.0, data={"label": "com.test.app", "log_file": "/abs/log", "keep_alive": True, "run_at_load": False})
