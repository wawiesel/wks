"""Unit tests for wks.api.monitor._enforce_monitor_db_limit module."""

from wks.api.database.Database import Database
from wks.api.database.DatabaseConfig import DatabaseConfig
from wks.api.monitor._enforce_monitor_db_limit import _enforce_monitor_db_limit


def test_enforce_limit_no_limit(minimal_config_dict):
    """Test that max_docs <= 0 returns immediately."""
    db_cfg = DatabaseConfig.model_validate(minimal_config_dict["database"])
    with Database(db_cfg, "test") as db:
        _enforce_monitor_db_limit(db, max_docs=0, min_priority=0.0)


def test_enforce_limit_min_priority(minimal_config_dict):
    """Test removing entries below min_priority."""
    db_cfg = DatabaseConfig.model_validate(minimal_config_dict["database"])
    with Database(db_cfg, "test") as db:
        db.insert_one({"path": "low", "priority": 0.5})
        db.insert_one({"path": "high", "priority": 1.5})

        _enforce_monitor_db_limit(db, max_docs=100, min_priority=1.0)

        assert db.count_documents({}) == 1
        assert db.find_one({"path": "high"}) is not None


def test_enforce_limit_max_docs(minimal_config_dict):
    """Test enforcing max_docs by removing lowest priority entries."""
    db_cfg = DatabaseConfig.model_validate(minimal_config_dict["database"])
    with Database(db_cfg, "test") as db:
        db.insert_one({"path": "p1", "priority": 1.0})
        db.insert_one({"path": "p2", "priority": 2.0})
        db.insert_one({"path": "p3", "priority": 3.0})

        # Limit to 2 docs
        _enforce_monitor_db_limit(db, max_docs=2, min_priority=0.0)

        assert db.count_documents({}) == 2
        # p1 should be gone as it has lowest priority
        assert db.find_one({"path": "p1"}) is None
        assert db.find_one({"path": "p2"}) is not None
        assert db.find_one({"path": "p3"}) is not None


def test_enforce_limit_exception_handling():
    """Test exception handling and warning reporting."""

    class BrokenDatabase:
        def delete_many(self, query):
            raise RuntimeError("DB Error")

        def find(self, *args, **kwargs):
            return self

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return []

    warnings: list[str] = []
    from unittest.mock import MagicMock

    db_mock = MagicMock(spec=Database)
    db_mock.delete_many.side_effect = RuntimeError("DB Error")
    db_mock.find.return_value.sort.return_value.limit.return_value = []

    _enforce_monitor_db_limit(db_mock, max_docs=10, min_priority=1.0, warnings=warnings)

    assert len(warnings) == 1
    assert "Database limit enforcement failed: DB Error" in warnings[0]
