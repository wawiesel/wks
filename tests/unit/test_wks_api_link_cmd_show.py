"""Unit tests for wks.api.link.cmd_show."""

import json

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_show import cmd_show


def test_cmd_show_from_direction(monkeypatch, tmp_path, minimal_config_dict):
    """Test showing links FROM a specific URI."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(lambda: cmd_show(uri="file:///test/note.md", direction="from"))

    assert result.success
    assert result.output["uri"] == "file:///test/note.md"
    assert result.output["direction"] == "from"
    assert "links" in result.output


def test_cmd_show_to_direction(monkeypatch, tmp_path, minimal_config_dict):
    """Test showing links TO a specific URI."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(lambda: cmd_show(uri="file:///test/target.md", direction="to"))

    assert result.success
    assert result.output["direction"] == "to"


def test_cmd_show_both_directions(monkeypatch, tmp_path, minimal_config_dict):
    """Test showing links in BOTH directions."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(lambda: cmd_show(uri="file:///test/note.md", direction="both"))

    assert result.success
    assert result.output["direction"] == "both"
