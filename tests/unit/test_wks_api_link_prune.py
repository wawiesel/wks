"""Unit tests for wks.api.link.prune."""

from unittest.mock import MagicMock

from wks.api.link.prune import prune


def test_link_prune_removes_orphaned_edges(monkeypatch):
    """Test that edges with invalid from_local_uri are removed."""
    mock_config = MagicMock()

    # Mock nodes database (empty = no valid nodes)
    mock_nodes_db = MagicMock()
    mock_nodes_col = MagicMock()
    mock_nodes_db.__enter__.return_value = mock_nodes_col
    mock_nodes_col.find.return_value = []

    # Mock edges database
    mock_edges_db = MagicMock()
    mock_edges_col = MagicMock()
    mock_edges_db.__enter__.return_value = mock_edges_col
    mock_edges_col.find.return_value = [
        {"_id": "1", "from_local_uri": "file:///orphan"},
    ]

    def db_factory(config, name):
        if name == "nodes":
            return mock_nodes_db
        return mock_edges_db

    monkeypatch.setattr("wks.api.link.prune.Database", db_factory)

    result = prune(mock_config)

    mock_edges_col.delete_many.assert_called_once()
    assert result["checked_count"] == 1


def test_link_prune_keeps_valid_edges(monkeypatch):
    """Test that edges with valid nodes are kept."""
    mock_config = MagicMock()

    # Mock nodes database with valid node
    mock_nodes_db = MagicMock()
    mock_nodes_col = MagicMock()
    mock_nodes_db.__enter__.return_value = mock_nodes_col
    mock_nodes_col.find.return_value = [{"local_uri": "file:///valid"}]

    # Mock edges database
    mock_edges_db = MagicMock()
    mock_edges_col = MagicMock()
    mock_edges_db.__enter__.return_value = mock_edges_col
    mock_edges_col.find.return_value = [
        {"_id": "1", "from_local_uri": "file:///valid", "to_local_uri": "file:///valid"},
    ]

    def db_factory(config, name):
        if name == "nodes":
            return mock_nodes_db
        return mock_edges_db

    monkeypatch.setattr("wks.api.link.prune.Database", db_factory)

    result = prune(mock_config)

    mock_edges_col.delete_many.assert_not_called()
    assert result["deleted_count"] == 0


def test_link_prune_handles_broken_local_target(monkeypatch):
    """Test pruning edges with broken local targets."""
    mock_config = MagicMock()

    mock_nodes_db = MagicMock()
    mock_nodes_col = MagicMock()
    mock_nodes_db.__enter__.return_value = mock_nodes_col
    mock_nodes_col.find.return_value = [{"local_uri": "file:///source"}]

    mock_edges_db = MagicMock()
    mock_edges_col = MagicMock()
    mock_edges_db.__enter__.return_value = mock_edges_col
    mock_edges_col.find.return_value = [
        {"_id": "1", "from_local_uri": "file:///source", "to_local_uri": "file:///nonexistent"},
    ]

    def db_factory(config, name):
        if name == "nodes":
            return mock_nodes_db
        return mock_edges_db

    monkeypatch.setattr("wks.api.link.prune.Database", db_factory)

    mock_path = MagicMock()
    mock_path.exists.return_value = False
    monkeypatch.setattr("wks.api.link.prune.Path", lambda p: mock_path)

    monkeypatch.setattr("wks.api.link.prune.uri_to_path", lambda u: "/tmp/foo")

    prune(mock_config)

    # Should delete edge with broken target
    mock_edges_col.delete_many.assert_called_once()
