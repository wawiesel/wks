"""Unit tests for wks.api.database.cmd_prune with dynamic dispatch."""

from unittest.mock import MagicMock, patch

import pytest


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
    @patch("wks.api.database._set_last_prune_timestamp.set_last_prune_timestamp")
    def test_prune_dispatch_single(self, mock_timestamp, mock_import, mock_load, mock_config):
        """Test dispatching to a single database handler."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config

        # Mock module and prune function
        mock_module = MagicMock()
        mock_module.prune.return_value = {"deleted_count": 5, "checked_count": 10}
        mock_import.return_value = mock_module

        result = cmd_prune(database="nodes")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        mock_import.assert_called_with("wks.api.monitor.prune")
        mock_module.prune.assert_called_once()
        assert result.output["deleted_count"] == 5
        assert result.output["checked_count"] == 10
        mock_timestamp.assert_called_with("nodes")

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.import_module")
    @patch("wks.api.database.cmd_prune.Database")
    @patch("wks.api.database._set_last_prune_timestamp.set_last_prune_timestamp")
    def test_prune_dispatch_all(self, mock_timestamp, mock_db, mock_import, mock_load, mock_config):
        """Test dispatching to all known databases."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config

        # Mock available databases
        mock_db.list_databases.return_value = ["nodes", "edges", "transform", "unknown_db"]

        # Mock modules
        mock_nodes = MagicMock()
        mock_nodes.prune.return_value = {"deleted_count": 1, "checked_count": 2}

        mock_edges = MagicMock()
        mock_edges.prune.return_value = {"deleted_count": 3, "checked_count": 4}

        mock_transform = MagicMock()
        mock_transform.prune.return_value = {"deleted_count": 0, "checked_count": 0}

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

        # Should have called prune for nodes, edges, transform
        assert mock_nodes.prune.call_count == 1
        assert mock_edges.prune.call_count == 1
        assert mock_transform.prune.call_count == 1

        # Should NOT have tried to prune unknown_db (not in DB_HANDLERS)
        assert mock_timestamp.call_count == 3
        mock_timestamp.assert_any_call("nodes")
        mock_timestamp.assert_any_call("edges")
        mock_timestamp.assert_any_call("transform")

        # Check aggregation
        assert result.output["deleted_count"] == 4  # 1 + 3 + 0
        assert result.output["checked_count"] == 6  # 2 + 4 + 0

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
        assert "Failed to import handler" in result.output["warnings"][0]


def test_get_status_path(monkeypatch, tmp_path):
    """Test status path generation."""
    from wks.api.database._get_status_path import _get_status_path

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    result = _get_status_path()
    assert result == wks_home / "database.json"


def test_set_and_get_prune_timestamp(monkeypatch, tmp_path):
    """Test setting and getting prune timestamp."""
    from wks.api.database._get_last_prune_timestamp import get_last_prune_timestamp
    from wks.api.database._set_last_prune_timestamp import set_last_prune_timestamp

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Initially no timestamp
    assert get_last_prune_timestamp("transform") is None

    # Set timestamp
    from datetime import datetime, timezone

    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    set_last_prune_timestamp("transform", ts)

    # Get it back
    result = get_last_prune_timestamp("transform")
    assert result is not None
    assert result.year == 2025


def test_should_prune_logic(monkeypatch, tmp_path):
    """Test should_prune logic."""
    from wks.api.database._set_last_prune_timestamp import set_last_prune_timestamp
    from wks.api.database._should_prune import should_prune

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # 0 = disabled
    assert should_prune("transform", 0) is False

    # Never pruned
    assert should_prune("transform", 3600) is True

    # Recently pruned
    set_last_prune_timestamp("transform")
    assert should_prune("transform", 3600) is False
