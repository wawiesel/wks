"""Unit tests for wks.api.database.cmd_prune."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from wks.api.database.cmd_prune import cmd_prune


@pytest.fixture
def mock_config():
    """Create a mock WKSConfig."""
    config = MagicMock()
    config.database = MagicMock()
    return config


class TestCmdPrune:
    """Tests for cmd_prune function."""

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_nodes(self, mock_database, mock_load, mock_config, tmp_path):
        """Test prune nodes removes non-existent file documents."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config
        mock_nodes_db = MagicMock()

        def db_side_effect(config, name):
            mock_ctx = MagicMock()
            if name == "nodes":
                mock_ctx.__enter__.return_value = mock_nodes_db
            return mock_ctx

        mock_database.side_effect = db_side_effect

        existing_file = tmp_path / "exist.md"
        existing_file.touch()
        existing_uri = f"file://host{existing_file}"
        missing_uri = f"file://host{tmp_path / 'gone.md'}"

        mock_nodes_db.find.return_value = [
            {"_id": "1", "local_uri": existing_uri},
            {"_id": "2", "local_uri": missing_uri},
        ]
        mock_nodes_db.delete_many.return_value = 1

        result = cmd_prune(database="nodes")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        mock_nodes_db.delete_many.assert_called()
        args, _ = mock_nodes_db.delete_many.call_args
        assert args[0]["_id"]["$in"] == ["2"]
        assert result.output["deleted_count"] == 1
        assert result.output["checked_count"] == 2

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_edges(self, mock_database, mock_load, mock_config):
        """Test prune edges removes edges with invalid source/target."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config
        mock_nodes_db = MagicMock()
        mock_edges_db = MagicMock()

        def db_side_effect(config, name):
            mock_ctx = MagicMock()
            if name == "nodes":
                mock_ctx.__enter__.return_value = mock_nodes_db
            elif name == "edges":
                mock_ctx.__enter__.return_value = mock_edges_db
            return mock_ctx

        mock_database.side_effect = db_side_effect

        valid_uri = "file://host/valid.md"

        # Valid nodes contains only valid_uri
        mock_nodes_db.find.return_value = [{"local_uri": valid_uri}]

        # Edges
        # 1. Valid -> Valid (keep)
        # 2. Invalid -> Valid (delete, bad source)
        # 3. Valid -> Unmonitored Existing (keep, FS check passes)
        # 4. Valid -> Broken (delete, FS check fails)
        # 5. Valid -> Remote (to_local_uri is None) (keep)
        # 6. Valid -> Broken Local BUT Has Remote Fallback (keep)
        mock_edges_db.find.return_value = [
            {
                "_id": "e1",
                "from_local_uri": valid_uri,
                "to_local_uri": valid_uri,
                "to_remote_uri": None,
                "from_remote_uri": None,
            },
            {
                "_id": "e2",
                "from_local_uri": "bad",
                "to_local_uri": valid_uri,
                "to_remote_uri": None,
                "from_remote_uri": None,
            },
            {
                "_id": "e3",
                "from_local_uri": valid_uri,
                "to_local_uri": "file:///unmonitored/exists",
                "to_remote_uri": None,
                "from_remote_uri": None,
            },
            {
                "_id": "e4",
                "from_local_uri": valid_uri,
                "to_local_uri": "file:///broken/missing",
                "to_remote_uri": None,
                "from_remote_uri": None,
            },
            {
                "_id": "e5",
                "from_local_uri": valid_uri,
                "to_local_uri": None,
                "to_remote_uri": "http://foo",
                "from_remote_uri": None,
            },
            {
                "_id": "e6",
                "from_local_uri": valid_uri,
                "to_local_uri": "file:///broken/missing",
                "to_remote_uri": "http://foo",
                "from_remote_uri": None,
            },
        ]
        mock_edges_db.delete_many.return_value = 2

        with (
            patch("wks.api.database.cmd_prune.uri_to_path") as mock_u2p,
            patch("wks.api.database.cmd_prune.Path") as mock_path,
        ):
            # Map URIs to paths
            mock_u2p.side_effect = lambda u: u.replace("file://", "")

            # Mock filesystem existence
            # Path(path_str).exists()
            def path_side_effect(path_str):
                m = MagicMock()
                # /path/to/valid covered by DB check
                m.exists.return_value = "exists" in str(path_str) or "valid" in str(path_str)
                return m

            mock_path.side_effect = path_side_effect

            result = cmd_prune(database="edges")
            for _ in result.progress_callback(result):
                pass

        assert result.success is True
        mock_edges_db.delete_many.assert_called()
        args, _ = mock_edges_db.delete_many.call_args
        deleted_ids = args[0]["_id"]["$in"]

        # e2: Bad source -> Delete
        assert "e2" in deleted_ids

        # e3: Bad DB target but exists on FS -> Keep
        assert "e3" not in deleted_ids

        # e4: Bad DB target AND missing on FS -> Delete
        assert "e4" in deleted_ids

        # e5: Remote target (no local uri) -> Keep
        assert "e5" not in deleted_ids

        # e6: Broken Local but Has Remote -> Keep
        assert "e6" not in deleted_ids

        assert "e1" not in deleted_ids
        assert result.output["deleted_count"] == 2

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.requests.head")
    @patch("wks.api.database.cmd_prune._has_internet")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_edges_remote(self, mock_database, mock_has_internet, mock_head, mock_load, mock_config, tmp_path):
        """Test remote pruning logic (unset instead of delete)."""
        mock_load.return_value = mock_config
        valid_uri = "file:///valid/path"

        mock_nodes_db = MagicMock()
        mock_edges_db = MagicMock()

        def db_side_effect(config, name):
            mock_ctx = MagicMock()
            if name == "nodes":
                mock_ctx.__enter__.return_value = mock_nodes_db
            elif name == "edges":
                mock_ctx.__enter__.return_value = mock_edges_db
            return mock_ctx

        mock_database.side_effect = db_side_effect
        mock_has_internet.return_value = True

        mock_nodes_db.find.return_value = [{"local_uri": valid_uri}]

        # Edges
        # e1: Remote 200 (Keep)
        # e2: Remote 404 (Unset Remote)
        # e3: Remote 410 (Unset Remote)
        # e4: Remote Timeout (Keep)
        # e5: Local Valid, Remote 404 (Local populated -> Skip Remote Check)
        mock_edges_db.find.return_value = [
            {
                "_id": "e1",
                "from_local_uri": valid_uri,
                "to_local_uri": "",
                "to_remote_uri": "http://ok",
                "from_remote_uri": None,
            },
            {
                "_id": "e2",
                "from_local_uri": valid_uri,
                "to_local_uri": None,
                "to_remote_uri": "http://gone",
                "from_remote_uri": None,
            },
            {
                "_id": "e3",
                "from_local_uri": valid_uri,
                "to_local_uri": None,
                "to_remote_uri": "http://vanished",
                "from_remote_uri": None,
            },
            {
                "_id": "e4",
                "from_local_uri": valid_uri,
                "to_local_uri": None,
                "to_remote_uri": "http://timeout",
                "from_remote_uri": None,
            },
            {
                "_id": "e5",
                "from_local_uri": valid_uri,
                "to_local_uri": valid_uri,
                "to_remote_uri": "http://gone",
                "from_remote_uri": None,
            },
        ]

        # Mock responses
        def head_side_effect(url, timeout=5):
            m = MagicMock()
            if "ok" in url:
                m.status_code = 200
            elif "gone" in url:
                m.status_code = 404
            elif "vanished" in url:
                m.status_code = 410
            elif "timeout" in url:
                raise requests.Timeout("Timeout")
            return m

        mock_head.side_effect = head_side_effect

        result = cmd_prune(database="edges", remote=True)
        for _ in result.progress_callback(result):
            pass

        assert result.success is True

        # Verify deletions (e2 and e3 should be deleted as both Local and Remote are gone)
        mock_edges_db.delete_many.assert_called_once()
        args, _ = mock_edges_db.delete_many.call_args
        deleted_ids = args[0]["_id"]["$in"]
        assert "e2" in deleted_ids
        assert "e3" in deleted_ids
        assert "e1" not in deleted_ids
        assert "e4" not in deleted_ids
        assert "e5" not in deleted_ids

        # Verify updates (should not happen for e2/e3 as they are deleted)
        mock_edges_db.update_many.assert_not_called()

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.requests.head")
    @patch("wks.api.database.cmd_prune._has_internet")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_edges_from_remote(
        self, mock_database, mock_has_internet, mock_head, mock_load, mock_config, tmp_path
    ):
        """Test from_remote_uri validation logic."""
        mock_load.return_value = mock_config
        valid_uri = "file:///valid/path"

        mock_nodes_db = MagicMock()
        mock_edges_db = MagicMock()

        def db_side_effect(config, name):
            mock_ctx = MagicMock()
            if name == "nodes":
                mock_ctx.__enter__.return_value = mock_nodes_db
            elif name == "edges":
                mock_ctx.__enter__.return_value = mock_edges_db
            return mock_ctx

        mock_database.side_effect = db_side_effect
        mock_has_internet.return_value = True

        mock_nodes_db.find.return_value = [{"local_uri": valid_uri}]

        # Edges
        # e1: From Remote 200 (Keep)
        # e2: From Remote 404 (Unset from_remote_uri)
        mock_edges_db.find.return_value = [
            {
                "_id": "e1",
                "from_local_uri": valid_uri,
                "to_local_uri": valid_uri,
                "from_remote_uri": "http://ok",
                "to_remote_uri": None,
            },
            {
                "_id": "e2",
                "from_local_uri": valid_uri,
                "to_local_uri": valid_uri,
                "from_remote_uri": "http://gone",
                "to_remote_uri": None,
            },
        ]

        def head_side_effect(url, timeout=5):
            m = MagicMock()
            if "ok" in url:
                m.status_code = 200
            elif "gone" in url:
                m.status_code = 404
            return m

        mock_head.side_effect = head_side_effect

        result = cmd_prune(database="edges", remote=True)
        for _ in result.progress_callback(result):
            pass

        assert result.success is True

        # Verify deletions (0, as local targets are valid)
        mock_edges_db.delete_many.assert_not_called()

        # Verify updates (unset from_remote_uri for e2)
        mock_edges_db.update_many.assert_called_once()
        args, _ = mock_edges_db.update_many.call_args

        updated_ids = args[0]["_id"]["$in"]
        assert "e1" not in updated_ids
        assert "e2" in updated_ids

        unset_op = args[1]
        assert "$unset" in unset_op
        assert "from_remote_uri" in unset_op["$unset"]

    @patch("wks.api.config.WKSConfig.WKSConfig.load")
    @patch("wks.api.database.cmd_prune.Database")
    def test_prune_all(self, mock_database, mock_load, mock_config, tmp_path):
        """Test prune all runs both nodes and edges."""
        from wks.api.database.cmd_prune import cmd_prune

        mock_load.return_value = mock_config
        mock_nodes_db = MagicMock()
        mock_edges_db = MagicMock()

        def db_side_effect(config, name):
            mock_ctx = MagicMock()
            if name == "nodes":
                mock_ctx.__enter__.return_value = mock_nodes_db
            elif name == "edges":
                mock_ctx.__enter__.return_value = mock_edges_db
            return mock_ctx

        mock_database.side_effect = db_side_effect

        # Mock Data
        mock_nodes_db.find.return_value = []  # No nodes, or empty logic for simplicity
        mock_edges_db.find.return_value = []
        mock_nodes_db.delete_many.return_value = 0
        mock_edges_db.delete_many.return_value = 0

        result = cmd_prune(database="all")
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        # Both DBs should have been accessed
        assert mock_nodes_db.find.called
        assert mock_edges_db.find.called
