"""Unit tests for wks.api.config.cmd_show module."""

import json
from unittest.mock import patch

import pytest

from wks.api.config.cmd_show import cmd_show

pytestmark = pytest.mark.config


def build_valid_config_dict(tmp_path) -> dict:
    """Build a valid config dict for testing."""
    return {
        "monitor": {
            "filter": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {"~": 100.0},
                "weights": {},
            },
            "database": "monitor",
            "sync": {
                "max_documents": 1000000,
                "min_priority": 0.0,
                "prune_interval_secs": 300.0,
            },
        },
        "vault": {
            "vault_type": "obsidian",
            "base_dir": str(tmp_path / "vault"),
            "wks_dir": "WKS",
            "update_frequency_seconds": 3600.0,
            "database": "vault",
        },
        "db": {
            "type": "mongo",
            "prefix": "wks",
            "data": {"uri": "mongodb://localhost:27017/"},
        },
        "transform": {
            "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
            "engines": {},
            "database": "transform",
        },
    }


class TestCmdShow:
    """Test cmd_show function."""

    def test_cmd_show_no_section(self, tmp_path, monkeypatch):
        """Test cmd_show() with no section lists all sections."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        with patch("wks.api.config.get_config_path.get_config_path", return_value=config_path):
            result = cmd_show(None)

        assert result.success is True
        assert "sections" in result.output
        assert "count" in result.output
        assert isinstance(result.output["sections"], list)
        assert len(result.output["sections"]) > 0

    def test_cmd_show_with_valid_section(self, tmp_path, monkeypatch):
        """Test cmd_show() with valid section returns section data."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        with patch("wks.api.config.get_config_path.get_config_path", return_value=config_path):
            result = cmd_show("monitor")

        assert result.success is True
        assert result.output["section"] == "monitor"
        assert "data" in result.output
        assert isinstance(result.output["data"], dict)

    def test_cmd_show_with_invalid_section(self, tmp_path, monkeypatch):
        """Test cmd_show() with invalid section returns error."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        with patch("wks.api.config.get_config_path.get_config_path", return_value=config_path):
            result = cmd_show("invalid_section")

        assert result.success is False
        assert "error" in result.output
        assert "available_sections" in result.output
