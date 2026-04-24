from wks.api.mcp.McpConfig import McpConfig


def test_mcp_config_valid():
    cfg = McpConfig(installs={})
    assert cfg.installs == {}


def test_mcp_config_defaults():
    cfg = McpConfig()
    assert cfg.installs == {}
