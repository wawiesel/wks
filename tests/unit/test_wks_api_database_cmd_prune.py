"""Unit tests for wks.api.database.cmd_prune with dynamic dispatch."""

from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import run_cmd


@pytest.fixture
def mock_config():
    """Create a mock WKSConfig."""
    config = MagicMock()
    config.database = MagicMock()
    return config


class TestCmdPrune:
    """Tests for cmd_prune function with dynamic dispatch."""

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    def test_prune_dispatch_single(self, mock_import, mock_load, mock_config, tmp_path, monkeypatch):
        """Test dispatching to a single database handler."""
        from wks.api.database.cmd_prune import cmd_prune

        wks_home = tmp_path / ".wks"
        wks_home.mkdir()
        monkeypatch.setenv("WKS_HOME", str(wks_home))

        mock_load.return_value = mock_config

        # Mock module and prune function
        mock_module = MagicMock()
        mock_module.prune.return_value = {"deleted_count": 5, "checked_count": 10, "warnings": []}
        mock_import.return_value = mock_module

        result = cmd_prune(database="nodes")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        assert set(result.output.keys()) == {"errors", "warnings", "database", "deleted_count", "checked_count"}
        assert result.output["errors"] == []
        assert result.output["warnings"] == []
        assert result.output["database"] == "nodes"
        mock_import.assert_called_with("wks.api.monitor.prune")
        mock_module.prune.assert_called_once()
        assert result.output["deleted_count"] == 5
        assert result.output["checked_count"] == 10
        assert "Pruned" in result.result

        # Verify timestamp was written
        assert (wks_home / "database.json").exists()

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_dispatch_all(self, mock_db, mock_import, mock_load, mock_config, tmp_path, monkeypatch):
        """Test dispatching to all known databases."""
        from wks.api.database.cmd_prune import cmd_prune

        wks_home = tmp_path / ".wks"
        wks_home.mkdir()
        monkeypatch.setenv("WKS_HOME", str(wks_home))

        mock_load.return_value = mock_config

        # Mock available databases
        mock_db.list_databases.return_value = ["nodes", "edges", "transform", "unknown_db"]

        # Mock modules
        mock_nodes = MagicMock()
        mock_nodes.prune.return_value = {"deleted_count": 1, "checked_count": 2, "warnings": []}

        mock_edges = MagicMock()
        mock_edges.prune.return_value = {"deleted_count": 3, "checked_count": 4, "warnings": []}

        mock_transform = MagicMock()
        mock_transform.prune.return_value = {"deleted_count": 0, "checked_count": 0, "warnings": []}

        def import_side_effect(name):
            if name == "wks.api.monitor.prune":
                return mock_nodes
            if name == "wks.api.link.prune":
                return mock_edges
            if name == "wks.api.transform.prune":
                return mock_transform
            raise ImportError(f"No module {name}")

        mock_import.side_effect = import_side_effect

        result = cmd_prune(database="all")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        assert set(result.output.keys()) == {"errors", "warnings", "database", "deleted_count", "checked_count"}
        assert result.output["errors"] == []
        assert result.output["warnings"] == []
        assert result.output["database"] == "all"

        # Should have called prune for nodes, edges, transform
        assert mock_nodes.prune.call_count == 1
        assert mock_edges.prune.call_count == 1
        assert mock_transform.prune.call_count == 1

        # Check aggregation
        assert result.output["deleted_count"] == 4  # 1 + 3 + 0
        assert result.output["checked_count"] == 6  # 2 + 4 + 0

        # Verify timestamps were written
        import json

        data = json.loads((wks_home / "database.json").read_text())
        assert "nodes" in data["prune_timestamps"]
        assert "edges" in data["prune_timestamps"]
        assert "transform" in data["prune_timestamps"]

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    def test_prune_handler_not_found(self, mock_import, mock_load, mock_config):
        """Test handling of missing handler for a specific target."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config

        # Asking for a database that has no handler
        result = cmd_prune(database="unknown_db")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        assert result.output["errors"] == []
        assert result.output["database"] == "unknown_db"
        assert result.output["deleted_count"] == 0
        assert result.output["checked_count"] == 0
        mock_import.assert_not_called()
        assert "No prune handler found" in result.output["warnings"][0]

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    def test_prune_import_error(self, mock_import, mock_load, mock_config):
        """Test graceful handling of ImportError."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config
        mock_import.side_effect = ImportError("Broken module")

        result = cmd_prune(database="nodes")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        assert result.output["errors"] == []
        assert result.output["database"] == "nodes"
        assert result.output["deleted_count"] == 0
        assert result.output["checked_count"] == 0
        assert "Failed to import handler" in result.output["warnings"][0]

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    def test_cmd_prune_updates_timestamp(self, mock_import, mock_load, mock_config, tmp_path, monkeypatch):
        """Test that cmd_prune updates the last prune timestamp on success."""
        from wks.api.database.cmd_prune import cmd_prune

        wks_home = tmp_path / ".wks"
        wks_home.mkdir()
        monkeypatch.setenv("WKS_HOME", str(wks_home))

        mock_load.return_value = mock_config
        mock_module = MagicMock()
        mock_module.prune.return_value = {"deleted_count": 0, "checked_count": 0, "warnings": []}
        mock_import.return_value = mock_module

        result = cmd_prune(database="nodes")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        status_file = wks_home / "database.json"
        assert status_file.exists()
        import json

        data = json.loads(status_file.read_text())
        assert "prune_timestamps" in data
        assert "nodes" in data["prune_timestamps"]


def test_cmd_prune_handler_error(tracked_wks_config):
    """Test cmd_prune handles error from a handler."""
    from wks.api.database.cmd_prune import cmd_prune

    # Mock import_module to return a mock module whose prune() raises Exception
    mock_module = MagicMock()
    mock_module.prune.side_effect = Exception("Prune failed")

    with patch("wks.api.database.cmd_prune.import_module", return_value=mock_module):
        # We need at least one target to trigger the loop
        result = run_cmd(cmd_prune, database="nodes")
        assert result.success is True  # It reports as warning, not failure
        assert result.output["errors"] == []
        assert result.output["database"] == "nodes"
        assert result.output["deleted_count"] == 0
        assert result.output["checked_count"] == 0
        assert "Prune failed" in result.output["warnings"][0]
