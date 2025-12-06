"""Unit tests for wks.api.db.DbCollection module."""

import builtins
from unittest.mock import MagicMock, patch

import pytest

from wks.api.db.DbCollection import DbCollection
from wks.api.db.DbConfig import DbConfig

pytestmark = pytest.mark.db


def build_db_config(type: str = "mongo", prefix: str = "wks", uri: str = "mongodb://localhost:27017/"):
    """Build a DbConfig for testing."""
    if type == "mongo":
        data = {"uri": uri}
    elif type == "mongomock":
        data = {}
    else:
        data = {}
    return DbConfig(type=type, prefix=prefix, data=data)


class TestDbCollectionInit:
    """Test DbCollection.__init__."""

    def test_init_with_collection_name(self, monkeypatch):
        """Test __init__ with simple collection name (prefix auto-prepended)."""
        db_config = build_db_config(prefix="wks")

        collection = DbCollection(db_config, "monitor")
        assert collection.db_config == db_config
        assert collection.db_name == "wks"
        assert collection.coll_name == "monitor"
        assert collection._impl is None

    def test_init_with_dotted_name(self, monkeypatch):
        """Test __init__ with dotted name (backwards compatibility)."""
        db_config = build_db_config(prefix="wks")

        collection = DbCollection(db_config, "custom.monitor")
        assert collection.db_name == "custom"
        assert collection.coll_name == "monitor"

    def test_init_with_custom_prefix(self, monkeypatch):
        """Test __init__ with custom prefix."""
        db_config = build_db_config(prefix="custom")

        collection = DbCollection(db_config, "monitor")
        assert collection.db_name == "custom"
        assert collection.coll_name == "monitor"


class TestDbCollectionContextManager:
    """Test DbCollection context manager (__enter__ / __exit__)."""

    def test_enter_with_mongo_backend(self, monkeypatch):
        """Test __enter__ with mongo backend."""
        db_config = build_db_config(type="mongo")

        collection = DbCollection(db_config, "monitor")

        # Mock the _Impl class
        mock_impl = MagicMock()
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            mock_import.return_value = mock_module

            result = collection.__enter__()
            assert result == collection
            assert collection._impl == mock_impl
            mock_impl.__enter__.assert_called_once()

    def test_enter_with_mongomock_backend(self, monkeypatch):
        """Test __enter__ with mongomock backend."""
        db_config = build_db_config(type="mongomock")

        collection = DbCollection(db_config, "monitor")

        # Mock the _Impl class
        mock_impl = MagicMock()
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            mock_import.return_value = mock_module

            result = collection.__enter__()
            assert result == collection
            assert collection._impl == mock_impl

    def test_enter_with_unsupported_backend(self, monkeypatch):
        """Test __enter__ raises ValueError for unsupported backend."""
        # Create a DbConfig with invalid type by directly constructing it
        from wks.api.db._mongo._DbConfigData import _DbConfigData

        db_config = DbConfig(type="invalid", data=_DbConfigData(uri="mongodb://localhost:27017/"))

        collection = DbCollection(db_config, "monitor")

        with pytest.raises(ValueError, match="Unsupported backend type"):
            collection.__enter__()

    def test_exit_calls_impl_exit(self, monkeypatch):
        """Test __exit__ calls _impl.__exit__ if _impl exists."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.__exit__ = MagicMock(return_value=False)
        collection._impl = mock_impl

        result = collection.__exit__(None, None, None)
        mock_impl.__exit__.assert_called_once_with(None, None, None)
        assert result is False

    def test_exit_without_impl(self, monkeypatch):
        """Test __exit__ returns False if _impl is None."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        collection._impl = None

        result = collection.__exit__(None, None, None)
        assert result is False


class TestDbCollectionMethods:
    """Test DbCollection methods (count_documents, find_one, etc.)."""

    def test_count_documents(self, monkeypatch):
        """Test count_documents delegates to _impl."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.count_documents = MagicMock(return_value=42)
        collection._impl = mock_impl

        result = collection.count_documents({"status": "active"})
        assert result == 42
        mock_impl.count_documents.assert_called_once_with({"status": "active"})

    def test_count_documents_no_filter(self, monkeypatch):
        """Test count_documents with None filter."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.count_documents = MagicMock(return_value=10)
        collection._impl = mock_impl

        result = collection.count_documents(None)
        assert result == 10
        mock_impl.count_documents.assert_called_once_with(None)

    def test_find_one(self, monkeypatch):
        """Test find_one delegates to _impl."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_doc = {"_id": "123", "path": "/test"}
        mock_impl.find_one = MagicMock(return_value=mock_doc)
        collection._impl = mock_impl

        result = collection.find_one({"path": "/test"}, {"_id": 1})
        assert result == mock_doc
        mock_impl.find_one.assert_called_once_with({"path": "/test"}, {"_id": 1})

    def test_find_one_no_projection(self, monkeypatch):
        """Test find_one with None projection."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.find_one = MagicMock(return_value=None)
        collection._impl = mock_impl

        result = collection.find_one({"path": "/test"}, None)
        assert result is None
        mock_impl.find_one.assert_called_once_with({"path": "/test"}, None)

    def test_update_one(self, monkeypatch):
        """Test update_one delegates to _impl."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.update_one = MagicMock()
        collection._impl = mock_impl

        collection.update_one({"path": "/test"}, {"$set": {"status": "active"}}, upsert=True)
        mock_impl.update_one.assert_called_once_with({"path": "/test"}, {"$set": {"status": "active"}}, True)

    def test_update_one_no_upsert(self, monkeypatch):
        """Test update_one with upsert=False."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.update_one = MagicMock()
        collection._impl = mock_impl

        collection.update_one({"path": "/test"}, {"$set": {"status": "active"}}, upsert=False)
        mock_impl.update_one.assert_called_once_with({"path": "/test"}, {"$set": {"status": "active"}}, False)

    def test_delete_many(self, monkeypatch):
        """Test delete_many delegates to _impl."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_impl.delete_many = MagicMock(return_value=5)
        collection._impl = mock_impl

        result = collection.delete_many({"status": "inactive"})
        assert result == 5
        mock_impl.delete_many.assert_called_once_with({"status": "inactive"})

    def test_find(self, monkeypatch):
        """Test find delegates to _impl."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_impl.find = MagicMock(return_value=mock_cursor)
        collection._impl = mock_impl

        result = collection.find({"status": "active"}, {"_id": 0})
        assert result == mock_cursor
        mock_impl.find.assert_called_once_with({"status": "active"}, {"_id": 0})

    def test_find_no_filter(self, monkeypatch):
        """Test find with None filter."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_impl.find = MagicMock(return_value=mock_cursor)
        collection._impl = mock_impl

        result = collection.find(None, None)
        assert result == mock_cursor
        mock_impl.find.assert_called_once_with(None, None)


class TestDbCollectionQuery:
    """Test DbCollection.query classmethod."""

    def test_query_with_filter(self, monkeypatch):
        """Test query with filter and limit."""
        db_config = build_db_config()
        assert isinstance(db_config.type, str)

        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=[{"_id": "1"}, {"_id": "2"}])
        mock_impl.find = MagicMock(return_value=mock_cursor)
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        original_import = builtins.__import__
        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            # Make __import__ return mock_module for any wks.api.db._* imports

            def import_side_effect(name, *args, **kwargs):
                if isinstance(name, str) and "wks.api.db._" in name and "_Impl" in name:
                    return mock_module
                # For other imports (including DbConfig), use original import
                return original_import(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = DbCollection.query(db_config, "monitor", {"status": "active"}, limit=10)
            assert result["count"] == 2
            assert len(result["results"]) == 2
            assert result["results"] == [{"_id": "1"}, {"_id": "2"}]

    def test_query_no_filter(self, monkeypatch):
        """Test query with None filter."""
        db_config = build_db_config()
        assert isinstance(db_config.type, str)

        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=[])
        mock_impl.find = MagicMock(return_value=mock_cursor)
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        original_import = builtins.__import__
        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            # Make __import__ return mock_module for any wks.api.db._* imports

            def import_side_effect(name, *args, **kwargs):
                if isinstance(name, str) and "wks.api.db._" in name and "_Impl" in name:
                    return mock_module
                # For other imports (including DbConfig), use original import
                return original_import(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = DbCollection.query(db_config, "monitor", None, limit=50)
            assert result["count"] == 0
            assert result["results"] == []

    def test_query_with_projection(self, monkeypatch):
        """Test query with custom projection."""
        db_config = build_db_config()
        # Ensure db_config.type is a string, not a mock
        assert isinstance(db_config.type, str)

        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=[{"name": "test"}])
        mock_impl.find = MagicMock(return_value=mock_cursor)
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        original_import = builtins.__import__
        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            # Make __import__ return the module when called with the expected arguments

            def import_side_effect(name, *args, **kwargs):
                if isinstance(name, str) and "wks.api.db._" in name and "_Impl" in name:
                    return mock_module
                return original_import(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = DbCollection.query(db_config, "monitor", {}, limit=50, projection={"name": 1})
            assert result["count"] == 1
            mock_impl.find.assert_called_once_with({}, {"name": 1})

    def test_query_default_projection(self, monkeypatch):
        """Test query uses default projection when None provided."""
        db_config = build_db_config()
        assert isinstance(db_config.type, str)

        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=[])
        mock_impl.find = MagicMock(return_value=mock_cursor)
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        original_import = builtins.__import__
        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            # Make __import__ return mock_module for any wks.api.db._* imports

            def import_side_effect(name, *args, **kwargs):
                if isinstance(name, str) and "wks.api.db._" in name and "_Impl" in name:
                    return mock_module
                # For other imports (including DbConfig), use original import
                return original_import(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = DbCollection.query(db_config, "monitor", {}, limit=50, projection=None)
            assert result["count"] == 0
            assert result["results"] == []
            mock_impl.find.assert_called_once_with({}, {"_id": 0})

    def test_query_with_dotted_name(self, monkeypatch):
        """Test query with dotted collection name (backwards compatibility)."""
        db_config = build_db_config(prefix="wks")
        assert isinstance(db_config.type, str)

        mock_impl = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.limit = MagicMock(return_value=[])
        mock_impl.find = MagicMock(return_value=mock_cursor)
        mock_impl.__enter__ = MagicMock(return_value=mock_impl)

        original_import = builtins.__import__
        with patch("builtins.__import__") as mock_import:
            mock_module = MagicMock()
            mock_module._Impl = MagicMock(return_value=mock_impl)
            # Make __import__ return mock_module for any wks.api.db._* imports

            def import_side_effect(name, *args, **kwargs):
                if isinstance(name, str) and "wks.api.db._" in name and "_Impl" in name:
                    return mock_module
                # For other imports (including DbConfig), use original import
                return original_import(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            result = DbCollection.query(db_config, "custom.monitor", {}, limit=50)
            assert result["count"] == 0


class TestDbCollectionHelpers:
    """Test DbCollection helper methods (get_client, get_database)."""

    def test_get_client(self, monkeypatch):
        """Test get_client returns _impl._client."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_client = MagicMock()
        mock_impl = MagicMock()
        mock_impl._client = mock_client
        collection._impl = mock_impl

        result = collection.get_client()
        assert result == mock_client

    def test_get_client_no_impl(self, monkeypatch):
        """Test get_client raises RuntimeError if _impl is None."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        collection._impl = None

        with pytest.raises(RuntimeError, match="Collection not initialized"):
            collection.get_client()

    def test_get_database(self, monkeypatch):
        """Test get_database returns _impl._client[database_name]."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_impl = MagicMock()
        mock_impl._client = mock_client
        collection._impl = mock_impl

        result = collection.get_database("testdb")
        assert result == mock_db
        mock_client.__getitem__.assert_called_once_with("testdb")

    def test_get_database_default(self, monkeypatch):
        """Test get_database uses collection.db_name when database_name is None."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        collection.db_name = "wks"
        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_impl = MagicMock()
        mock_impl._client = mock_client
        collection._impl = mock_impl

        result = collection.get_database(None)
        assert result == mock_db
        mock_client.__getitem__.assert_called_once_with("wks")

    def test_get_database_no_impl(self, monkeypatch):
        """Test get_database raises RuntimeError if _impl is None."""
        db_config = build_db_config()

        collection = DbCollection(db_config, "monitor")
        collection._impl = None

        with pytest.raises(RuntimeError, match="Collection not initialized"):
            collection.get_database("testdb")
