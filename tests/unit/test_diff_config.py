"""Tests for wks/diff/config.py - DiffConfig and related dataclasses."""

import pytest

from wks.diff.config import (
    DiffConfig,
    DiffConfigError,
    DiffEngineConfig,
    DiffRouterConfig,
)


@pytest.mark.unit
class TestDiffEngineConfig:
    """Tests for DiffEngineConfig validation."""

    def test_valid_engine(self):
        cfg = DiffEngineConfig(name="myers", enabled=True, is_default=True, options={})
        assert cfg.name == "myers"
        assert cfg.enabled is True
        assert cfg.is_default is True

    def test_invalid_name(self):
        with pytest.raises(DiffConfigError):
            DiffEngineConfig(name="", enabled=True, is_default=False, options={})

    def test_invalid_enabled(self):
        with pytest.raises(DiffConfigError):
            DiffEngineConfig(name="myers", enabled="yes", is_default=False, options={})

    def test_invalid_is_default(self):
        with pytest.raises(DiffConfigError):
            DiffEngineConfig(name="myers", enabled=True, is_default="no", options={})

    def test_invalid_options(self):
        with pytest.raises(DiffConfigError):
            DiffEngineConfig(name="myers", enabled=True, is_default=False, options="opts")


@pytest.mark.unit
class TestDiffRouterConfig:
    """Tests for DiffRouterConfig validation."""

    def test_valid_router(self):
        cfg = DiffRouterConfig(rules=[{"engine": "myers"}], fallback="myers")
        assert cfg.fallback == "myers"

    def test_invalid_rules_type(self):
        with pytest.raises(DiffConfigError):
            DiffRouterConfig(rules="not-a-list", fallback="myers")

    def test_invalid_rule_entry_type(self):
        with pytest.raises(DiffConfigError):
            DiffRouterConfig(rules=["not-a-dict"], fallback="myers")

    def test_invalid_fallback(self):
        with pytest.raises(DiffConfigError):
            DiffRouterConfig(rules=[], fallback="")


@pytest.mark.unit
class TestDiffConfig:
    """Tests for DiffConfig.from_config_dict and validation."""

    def test_from_config_dict_valid(self):
        cfg = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                    "bsdiff3": {"enabled": True, "is_default": False},
                },
                "_router": {
                    "rules": [{"engine": "myers", "pattern": "*.txt"}],
                    "fallback": "bsdiff3",
                },
            }
        }

        dc = DiffConfig.from_config_dict(cfg)
        assert "myers" in dc.engines
        assert dc.engines["myers"].is_default is True
        assert dc.router.fallback == "bsdiff3"

    def test_from_config_dict_missing_section(self):
        with pytest.raises(DiffConfigError) as exc:
            DiffConfig.from_config_dict({})
        assert "diff section is required" in str(exc.value)

    def test_from_config_dict_no_default_engine(self):
        cfg = {
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": False},
                },
                "_router": {"rules": [], "fallback": "myers"},
            }
        }

        with pytest.raises(DiffConfigError) as exc:
            DiffConfig.from_config_dict(cfg)
        assert "at least one engine with is_default=true" in str(exc.value)
