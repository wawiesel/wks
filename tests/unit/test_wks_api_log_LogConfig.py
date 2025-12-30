"""Unit tests for wks.api.log.LogConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.log.LogConfig import LogConfig


def test_log_config_valid():
    cfg = LogConfig(
        level="INFO",
        info_retention_days=7.0,
        warning_retention_days=30.0,
        error_retention_days=14.0,
        debug_retention_days=1.0,
    )
    assert cfg.level == "INFO"
    assert cfg.info_retention_days == 7.0
    assert cfg.warning_retention_days == 30.0


def test_log_config_validation_days():
    with pytest.raises(ValidationError):
        LogConfig(
            level="INFO",
            info_retention_days=0.0,  # gt 0
            warning_retention_days=1.0,
            error_retention_days=1.0,
            debug_retention_days=1.0,
        )
