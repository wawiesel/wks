"""Tests for new MCP server tools."""

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
            "database": "wks.transform",
        },
        "mongo": {"uri": "mongodb://localhost:27017"},
        "monitor": {"database": "wks.monitor"},
        "vault": {"database": "wks.vault"},
    }


class TestMCPServerNewTools:
    """Test new MCP tools - verify MCPResult structure."""

    def test_wks_config(self, mock_server, mock_config):
        """Test wksm_config tool returns MCPResult format."""
        result = mock_server._tool_config(mock_config)
        assert result["success"] is True
        assert result["data"] == mock_config
        assert "messages" in result

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_transform(
        self, mock_controller_cls, mock_connect, mock_wks_config, mock_server, mock_config, tmp_path
    ):
        """Test wksm_transform tool returns MCPResult format."""
        # Mock WKSConfig.load()
        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.transform.return_value = "checksum123"

        # Create a test file that exists
        test_file = tmp_path / "file.pdf"
        test_file.write_bytes(b"PDF content")

        result = mock_server._tool_transform(mock_config, str(test_file), "docling", {})

        assert result["success"] is True
        assert result["data"]["checksum"] == "checksum123"
        mock_controller.transform.assert_called_once()

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_cat(self, mock_controller_cls, mock_connect, mock_wks_config, mock_server, mock_config):
        """Test wksm_cat tool returns MCPResult format."""
        # Mock WKSConfig.load()
        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.get_content.return_value = "content"

        result = mock_server._tool_cat(mock_config, "checksum123")

        assert result["success"] is True
        assert result["data"]["content"] == "content"
        mock_controller.get_content.assert_called_once_with("checksum123")

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.diff.DiffController")
    def test_wks_diff(self, mock_diff_cls, mock_transform_cls, mock_connect, mock_server, mock_config):
        """Test wksm_diff tool returns MCPResult format."""
        mock_diff = mock_diff_cls.return_value
        mock_diff.diff.return_value = "diff result"

        result = mock_server._tool_diff(mock_config, "unified", "a", "b")

        assert result["success"] is True
        assert result["data"]["diff"] == "diff result"
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

        assert result == {"notes_scanned": 10, "links_found": 5, "created": 2, "failed": []}
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

    @patch("wks.mcp_server.ServiceController")
    def test_wks_service(self, mock_service_ctrl, mock_server, mock_config):
        """Test wksm_service tool returns MCPResult format."""
        mock_status = MagicMock()
        mock_status.to_dict.return_value = {"service": {"running": True}}
        mock_service_ctrl.get_status.return_value = mock_status

        result = mock_server._tool_service(mock_config)

        assert result["success"] is True
        assert result["data"]["service"]["running"] is True
        mock_service_ctrl.get_status.assert_called_once()

    @patch("wks.config.WKSConfig")
    @patch("wks.utils.expand_path")
    def test_wks_transform_file_not_found(self, mock_expand, mock_wks_config, mock_server, mock_config, tmp_path):
        """Test wksm_transform tool handles file not found."""
        nonexistent = tmp_path / "nonexistent.pdf"
        mock_expand.return_value = nonexistent

        result = mock_server._tool_transform(mock_config, str(nonexistent), "docling", {})

        assert result["success"] is False
        assert "File not found" in result["messages"][0]["text"]

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.utils.expand_path")
    def test_wks_transform_value_error(
        self,
        mock_expand,
        mock_controller_cls,
        mock_connect,
        mock_wks_config,
        mock_server,
        mock_config,
        tmp_path,
    ):
        """Test wksm_transform tool handles ValueError."""
        test_file = tmp_path / "file.pdf"
        test_file.write_bytes(b"PDF content")
        mock_expand.return_value = test_file

        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.transform.side_effect = ValueError("Invalid engine")

        result = mock_server._tool_transform(mock_config, str(test_file), "docling", {})

        assert result["success"] is False
        assert "Invalid input" in result["messages"][0]["text"]

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.utils.expand_path")
    def test_wks_transform_runtime_error(
        self,
        mock_expand,
        mock_controller_cls,
        mock_connect,
        mock_wks_config,
        mock_server,
        mock_config,
        tmp_path,
    ):
        """Test wksm_transform tool handles RuntimeError."""
        test_file = tmp_path / "file.pdf"
        test_file.write_bytes(b"PDF content")
        mock_expand.return_value = test_file

        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.transform.side_effect = RuntimeError("Transform failed")

        result = mock_server._tool_transform(mock_config, str(test_file), "docling", {})

        assert result["success"] is False
        assert "Transform failed" in result["messages"][0]["text"]

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.utils.expand_path")
    def test_wks_transform_unexpected_error(
        self,
        mock_expand,
        mock_controller_cls,
        mock_connect,
        mock_wks_config,
        mock_server,
        mock_config,
        tmp_path,
    ):
        """Test wksm_transform tool handles unexpected errors."""
        test_file = tmp_path / "file.pdf"
        test_file.write_bytes(b"PDF content")
        mock_expand.return_value = test_file

        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.transform.side_effect = KeyError("Unexpected")

        result = mock_server._tool_transform(mock_config, str(test_file), "docling", {})

        assert result["success"] is False
        assert "Unexpected error" in result["messages"][0]["text"]

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_cat_file_not_found(self, mock_controller_cls, mock_connect, mock_wks_config, mock_server, mock_config):
        """Test wksm_cat tool handles FileNotFoundError."""
        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.get_content.side_effect = FileNotFoundError("Cache entry not found")

        result = mock_server._tool_cat(mock_config, "bad_checksum")

        assert result["success"] is False
        assert "File or cache entry not found" in result["messages"][0]["text"]

    @patch("wks.config.WKSConfig")
    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    def test_wks_cat_unexpected_error(
        self, mock_controller_cls, mock_connect, mock_wks_config, mock_server, mock_config
    ):
        """Test wksm_cat tool handles unexpected errors."""
        mock_cfg = MagicMock()
        mock_cfg.transform.cache.location = "~/.wks/cache"
        mock_cfg.transform.cache.max_size_bytes = 1000
        mock_cfg.transform.database = "wks.transform"
        mock_cfg.mongo.uri = "mongodb://localhost:27017"
        mock_wks_config.load.return_value = mock_cfg

        mock_controller = mock_controller_cls.return_value
        mock_controller.get_content.side_effect = ValueError("Unexpected error")

        result = mock_server._tool_cat(mock_config, "checksum123")

        assert result["success"] is False
        assert "Failed to retrieve content" in result["messages"][0]["text"]

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.diff.DiffController")
    def test_wks_diff_value_error(self, mock_diff_cls, mock_transform_cls, mock_connect, mock_server, mock_config):
        """Test wksm_diff tool handles ValueError."""
        mock_diff = mock_diff_cls.return_value
        mock_diff.diff.side_effect = ValueError("Invalid input")

        result = mock_server._tool_diff(mock_config, "unified", "a", "b")

        assert result["success"] is False
        assert "Invalid input" in result["messages"][0]["text"]

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.diff.DiffController")
    def test_wks_diff_runtime_error(self, mock_diff_cls, mock_transform_cls, mock_connect, mock_server, mock_config):
        """Test wksm_diff tool handles RuntimeError."""
        mock_diff = mock_diff_cls.return_value
        mock_diff.diff.side_effect = RuntimeError("Diff failed")

        result = mock_server._tool_diff(mock_config, "unified", "a", "b")

        assert result["success"] is False
        assert "Diff failed" in result["messages"][0]["text"]

    @patch("wks.db_helpers.connect_to_mongo")
    @patch("wks.transform.TransformController")
    @patch("wks.diff.DiffController")
    def test_wks_diff_unexpected_error(self, mock_diff_cls, mock_transform_cls, mock_connect, mock_server, mock_config):
        """Test wksm_diff tool handles unexpected errors."""
        mock_diff = mock_diff_cls.return_value
        mock_diff.diff.side_effect = KeyError("Unexpected")

        result = mock_server._tool_diff(mock_config, "unified", "a", "b")

        assert result["success"] is False
        assert "Unexpected error" in result["messages"][0]["text"]

    @patch("wks.mcp_server.load_config")
    def test_call_tool_not_found(self, mock_load_config, mock_config):
        """Test call_tool returns error for unknown tool."""
        from wks.mcp_server import call_tool

        mock_load_config.return_value = mock_config

        result = call_tool("unknown_tool", {})

        assert result["success"] is False
        assert "Tool not found" in result["messages"][0]["text"]

    @patch("wks.mcp_server.load_config")
    def test_call_tool_success(self, mock_load_config, mock_config):
        """Test call_tool successfully calls a tool."""
        from wks.mcp_server import call_tool

        mock_load_config.return_value = mock_config

        result = call_tool("wksm_config", {})

        assert result["success"] is True
        assert "data" in result
