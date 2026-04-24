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


def test_transform_config_route_targets_must_exist():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
                "default_engine": "default",
                "engines": {
                    "default": {
                        "type": "route",
                        "data": {
                            "order": ["missing"],
                            "passthrough_text": True,
                        },
                    },
                    "textpass": {"type": "textpass", "data": {}},
                },
            }
        )


def test_transform_config_route_targets_cannot_reference_route():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
                "default_engine": "default",
                "engines": {
                    "default": {
                        "type": "route",
                        "data": {
                            "order": ["other_route"],
                            "passthrough_text": True,
                        },
                    },
                    "other_route": {
                        "type": "route",
                        "data": {
                            "order": ["textpass"],
                        },
                    },
                    "textpass": {"type": "textpass", "data": {}},
                    "nullpass": {"type": "null", "data": {"message": "no transform"}},
                },
            }
        )


def test_transform_config_route_targets_cannot_reference_null():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
                "default_engine": "default",
                "engines": {
                    "default": {
                        "type": "route",
                        "data": {
                            "order": ["nullpass"],
                        },
                    },
                    "nullpass": {"type": "null", "data": {"message": "no transform"}},
                },
            }
        )


def test_transform_config_route_requires_behavior():
    with pytest.raises(ValidationError):
        TransformConfig.model_validate(
            {
                "cache": {"base_dir": "/tmp", "max_size_bytes": 1000},
                "default_engine": "default",
                "engines": {
                    "default": {
                        "type": "route",
                        "data": {},
                    },
                },
            }
        )
