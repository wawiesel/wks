"""Config list command tests.

Requirements Satisfied:

- CONFIG.1
- CONFIG.3
- CONFIG.6
"""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.cmd_list import cmd_list


@pytest.mark.config
def test_cmd_list_success(wks_home):
    result = run_cmd(cmd_list)
    assert result.success is True
    assert "monitor" in result.output["content"]["sections"]
    assert "database" in result.output["content"]["sections"]
    assert "daemon" in result.output["content"]["sections"]
    assert result.output["config_path"]


@pytest.mark.config
def test_cmd_list_missing_config(tmp_path, monkeypatch):
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    tmp_path.mkdir(parents=True, exist_ok=True)

    result = run_cmd(cmd_list)
    assert result.success is False
    assert "not found" in result.output["errors"][0].lower()


@pytest.mark.config
def test_cmd_list_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text("{not json")

    result = run_cmd(cmd_list)
    assert result.success is False
    assert "invalid json" in result.output["errors"][0].lower()
