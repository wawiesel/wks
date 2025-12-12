"""Coverage for MCP install_mcp_configs without mocks."""

import json
from pathlib import Path

import pytest

from wks.api.mcp.InstallResult import InstallResult
from wks.api.mcp.install_mcp_configs import install_mcp_configs


def test_install_mcp_configs_creates_files(tmp_path):
    targets = {"cursor": tmp_path / "cursor" / "mcp.json"}
    results = install_mcp_configs(clients=["cursor"], command_override=str(tmp_path / "bin" / "wksc"), targets=targets)
    assert results[0].status in {"created", "updated"}
    data = json.loads(targets["cursor"].read_text())
    assert data["mcpServers"]["wks"]["args"] == ["mcp", "run"]


def test_install_mcp_configs_invalid_existing_json(tmp_path):
    targets = {"claude": tmp_path / "claude" / "mcp.json"}
    targets["claude"].parent.mkdir(parents=True, exist_ok=True)
    targets["claude"].write_text("{not json")
    results = install_mcp_configs(clients=["claude"], command_override=str(tmp_path / "bin" / "wksc"), targets=targets)
    assert results[0].status == "updated"
    data = json.loads(targets["claude"].read_text())
    assert "wks" in data["mcpServers"]


def test_install_mcp_configs_unknown_client(tmp_path):
    with pytest.raises(ValueError):
        install_mcp_configs(clients=["unknown"], targets={"known": tmp_path / "known.json"})


def test_install_result_dataclass():
    res = InstallResult("c", Path("/tmp/file"), "created", "ok")
    assert res.client == "c"
    assert res.status == "created"


def test_install_mcp_configs_fallback_and_existing(tmp_path, monkeypatch):
    """Cover fallback resolution, backup path, non-dict servers, and unchanged state."""
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    cursor_target = tmp_path / "cursor" / "mcp.json"
    cursor_target.parent.mkdir(parents=True, exist_ok=True)
    cursor_target.write_text("[]")  # triggers backup + non-dict handling

    results = install_mcp_configs(clients=["cursor"], targets={"cursor": cursor_target})
    res = results[0]
    assert res.status == "updated"  # file existed, replaced after backup
    assert "backed up" in res.message
    assert cursor_target.with_suffix(".json.bak").exists()

    # Non-dict mcpServers should be reset to dict before update
    claude_target = tmp_path / "claude" / "mcp.json"
    claude_target.parent.mkdir(parents=True, exist_ok=True)
    claude_target.write_text(json.dumps({"mcpServers": ["bad"]}))
    res_claude = install_mcp_configs(clients=["claude"], targets={"claude": claude_target})[0]
    assert res_claude.status in {"created", "updated"}
    data = json.loads(claude_target.read_text())
    assert isinstance(data["mcpServers"], dict)
    assert "Updated MCP server entry" in res_claude.message

    # Second run should hit the unchanged path
    unchanged = install_mcp_configs(clients=["cursor"], targets={"cursor": cursor_target})[0]
    assert unchanged.status == "unchanged"
    assert "already" in unchanged.message.lower()


def test_install_mcp_configs_prefers_wksc_if_found(tmp_path, monkeypatch):
    exe = tmp_path / "bin" / "wksc"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n")
    monkeypatch.setattr("shutil.which", lambda cmd: str(exe))
    target = tmp_path / "cursor.json"

    result = install_mcp_configs(clients=["cursor"], targets={"cursor": target})[0]
    data = json.loads(target.read_text())
    assert data["mcpServers"]["wks"]["command"] == str(exe)
    assert result.status in {"created", "updated"}
