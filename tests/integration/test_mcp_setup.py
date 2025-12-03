import json
from pathlib import Path

import pytest

import wks.mcp_setup as mcp_setup


def _fake_command(tmp_path: Path):
    fake_bin = tmp_path / "bin" / "wksc"
    fake_bin.parent.mkdir(parents=True, exist_ok=True)
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    return str(fake_bin)


@pytest.mark.integration
def test_install_creates_configs(tmp_path, monkeypatch):
    cursor_path = tmp_path / "cursor" / "mcp.json"
    # Ensure parent directory exists
    cursor_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        mcp_setup,
        "MCP_CONFIG_TARGETS",
        {"cursor": cursor_path},
    )
    monkeypatch.setattr(mcp_setup.shutil, "which", lambda _: _fake_command(tmp_path))

    results = mcp_setup.install_mcp_configs()
    assert len(results) > 0, "No results returned"
    assert results[0].status == "created", f"Expected 'created', got '{results[0].status}'"
    assert cursor_path.exists(), "Config file was not created"
    data = json.loads(cursor_path.read_text())
    assert "mcpServers" in data, "mcpServers key missing"
    assert "wks" in data["mcpServers"], "wks server config missing"
    assert data["mcpServers"]["wks"]["command"].endswith("wksc")
    assert data["mcpServers"]["wks"]["args"] == ["mcp", "run"]


@pytest.mark.integration
def test_install_recovers_from_invalid_json(tmp_path, monkeypatch):
    config_path = tmp_path / "claude" / "mcp.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{not json")

    monkeypatch.setattr(
        mcp_setup,
        "MCP_CONFIG_TARGETS",
        {"claude": config_path},
    )
    monkeypatch.setattr(mcp_setup.shutil, "which", lambda _: _fake_command(tmp_path))

    results = mcp_setup.install_mcp_configs()
    assert len(results) > 0, "No results returned"
    assert results[0].status == "updated", f"Expected 'updated', got '{results[0].status}'"
    backup = config_path.with_suffix(".json.bak")
    assert backup.exists(), "Backup file was not created"
    assert config_path.exists(), "Config file was not recreated"
    data = json.loads(config_path.read_text())
    assert "mcpServers" in data, "mcpServers key missing"
    assert "wks" in data["mcpServers"], "wks server config missing"
