"""Unit tests for wks.api.diff.DiffConfig module."""

from typing import Any

import pytest

from wks.api.diff.DiffConfig import DiffConfig
from wks.api.diff.DiffConfigError import DiffConfigError
from wks.api.diff.DiffRouterConfig import DiffRouterConfig

pytestmark = pytest.mark.unit


class TestDiffConfig:
    """Test DiffConfig class."""

    def test_from_config_dict_valid(self):
        """Test loading valid diff config."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                    "bsdiff3": {"enabled": True, "is_default": False},
                },
                "_router": {"rules": [], "fallback": "myers"},
            }
        }

        diff_config = DiffConfig.from_config_dict(config)
        assert "myers" in diff_config.engines
        assert "bsdiff3" in diff_config.engines
        assert diff_config.engines["myers"].enabled is True
        assert diff_config.engines["myers"].is_default is True
        assert isinstance(diff_config.router, DiffRouterConfig)

    def test_from_config_dict_missing_diff_section(self):
        """Test loading config without diff section."""
        config: dict[str, Any] = {}

        with pytest.raises(DiffConfigError, match="diff section is required"):
            DiffConfig.from_config_dict(config)

    def test_from_config_dict_missing_engines(self):
        """Test loading config without engines."""
        config: dict[str, Any] = {"diff": {}}

        with pytest.raises(DiffConfigError, match=r"diff.engines is required"):
            DiffConfig.from_config_dict(config)

    def test_from_config_dict_invalid_engine_dict(self):
        """Test loading config with invalid engine dict."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": "not a dict",  # Invalid: should be dict
                }
            }
        }

        with pytest.raises(DiffConfigError, match="must be a dict"):
            DiffConfig.from_config_dict(config)

    def test_from_config_dict_no_default_engine(self):
        """Test validation fails when no default engine."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": False},
                    "bsdiff3": {"enabled": True, "is_default": False},
                }
            }
        }

        with pytest.raises(DiffConfigError, match="at least one engine with is_default=true"):
            DiffConfig.from_config_dict(config)

    def test_from_config_dict_engine_enabled_defaults(self):
        """Test engine enabled and is_default default to False."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": {},  # No enabled or is_default specified
                    "bsdiff3": {"enabled": True, "is_default": True},  # This one is default
                }
            }
        }

        diff_config = DiffConfig.from_config_dict(config)
        assert diff_config.engines["myers"].enabled is False
        assert diff_config.engines["myers"].is_default is False
        assert diff_config.engines["bsdiff3"].enabled is True
        assert diff_config.engines["bsdiff3"].is_default is True

    def test_from_config_dict_router_defaults(self):
        """Test router config defaults when not specified."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                }
            }
        }

        diff_config = DiffConfig.from_config_dict(config)
        assert isinstance(diff_config.router, DiffRouterConfig)
        assert diff_config.router.fallback == "text"
        assert diff_config.router.rules == []

    def test_from_config_dict_router_custom(self):
        """Test router config with custom values."""
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "_router": {"rules": [{"pattern": "*.txt", "engine": "myers"}], "fallback": "bsdiff3"},
            }
        }

        diff_config = DiffConfig.from_config_dict(config)
        assert diff_config.router.fallback == "bsdiff3"
        assert len(diff_config.router.rules) == 1

    def test_validation_invalid_engines_type(self):
        """Test validation fails when engines is not a dict."""
        # Use from_config_dict to trigger validation
        config: dict[str, Any] = {
            "diff": {
                "engines": "not a dict",  # Invalid type
            }
        }

        # The error occurs when trying to call .items() on a string
        with pytest.raises((DiffConfigError, AttributeError)):
            DiffConfig.from_config_dict(config)

    def test_validation_invalid_engine_config_type(self):
        """Test validation fails when engine config is not a dict."""
        # The validation happens in from_config_dict, not in __post_init__
        # So we test via from_config_dict
        config: dict[str, Any] = {
            "diff": {
                "engines": {
                    "myers": "not a dict",  # Invalid: should be dict
                }
            }
        }

        with pytest.raises(DiffConfigError, match="must be a dict"):
            DiffConfig.from_config_dict(config)
