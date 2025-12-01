"""Tests for new MCP server tools."""

import json
from unittest.mock import MagicMock, patch
import pytest
from wks.mcp_server import MCPServer

@pytest.fixture
def mock_server():
    """Create a mock MCP server."""
    return MCPServer()

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "transform": {
            "cache_location": "~/.wks/cache",
            "cache_max_size_bytes": 1000,
            "database": "wks.transform"
        },
        "mongo": {
            "uri": "mongodb://localhost:27017"
        },
        "monitor": {
            "database": "wks.monitor"
        },
        "vault": {
            "database": "wks.vault"
        }
    }

class TestMCPServerNewTools:
    """Test new MCP tools."""

    def test_wks_config(self, mock_server, mock_config):
        """Test wksm_config tool."""
        result = mock_server._tool_config(mock_config)
        assert result == mock_config

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_transform(self, mock_controller_cls, mock_connect, mock_server, mock_config):
        """Test wksm_transform tool."""
        mock_controller = mock_controller_cls.return_value
        mock_controller.transform.return_value = "checksum123"
        
        result = mock_server._tool_transform(mock_config, "file.pdf", "docling", {})
        
        assert result == {"checksum": "checksum123"}
        mock_controller.transform.assert_called_once()

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_cat(self, mock_controller_cls, mock_connect, mock_server, mock_config):
        """Test wksm_cat tool."""
        mock_controller = mock_controller_cls.return_value
        mock_controller.get_content.return_value = "content"
        
        result = mock_server._tool_cat(mock_config, "checksum123")
        
        assert result == {"content": "content"}
        mock_controller.get_content.assert_called_once_with("checksum123")

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.diff.DiffController")
    def test_wks_diff(self, mock_diff_cls, mock_transform_cls, mock_connect, mock_server, mock_config):
        """Test wksm_diff tool."""
        mock_diff = mock_diff_cls.return_value
        mock_diff.diff.return_value = "diff result"
        
        result = mock_server._tool_diff(mock_config, "unified", "a", "b")
        
        assert result == {"diff": "diff result"}
        mock_diff.diff.assert_called_once_with("a", "b", "unified")

    @patch("wks.vault.load_vault")
    @patch("wks.vault.VaultController")
    def test_wks_vault_validate(self, mock_controller_cls, mock_load_vault, mock_server, mock_config):
        """Test wksm_vault_validate tool."""
        mock_controller = mock_controller_cls.return_value
        mock_controller.validate_vault.return_value = {"status": "ok"}
        
        result = mock_server._tool_vault_validate(mock_config)
        
        assert result == {"status": "ok"}
        mock_load_vault.assert_called_once_with(mock_config)
        mock_controller.validate_vault.assert_called_once()

    @patch("wks.vault.load_vault")
    @patch("wks.vault.VaultController")
    def test_wks_vault_fix_symlinks(self, mock_controller_cls, mock_load_vault, mock_server, mock_config):
        """Test wksm_vault_fix_symlinks tool."""
        mock_controller = mock_controller_cls.return_value
        # Mock result object
        mock_result = MagicMock()
        mock_result.notes_scanned = 10
        mock_result.links_found = 5
        mock_result.created = 2
        mock_result.failed = []
        mock_controller.fix_symlinks.return_value = mock_result
        
        result = mock_server._tool_vault_fix_symlinks(mock_config)
        
        assert result == {
            "notes_scanned": 10,
            "links_found": 5,
            "created": 2,
            "failed": []
        }
        mock_load_vault.assert_called_once_with(mock_config)
        mock_controller.fix_symlinks.assert_called_once()

    @patch("wks.db_helpers.connect_to_mongo")
    def test_wks_db_query(self, mock_connect, mock_server, mock_config):
        """Test wksm_db_* tools."""
        mock_client = mock_connect.return_value
        mock_coll = mock_client["wks"]["monitor"]
        mock_coll.find.return_value.limit.return_value = [{"path": "/a"}]
        
        result = mock_server._tool_db_query(mock_config, "monitor", {}, 10)
        
        assert result["count"] == 1
        assert result["results"][0]["path"] == "/a"
