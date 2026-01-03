"""Unit tests for wks.api.diff.DiffConfig."""

from typing import Any

import pytest
from pydantic import ValidationError

from wks.api.diff.DiffConfig import DiffConfig
from wks.api.diff.DiffRouterConfig import DiffRouterConfig


def test_valid_config():
    """Test loading valid configuration."""
    config_dict: dict[str, Any] = {
        "engines": {"text": {"enabled": True, "is_default": True}},
        "_router": {"rules": [], "fallback": "text"},
    }
    config = DiffConfig.model_validate(config_dict)
    assert len(config.engines) == 1
    assert config.engines["text"].enabled is True
    assert config.engines["text"].is_default is True
    assert isinstance(config.router, DiffRouterConfig)


def test_missing_engines():
    """Test error when engines section is missing."""
    config_dict: dict[str, Any] = {}
    with pytest.raises(ValidationError) as excinfo:
        DiffConfig.model_validate(config_dict)
    assert "Field required" in str(excinfo.value)
    assert "engines" in str(excinfo.value)


def test_no_default_engine():
    """Test error when no engine is marked as default."""
    config_dict: dict[str, Any] = {
        "engines": {"text": {"enabled": True, "is_default": False}},
        "_router": {"rules": [], "fallback": "text"},
    }
    with pytest.raises(ValidationError) as excinfo:
        DiffConfig.model_validate(config_dict)
    assert "At least one engine must be marked as default" in str(excinfo.value)


def test_invalid_engine_type():
    """Test error when engine config is not a dict."""
    config_dict: dict[str, Any] = {
        "engines": {"text": "invalid"},
        "_router": {"rules": [], "fallback": "text"},
    }
    with pytest.raises(ValidationError):
        DiffConfig.model_validate(config_dict)


def test_router_defaults():
    """Test router defaults when _router section is missing."""
    config_dict: dict[str, Any] = {
        "engines": {"text": {"enabled": True, "is_default": True}},
    }
    config = DiffConfig.model_validate(config_dict)
    assert config.router.fallback == "text"
    assert config.router.rules == []


def test_explicit_router_config():
    """Test parsing explicit router configuration."""
    config_dict: dict[str, Any] = {
        "engines": {"text": {"enabled": True, "is_default": True}},
        "_router": {
            "rules": [{"glob": "*.py", "engine": "python"}],
            "fallback": "binary",
        },
    }
    config = DiffConfig.model_validate(config_dict)
    assert config.router.fallback == "binary"
    assert len(config.router.rules) == 1
    assert config.router.rules[0] == {"glob": "*.py", "engine": "python"}
