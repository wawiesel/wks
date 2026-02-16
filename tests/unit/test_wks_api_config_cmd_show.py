"""Unit tests for config cmd_show.

Requirements Satisfied:

- CONFIG.4
- CONFIG.6
"""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.cmd_show import cmd_show

pytestmark = pytest.mark.config


class TestCmdShow:
    def test_cmd_show_no_section(self, wks_home_with_priority):
        result = run_cmd(cmd_show, "")
        assert not result.success
        assert set(result.output.keys()) == {"errors", "warnings", "section", "content", "config_path"}
        assert result.output["warnings"] == []
        assert result.output["errors"]
        assert "Unknown section" in result.output["errors"][0]
        assert result.output["section"] == ""
        assert result.output["content"] == {}

    def test_cmd_show_with_valid_section(self, wks_home_with_priority):
        result = run_cmd(cmd_show, "monitor")
        assert result.success
        assert set(result.output.keys()) == {"errors", "warnings", "section", "content", "config_path"}
        assert result.output["errors"] == []
        assert result.output["warnings"] == []
        assert result.output["section"] == "monitor"
        assert isinstance(result.output["content"], dict)
        assert result.output["config_path"]

    def test_cmd_show_with_invalid_section(self, wks_home_with_priority):
        result = run_cmd(cmd_show, "invalid_section")
        assert not result.success
        assert set(result.output.keys()) == {"errors", "warnings", "section", "content", "config_path"}
        assert result.output["errors"]
        assert result.output["warnings"] == []
        assert result.output["section"] == "invalid_section"
        assert result.output["content"] == {}

    def test_cmd_show_invalid_config_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        (tmp_path / "config.json").write_text("{invalid json")

        result = run_cmd(cmd_show, "monitor")
        assert result.success is False
        assert set(result.output.keys()) == {"errors", "warnings", "section", "content", "config_path"}
        assert result.output["section"] == "monitor"
        assert result.output["warnings"] == []
        assert result.output["errors"]
