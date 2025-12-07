"""Unit tests for wks.api.config.cmd_show.cmd_show_all module."""

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
        "database": {
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


class TestCmdShowAll:
    """Test cmd_show_all function."""

    def test_cmd_show_all_returns_complete_config(self, tmp_path, monkeypatch):
        """Test cmd_show_all() returns complete configuration."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        with patch("wks.api.config.get_config_path.get_config_path", return_value=config_path):
            result = cmd_show(show_all=True)
            
            # Execute the progress callback to get actual results
            def mock_update(msg: str, progress: float) -> None:
                pass
            
            result.progress_callback(mock_update, result)

        assert result.success is True
        assert isinstance(result.output, dict)
        assert "monitor" in result.output
        assert "vault" in result.output
        assert "database" in result.output
        assert "transform" in result.output

