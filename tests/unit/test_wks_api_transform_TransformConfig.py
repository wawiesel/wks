"""Unit tests for wks.api.transform.TransformConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.transform.TransformConfig import TransformConfig


def test_transform_config_valid():
    cfg = TransformConfig.model_validate(
        {
            "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
            "default_engine": "test",
            "engines": {"test": {"type": "test", "data": {}}},
        }
    )
    assert cfg.cache.base_dir == "/tmp"
    assert cfg.default_engine == "test"
    assert cfg.engines["test"].type == "test"


def test_transform_config_cache_validation():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 0},  # must be gt 0
                "default_engine": "missing",
                "engines": {},
            }
        )


def test_transform_config_engine_validation():
    # Engine type must be str
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 100},
                "default_engine": "test",
                "engines": {"test": {"type": 123, "data": {}}},  # type mismatch
            }
        )


def test_transform_config_default_engine_must_exist():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
                "default_engine": "missing",
                "engines": {"test": {"type": "textpass", "data": {}}},
            }
        )
