"""Unit tests for wks.api.mcp.McpConfig module."""

from wks.api.mcp.McpConfig import McpConfig


def test_mcp_config_valid():
    cfg = McpConfig(installs={})
    assert cfg.installs == {}


def test_mcp_config_defaults():
    # Installs has default factory
    cfg = McpConfig()
    assert cfg.installs == {}
