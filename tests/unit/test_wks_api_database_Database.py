from typing import cast

import pytest
from pydantic import BaseModel

from wks.api.database.Database import Database
from wks.api.database.DatabaseConfig import DatabaseConfig


def _db_config() -> DatabaseConfig:
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

        assert db.count_documents({"path": "/a"}) == 1
        assert db.count_documents({"path": "/b"}) == 1
        assert db.count_documents({"path": "/missing"}) == 0

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

        assert db.delete_many({"path": "/a"}) >= 0

        db.insert_one({"path": "/c", "value": 3})
        assert db.count_documents({"path": "/c"}) == 1
        db.insert_many([{"path": "/d"}, {"path": "/e"}])
        assert db.count_documents({"path": {"$in": ["/d", "/e"]}}) == 2
        assert db.delete_one({"path": "/c"}) >= 1
        assert db.count_documents({"path": "/c"}) == 0

        assert db.get_client() is not None
        assert db.get_database(cfg.prefix) is not None
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
        spy_backend = SpyBackend()
        db._backend = spy_backend  # type: ignore[assignment]

        raise ValueError("boom")

    assert spy_backend.exit_args is not None
    args = spy_backend.exit_args
    assert args[0] is ValueError
    assert isinstance(args[1], ValueError)
    assert str(args[1]) == "boom"
    assert args[2] is not None


def test_mongo_backend_init_error():
    cfg = DatabaseConfig.model_construct(
        type="mongo",
        prefix="test",
        data=cast(BaseModel, None),  # Invalid data
    )

    with pytest.raises(ValueError, match="MongoDB config data is required"), Database(cfg, "coll"):
        pass


def test_mongo_backend_ensure_local_early_connect(mongo_wks_env, monkeypatch):
    import subprocess
    from unittest.mock import MagicMock

    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    config = mongo_wks_env["config"]

    with Database(config.database, "coll"):
        pass

    mock_popen.assert_not_called()


def test_mongo_backend_basic_ops_integration(mongo_wks_env):
    config = mongo_wks_env["config"]

    with Database(config.database, "coll") as db:
        db.delete_many({})  # Ensure clean state
        db.insert_one({"a": 1})
        assert db.count_documents({"a": 1}) == 1
        assert db.delete_many({}) == 1
