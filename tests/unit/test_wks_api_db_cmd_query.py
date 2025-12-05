"""Unit tests for wks.api.db.cmd_query module."""

import json
import pytest
from unittest.mock import MagicMock, patch

from wks.api.db.cmd_query import cmd_query
from wks.api.db.DbCollection import DbCollection

pytestmark = pytest.mark.db


class TestCmdQuery:
    """Test cmd_query function."""

    def test_cmd_query_success(self, monkeypatch):
        """Test cmd_query with valid query."""
        mock_result = {"results": [{"_id": "1", "path": "/test"}], "count": 1}
        
        with patch.object(DbCollection, 'query', return_value=mock_result) as mock_query:
            result = cmd_query(collection="monitor", query_filter='{"status": "active"}', limit=10)
            
            assert result.success is True
            assert result.announce == "Querying monitor collection..."
            assert "Found 1 document(s)" in result.result
            assert result.output == mock_result
            mock_query.assert_called_once_with("monitor", {"status": "active"}, 10)

    def test_cmd_query_no_filter(self, monkeypatch):
        """Test cmd_query with no filter."""
        mock_result = {"results": [], "count": 0}
        
        with patch.object(DbCollection, 'query', return_value=mock_result) as mock_query:
            result = cmd_query(collection="monitor", query_filter=None, limit=50)
            
            assert result.success is True
            assert result.output == mock_result
            mock_query.assert_called_once_with("monitor", None, 50)

    def test_cmd_query_invalid_json(self, monkeypatch):
        """Test cmd_query with invalid JSON."""
        # The JSON parsing happens in cmd_query, and it catches JSONDecodeError
        result = cmd_query(collection="monitor", query_filter='{"invalid": json}', limit=50)
        
        assert result.success is False
        assert "Invalid JSON" in result.result
        assert "error" in result.output

    def test_cmd_query_empty_string_filter(self, monkeypatch):
        """Test cmd_query with empty string filter."""
        mock_result = {"results": [], "count": 0}
        
        with patch.object(DbCollection, 'query', return_value=mock_result) as mock_query:
            result = cmd_query(collection="monitor", query_filter="", limit=50)
            
            assert result.success is True
            mock_query.assert_called_once_with("monitor", None, 50)

    def test_cmd_query_query_fails(self, monkeypatch):
        """Test cmd_query when query raises exception."""
        with patch.object(DbCollection, 'query', side_effect=Exception("Connection failed")) as mock_query:
            result = cmd_query(collection="monitor", query_filter='{"status": "active"}', limit=50)
            
            assert result.success is False
            assert "Query failed" in result.result
            assert "error" in result.output
            assert "Connection failed" in result.output["error"]

    def test_cmd_query_complex_filter(self, monkeypatch):
        """Test cmd_query with complex filter."""
        mock_result = {"results": [{"_id": "1"}], "count": 1}
        complex_filter = '{"age": {"$gt": 18}, "name": {"$regex": "^A"}}'
        
        with patch.object(DbCollection, 'query', return_value=mock_result) as mock_query:
            result = cmd_query(collection="users", query_filter=complex_filter, limit=100)
            
            assert result.success is True
            parsed_filter = json.loads(complex_filter)
            mock_query.assert_called_once_with("users", parsed_filter, 100)

