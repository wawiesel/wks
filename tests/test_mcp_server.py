"""Comprehensive tests for MCP Server."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from wks.config import MongoSettings, MonitorConfig, VaultConfig, WKSConfig
from wks.mcp_server import MCPServer


@pytest.fixture
def mock_config():
    """Mock WKSConfig."""
    config = MagicMock(spec=WKSConfig)
    config.monitor = MonitorConfig(
        include_paths=["~"],
        exclude_paths=["~/Library"],
        include_dirnames=[],
        exclude_dirnames=[],
        include_globs=[],
        exclude_globs=[],
        managed_directories={"~": 100},
        priority={"depth_multiplier": 0.9},
        database="wks.monitor",
        touch_weight=0.1,
        max_documents=1000000,
        prune_interval_secs=300.0,
    )
    config.vault = VaultConfig(
        base_dir="~/_vault",
        wks_dir=".wks",
        update_frequency_seconds=3600,
        database="wks.vault",
        vault_type="obsidian",
    )
    config.mongo = MongoSettings(uri="mongodb://localhost:27017")
    return config


@pytest.fixture
def mcp_server():
    """Create MCP server instance with mocked streams."""
    input_stream = io.StringIO()
    output_stream = io.StringIO()
    server = MCPServer(input_stream=input_stream, output_stream=output_stream)
    return server, input_stream, output_stream


class TestMCPServer:
    """Test MCP Server functionality."""

    def test_initialize(self, mcp_server):
        """Test initialize request."""
        server, input_stream, output_stream = mcp_server

        # Prepare request
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        input_stream.write(json.dumps(request) + "\n")
        input_stream.seek(0)

        # Run one iteration
        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        # Check response
        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 1
        assert response["result"]["serverInfo"]["name"] == "wks-mcp-server"

    def test_list_tools(self, mcp_server):
        """Test tools/list request."""
        server, _input_stream, output_stream = mcp_server

        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 2
        tools = response["result"]["tools"]
        assert len(tools) > 0
        assert any(t["name"] == "wksm_monitor_status" for t in tools)

    @patch("wks.config.WKSConfig.load")
    @patch("wks.mcp_server.MonitorController")
    def test_call_tool_monitor_status(self, mock_controller, mock_load_config, mcp_server, mock_config):
        """Test calling wksm_monitor_status tool."""
        server, _input_stream, output_stream = mcp_server
        mock_load_config.return_value = mock_config

        mock_status = MagicMock()
        mock_status.model_dump.return_value = {"tracked_files": 100}
        mock_controller.get_status.return_value = mock_status

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "wksm_monitor_status", "arguments": {}},
        }

        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 3
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["tracked_files"] == 100

    @patch("wks.config.WKSConfig.load")
    @patch("wks.mcp_server.MonitorController")
    def test_call_tool_monitor_check(self, mock_controller, mock_load_config, mcp_server, mock_config):
        """Test calling wksm_monitor_check tool."""
        server, _input_stream, output_stream = mcp_server
        mock_load_config.return_value = mock_config

        mock_controller.check_path.return_value = {"is_monitored": True}

        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "wksm_monitor_check", "arguments": {"path": "/tmp/test.txt"}},
        }

        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 4
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["is_monitored"] is True

    def test_call_unknown_tool(self, mcp_server):
        """Test calling unknown tool."""
        server, _input_stream, output_stream = mcp_server

        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 5
        assert "error" in response
        assert response["error"]["code"] == -32601

    @patch("wks.config.WKSConfig.load")
    @patch("wks.mcp_server.MonitorController")
    def test_call_tool_missing_params(self, mock_controller, mock_load_config, mcp_server, mock_config):  # noqa: ARG002
        """Test calling tool with missing params."""
        server, _input_stream, output_stream = mcp_server
        mock_load_config.return_value = mock_config

        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "wksm_monitor_check",
                "arguments": {},  # Missing 'path'
            },
        }

        with patch.object(server, "_read_message", side_effect=[request, None]):
            server.run()

        output = output_stream.getvalue()
        response = json.loads(output)

        assert response["id"] == 6
        assert "error" in response
        assert "Missing required parameters" in response["error"]["message"]

    def test_lsp_mode_framing(self, mcp_server):
        """Test LSP-style Content-Length framing."""
        server, input_stream, output_stream = mcp_server

        payload = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

        input_stream.write(message)
        input_stream.seek(0)

        server.run()

        output = output_stream.getvalue()
        # Response should also be framed
        assert "Content-Length:" in output
        assert "jsonrpc" in output
