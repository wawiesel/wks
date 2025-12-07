"""Unit tests for wks.api.database.cmd_show module."""

import json
from unittest.mock import patch

import pytest

from wks.api.database.cmd_show import cmd_show
from wks.api.database.Database import Database

pytestmark = pytest.mark.db


class TestCmdShow:
    """Test cmd_show function."""

    def test_cmd_show_success(self, monkeypatch):
        """Test cmd_show with valid query."""
        from unittest.mock import MagicMock
        from wks.api.database.DbConfig import DbConfig

        mock_result = {"results": [{"_id": "1", "path": "/test"}], "count": 1}
        mock_config = MagicMock()
        mock_db_config = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        mock_config.database = mock_db_config

        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config) as mock_load:
            with patch.object(Database, "query", return_value=mock_result) as mock_query:
                result = cmd_show(collection="monitor", query_filter='{"status": "active"}', limit=10)

                assert result.success is True
                assert result.announce == "Querying monitor database..."
                assert "Found 1 document(s)" in result.result
                assert "results" in result.output
                assert "count" in result.output
                mock_query.assert_called_once_with(mock_db_config, "monitor", {"status": "active"}, 10)

    def test_cmd_show_no_filter(self, monkeypatch):
        """Test cmd_show with no filter."""
        from unittest.mock import MagicMock
        from wks.api.database.DbConfig import DbConfig

        mock_result = {"results": [], "count": 0}
        mock_config = MagicMock()
        mock_db_config = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        mock_config.database = mock_db_config

        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config) as mock_load:
            with patch.object(Database, "query", return_value=mock_result) as mock_query:
                result = cmd_show(collection="monitor", query_filter=None, limit=50)

                assert result.success is True
                assert "results" in result.output
                assert "count" in result.output
                mock_query.assert_called_once_with(mock_db_config, "monitor", None, 50)

    def test_cmd_show_invalid_json(self, monkeypatch):
        """Test cmd_show with invalid JSON."""
        # The JSON parsing happens in cmd_show, and it catches JSONDecodeError
        result = cmd_show(collection="monitor", query_filter='{"invalid": json}', limit=50)

        assert result.success is False
        assert "Invalid JSON" in result.result
        assert "error" in result.output

    def test_cmd_show_empty_string_filter(self, monkeypatch):
        """Test cmd_show with empty string filter."""
        from unittest.mock import MagicMock
        from wks.api.database.DbConfig import DbConfig

        mock_result = {"results": [], "count": 0}
        mock_config = MagicMock()
        mock_db_config = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        mock_config.database = mock_db_config

        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config) as mock_load:
            with patch.object(Database, "query", return_value=mock_result) as mock_query:
                result = cmd_show(collection="monitor", query_filter="", limit=50)

                assert result.success is True
                mock_query.assert_called_once_with(mock_db_config, "monitor", None, 50)

    def test_cmd_show_query_fails(self, monkeypatch):
        """Test cmd_show when query raises exception."""
        with patch.object(Database, "query", side_effect=Exception("Connection failed")) as mock_query:
            result = cmd_show(collection="monitor", query_filter='{"status": "active"}', limit=50)

            assert result.success is False
            assert "Query failed" in result.result
            assert "error" in result.output
            assert "Connection failed" in result.output["error"]

    def test_cmd_show_complex_filter(self, monkeypatch):
        """Test cmd_show with complex filter."""
        from unittest.mock import MagicMock
        from wks.api.database.DbConfig import DbConfig

        mock_result = {"results": [{"_id": "1"}], "count": 1}
        complex_filter = '{"age": {"$gt": 18}, "name": {"$regex": "^A"}}'
        mock_config = MagicMock()
        mock_db_config = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        mock_config.database = mock_db_config

        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config) as mock_load:
            with patch.object(Database, "query", return_value=mock_result) as mock_query:
                result = cmd_show(collection="users", query_filter=complex_filter, limit=100)

                assert result.success is True
                parsed_filter = json.loads(complex_filter)
                mock_query.assert_called_once_with(mock_db_config, "users", parsed_filter, 100)
