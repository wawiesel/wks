"""Tests for transform configuration."""

from typing import Any

import pytest

from wks.transform.config import (
    CacheConfig,
    EngineConfig,
    TransformConfig,
    TransformConfigError,
)


@pytest.mark.unit
class TestTransformConfigError:
    """Test TransformConfigError exception."""

    def test_transform_config_error_with_list(self):
        """Test TransformConfigError with list of errors."""
        error = TransformConfigError(["Error 1", "Error 2"])
        assert len(error.errors) == 2
        assert "Error 1" in str(error)
        assert "Error 2" in str(error)

    def test_transform_config_error_with_string(self):
        """Test TransformConfigError with single string error."""
        error = TransformConfigError("Single error")  # type: ignore[arg-type]
        assert len(error.errors) == 1
        assert error.errors[0] == "Single error"
        assert "Single error" in str(error)


@pytest.mark.unit
class TestTransformConfigValidation:
    """Test TransformConfig validation."""

    def test_transform_config_invalid_cache_type(self):
        """Test TransformConfig raises error when cache is not CacheConfig."""
        CacheConfig(location=".wks/cache", max_size_bytes=1000)
        engines = {"docling": EngineConfig(name="docling", enabled=True, options={})}

        with pytest.raises(TransformConfigError) as exc_info:
            TransformConfig(
                cache="not a CacheConfig",  # type: ignore[arg-type]  # Invalid type
                engines=engines,
                database="wks.transform",
            )

        assert "CacheConfig" in str(exc_info.value)

    def test_transform_config_invalid_engines_type(self):
        """Test TransformConfig raises error when engines is not dict."""
        cache_config = CacheConfig(location=".wks/cache", max_size_bytes=1000)

        with pytest.raises(TransformConfigError) as exc_info:
            TransformConfig(
                cache=cache_config,
                engines="not a dict",  # type: ignore[arg-type]  # Invalid type
                database="wks.transform",
            )

        assert "engines must be a dict" in str(exc_info.value)

    def test_transform_config_invalid_engine_instance(self):
        """Test TransformConfig raises error when engine is not EngineConfig."""
        cache_config = CacheConfig(location=".wks/cache", max_size_bytes=1000)
        engines = {
            "docling": "not an EngineConfig"  # Invalid type
        }

        with pytest.raises(TransformConfigError) as exc_info:
            TransformConfig(cache=cache_config, engines=engines, database="wks.transform")

        assert "EngineConfig" in str(exc_info.value)

    def test_transform_config_valid(self):
        """Test TransformConfig with valid configuration."""
        cache_config = CacheConfig(location=".wks/cache", max_size_bytes=1000)
        engines = {"docling": EngineConfig(name="docling", enabled=True, options={})}

        config = TransformConfig(cache=cache_config, engines=engines, database="wks.transform")

        assert config.cache == cache_config
        assert config.engines == engines
        assert config.database == "wks.transform"


@pytest.mark.unit
class TestTransformConfigFromDict:
    """Test TransformConfig.from_config_dict."""

    def test_from_config_dict_valid(self):
        """Test from_config_dict with valid config."""
        config_dict = {
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000},
                "engines": {"docling": {"enabled": True, "option1": "value1"}},
                "database": "wks.transform",
                "default_engine": "docling",
            }
        }

        config = TransformConfig.from_config_dict(config_dict)

        assert isinstance(config.cache, CacheConfig)
        assert config.cache.location == ".wks/cache"
        assert "docling" in config.engines
        assert config.engines["docling"].enabled is True
        assert config.engines["docling"].options == {"option1": "value1"}
        assert config.database == "wks.transform"
        assert config.default_engine == "docling"

    def test_from_config_dict_missing_transform_section(self):
        """Test from_config_dict raises error when transform section missing."""
        config_dict: dict[str, Any] = {}

        with pytest.raises(TransformConfigError) as exc_info:
            TransformConfig.from_config_dict(config_dict)

        assert "transform section is required" in str(exc_info.value)

    def test_from_config_dict_engine_not_dict(self):
        """Test from_config_dict raises error when engine config is not dict."""
        config_dict = {
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000},
                "engines": {
                    "docling": "not a dict"  # Invalid type
                },
                "database": "wks.transform",
            }
        }

        with pytest.raises(TransformConfigError) as exc_info:
            TransformConfig.from_config_dict(config_dict)

        assert "must be a dict" in str(exc_info.value)

    def test_from_config_dict_defaults(self):
        """Test from_config_dict uses defaults."""
        config_dict = {
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000},
                "engines": {},
            }
        }

        config = TransformConfig.from_config_dict(config_dict)

        assert config.database == "wks_transform"
        assert config.default_engine == "docling"

    def test_from_config_dict_engine_removes_enabled(self):
        """Test from_config_dict removes 'enabled' from engine options."""
        config_dict = {
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000},
                "engines": {"docling": {"enabled": True, "option1": "value1"}},
                "database": "wks.transform",
            }
        }

        config = TransformConfig.from_config_dict(config_dict)

        # 'enabled' should not be in options
        assert "enabled" not in config.engines["docling"].options
        assert config.engines["docling"].options == {"option1": "value1"}


@pytest.mark.unit
class TestCacheConfigValidation:
    """Test CacheConfig validation."""

    def test_cache_config_invalid_location_empty_string(self):
        """Test CacheConfig raises error when location is empty string."""
        with pytest.raises(TransformConfigError) as exc_info:
            CacheConfig(location="", max_size_bytes=1000)

        assert "location" in str(exc_info.value).lower()

    def test_cache_config_invalid_max_size_zero(self):
        """Test CacheConfig raises error when max_size_bytes is zero."""
        with pytest.raises(TransformConfigError) as exc_info:
            CacheConfig(location=".wks/cache", max_size_bytes=0)

        assert "max_size_bytes" in str(exc_info.value).lower()

    def test_cache_config_invalid_max_size_negative(self):
        """Test CacheConfig raises error when max_size_bytes is negative."""
        with pytest.raises(TransformConfigError) as exc_info:
            CacheConfig(location=".wks/cache", max_size_bytes=-1)

        assert "max_size_bytes" in str(exc_info.value).lower()

    def test_cache_config_invalid_location_type(self):
        """Test CacheConfig raises error when location is wrong type."""
        with pytest.raises(TransformConfigError) as exc_info:
            CacheConfig(location=123, max_size_bytes=1000)  # type: ignore[arg-type]

        assert "location" in str(exc_info.value).lower()


@pytest.mark.unit
class TestEngineConfigValidation:
    """Test EngineConfig validation."""

    def test_engine_config_invalid_name_empty_string(self):
        """Test EngineConfig raises error when name is empty string."""
        with pytest.raises(TransformConfigError) as exc_info:
            EngineConfig(name="", enabled=True, options={})

        assert "name" in str(exc_info.value).lower()

    def test_engine_config_invalid_enabled_type(self):
        """Test EngineConfig raises error when enabled is not boolean."""
        with pytest.raises(TransformConfigError) as exc_info:
            EngineConfig(name="docling", enabled="yes", options={})  # type: ignore[arg-type]

        assert "enabled" in str(exc_info.value).lower()

    def test_engine_config_invalid_options_type(self):
        """Test EngineConfig raises error when options is not dict."""
        with pytest.raises(TransformConfigError) as exc_info:
            EngineConfig(name="docling", enabled=True, options="not a dict")  # type: ignore[arg-type]

        assert "options" in str(exc_info.value).lower()

    def test_engine_config_valid(self):
        """Test EngineConfig with valid configuration."""
        config = EngineConfig(name="docling", enabled=True, options={"option1": "value1"})

        assert config.name == "docling"
        assert config.enabled is True
        assert config.options == {"option1": "value1"}
