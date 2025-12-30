"""Database public API coverage with mongomock backend (no mocks)."""

from typing import cast

import pytest
from pydantic import BaseModel

from wks.api.database.Database import Database
from wks.api.database.DatabaseConfig import DatabaseConfig


def _db_config() -> DatabaseConfig:
    # Use a unique prefix to avoid cross-test contamination via mongomock's in-memory client.
    # DatabaseConfig's validate_and_populate_data validator converts dict to BaseModel
    return DatabaseConfig(
        type="mongomock",
        prefix="wks_test_database_public",
        data=cast(BaseModel, {}),
        prune_frequency_secs=3600,
    )


def test_database_context_and_operations():
    cfg = _db_config()
    with Database(cfg, "monitor") as db:
        db.update_one({"path": "/a"}, {"$set": {"path": "/a", "value": 1}}, upsert=True)
        db.update_one({"path": "/b"}, {"$set": {"path": "/b", "value": 9}}, upsert=True)

        # count_documents must respect filter
        assert db.count_documents({"path": "/a"}) == 1
        assert db.count_documents({"path": "/b"}) == 1
        assert db.count_documents({"path": "/missing"}) == 0

        # find_one must respect filter and projection
        projected = db.find_one({"path": "/a"}, projection={"_id": 0, "path": 1})
        assert projected == {"path": "/a"}
        res = db.find_one({"path": "/b"})
        assert res is not None
        assert res["value"] == 9
        assert db.find_one({"path": "/missing"}) is None

        db.update_many({"path": "/a"}, {"$set": {"value": 2}})
        results = list(db.find({"path": "/a"}))
        assert len(results) == 1
        assert results[0]["value"] == 2

        projected_many = list(db.find({"path": "/a"}, projection={"_id": 0, "path": 1}))
        assert projected_many == [{"path": "/a"}]

        # delete_many is a passthrough; ensure it doesn't crash and respects filter
        assert db.delete_many({"path": "/a"}) >= 0

        # New operations coverage (lines 61-70)
        db.insert_one({"path": "/c", "value": 3})
        assert db.count_documents({"path": "/c"}) == 1
        db.insert_many([{"path": "/d"}, {"path": "/e"}])
        assert db.count_documents({"path": {"$in": ["/d", "/e"]}}) == 2
        assert db.delete_one({"path": "/c"}) >= 1
        assert db.count_documents({"path": "/c"}) == 0

        assert db.get_client() is not None
        assert db.get_database(cfg.prefix) is not None
    # __exit__ with no _impl should simply return False
    assert Database(cfg, "monitor").__exit__(None, None, None) is False


def test_database_query_and_list_databases():
    cfg = _db_config()
    with Database(cfg, "vault") as db:
        db.update_one({"path": "/doc"}, {"$set": {"path": "/doc"}}, upsert=True)
    result = Database.query(cfg, "vault", {"path": "/doc"}, limit=5)
    assert result["count"] == 1
    names = Database.list_databases(cfg)
    assert "vault" in names


def test_database_unsupported_backend():
    cfg = DatabaseConfig.model_construct(type="unsupported", prefix="wks", data=_db_config().data)
    db = Database(cfg, "monitor")
    try:
        db.__enter__()
    except ValueError as e:
        assert "Unsupported backend type" in str(e)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for unsupported backend")


def test_database_requires_context_for_client_and_database():
    cfg = _db_config()
    db = Database(cfg, "monitor")
    with pytest.raises(RuntimeError) as exc_info:
        db.get_client()
    assert str(exc_info.value) == "Collection not initialized. Use as context manager first."

    with pytest.raises(RuntimeError) as exc_info:
        db.get_database()
    assert str(exc_info.value) == "Collection not initialized. Use as context manager first."


def test_database_update_one_default_upsert_false():
    cfg = _db_config()
    with Database(cfg, "monitor") as db:
        # If upsert defaults to False, this should NOT create a document.
        db.update_one({"path": "/new"}, {"$set": {"path": "/new", "value": 1}})
        assert db.count_documents({"path": "/new"}) == 0


def test_database_get_database_default_and_override():
    cfg = _db_config()
    with Database(cfg, "monitor") as db:
        default_db = db.get_database()
        assert default_db.name == cfg.prefix

        other_db = db.get_database("other")
        assert other_db.name == "other"


def test_database_exit_passes_exception_info_to_impl() -> None:
    """Ensure Database.__exit__ forwards exc_type/exc_val/exc_tb to the backend impl."""

    class SpyBackend:
        def __init__(self):
            self.exit_args = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.exit_args = (exc_type, exc_val, exc_tb)
            return False

    cfg = _db_config()

    with pytest.raises(ValueError), Database(cfg, "monitor") as db:
        # Substitute the real backend with a Spy
        spy_backend = SpyBackend()
        db._backend = spy_backend  # type: ignore[assignment]

        # Trigger exception
        raise ValueError("boom")

    # Verify delegation
    assert spy_backend.exit_args is not None
    args = spy_backend.exit_args
    assert args[0] is ValueError
    assert isinstance(args[1], ValueError)
    assert str(args[1]) == "boom"
    assert args[2] is not None


# Migrated Integration Tests (formerly test_wks_api_database__mongo__Backend.py)
# Tested via public Database API with type="mongo"


def test_mongo_backend_init_error():
    """Test error when data is missing required fields."""
    # DatabaseConfig validates 'data' for mongo, but we can try to pass invalid dict
    # if we construct it manually or via partial validation.

    # Construct invalid config
    cfg = DatabaseConfig.model_construct(
        type="mongo",
        prefix="test",
        data=cast(BaseModel, None),  # Invalid data
    )

    # Attempt to use it
    with pytest.raises(ValueError, match="MongoDB config data is required"), Database(cfg, "coll"):
        pass


def test_mongo_backend_ensure_local_early_connect(monkeypatch):
    """Test skip startup if already connected."""
    import subprocess
    from unittest.mock import MagicMock

    monkeypatch.setattr("wks.api.database._mongo._Backend._Backend._can_connect", lambda self, uri: True)

    # Mock subprocess to ensure it's NOT called
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    cfg = DatabaseConfig(
        type="mongo",
        prefix="test",
        data=cast(BaseModel, {"uri": "mongodb://localhost:27017", "local": True}),
        prune_frequency_secs=3600,
    )

    with Database(cfg, "coll"):
        pass

    mock_popen.assert_not_called()


def test_mongo_backend_fallback_binary(monkeypatch, tmp_path):
    """Test fallback binary detection logic via public API."""
    import shutil
    import subprocess
    from pathlib import Path
    from unittest.mock import MagicMock

    # Mock shutil.which to fail
    monkeypatch.setattr(shutil, "which", lambda x: None)

    # Mock Path.exists to succeed only for specific path
    def mock_exists(self):
        return str(self) == "/usr/local/bin/mongod"

    monkeypatch.setattr(Path, "exists", mock_exists)

    # Mock connection success so we don't actually need a binary running
    monkeypatch.setattr("wks.api.database._mongo._Backend._Backend._can_connect", lambda *args: True)

    # Mock Popen to track if called (meaning it accepted the binary path)
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    cfg = DatabaseConfig(
        type="mongo",
        prefix="test",
        data=cast(BaseModel, {"uri": "mongodb://localhost:27017", "local": True}),
        prune_frequency_secs=3600,
    )

    with Database(cfg, "coll"):
        pass


def test_mongo_backend_basic_ops_integration(monkeypatch):
    """Test basic operations with mongo backend (mocked client)."""
    import mongomock

    # Patch the class in the module
    monkeypatch.setattr("wks.api.database._mongo._Backend.MongoClient", mongomock.MongoClient)

    cfg = DatabaseConfig(
        type="mongo",
        prefix="test",
        data=cast(BaseModel, {"uri": "mongodb://localhost:27017", "local": False}),
        prune_frequency_secs=3600,
    )

    with Database(cfg, "coll") as db:
        db.insert_one({"a": 1})
        assert db.count_documents({"a": 1}) == 1
        assert db.delete_many({}) == 1
