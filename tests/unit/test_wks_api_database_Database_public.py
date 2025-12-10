"""Database public API coverage with mongomock backend (no mocks)."""

import pytest

from wks.api.database.Database import Database
from wks.api.database.DatabaseConfig import DatabaseConfig


def _db_config() -> DatabaseConfig:
    return DatabaseConfig(type="mongomock", prefix="wks", data={})


def test_database_context_and_operations():
    cfg = _db_config()
    with Database(cfg, "monitor") as db:
        db.update_one({"path": "/a"}, {"$set": {"path": "/a", "value": 1}}, upsert=True)
        assert db.count_documents({"path": "/a"}) == 1
        assert db.find_one({"path": "/a"})["value"] == 1
        db.update_many({"path": "/a"}, {"$set": {"value": 2}})
        results = list(db.find({"path": "/a"}))
        assert results[0]["value"] == 2
        assert db.delete_many({"path": "/a"}) >= 0
        assert db.get_client() is not None
        assert db.get_database("wks") is not None
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
    with pytest.raises(RuntimeError):
        db.get_client()
    with pytest.raises(RuntimeError):
        db.get_database()
