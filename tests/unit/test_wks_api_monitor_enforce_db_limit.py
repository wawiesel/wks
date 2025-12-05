"""Unit tests for _enforce_monitor_db_limit function."""

import pytest
from types import SimpleNamespace

from wks.api.monitor._enforce_monitor_db_limit import _enforce_monitor_db_limit
pytestmark = pytest.mark.monitor


def test_enforce_monitor_db_limit_min_priority():
    """Test _enforce_monitor_db_limit removes entries below min_priority (hits line 9)."""
    calls = []

    class MockCollection:
        def delete_many(self, query):
            calls.append(("delete_many", query))
            return SimpleNamespace(deleted_count=5)

        def count_documents(self, query):
            return 0

    collection = MockCollection()
    _enforce_monitor_db_limit(collection, max_docs=1000, min_priority=0.5)

    # Should call delete_many with min_priority filter
    assert len(calls) == 1
    assert calls[0][0] == "delete_many"
    assert calls[0][1] == {"priority": {"$lt": 0.5}}


def test_enforce_monitor_db_limit_max_docs_zero():
    """Test _enforce_monitor_db_limit when max_docs <= 0 (hits line 13)."""
    calls = []

    class MockCollection:
        def delete_many(self, query):
            calls.append(("delete_many", query))
            return SimpleNamespace(deleted_count=0)

        def count_documents(self, query):
            return 0

    collection = MockCollection()
    _enforce_monitor_db_limit(collection, max_docs=0, min_priority=0.0)

    # Should only call delete_many for min_priority (if > 0), not for max_docs
    # Since min_priority is 0.0, no delete_many should be called
    assert len(calls) == 0


def test_enforce_monitor_db_limit_enforces_max_docs():
    """Test _enforce_monitor_db_limit enforces max_docs limit (hits lines 19-29)."""
    calls = []
    find_results = [
        {"_id": "id1", "priority": 0.1},
        {"_id": "id2", "priority": 0.2},
        {"_id": "id3", "priority": 0.3},
    ]

    class MockCursor:
        def __init__(self, results):
            self.results = results

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def __iter__(self):
            return iter(self.results)

    class MockCollection:
        def delete_many(self, query):
            calls.append(("delete_many", query))
            return SimpleNamespace(deleted_count=0)

        def count_documents(self, query):
            return 105  # Over max_docs of 100

        def find(self, *args, **kwargs):
            return MockCursor(find_results)

    collection = MockCollection()
    _enforce_monitor_db_limit(collection, max_docs=100, min_priority=0.0)

    # Should call delete_many for max_docs (min_priority is 0.0, so skipped)
    assert len(calls) >= 1
    # Should delete the lowest priority docs
    delete_call = [c for c in calls if "$in" in str(c[1])]
    assert len(delete_call) == 1


def test_enforce_monitor_db_limit_exception_handling():
    """Test _enforce_monitor_db_limit handles exceptions gracefully."""
    class MockCollection:
        def delete_many(self, query):
            raise Exception("Database error")

        def count_documents(self, query):
            raise Exception("Database error")

    collection = MockCollection()
    # Should not raise exception
    _enforce_monitor_db_limit(collection, max_docs=100, min_priority=0.5)


def test_enforce_monitor_db_limit_no_extras():
    """Test _enforce_monitor_db_limit when extras <= 0 (hits line 20-21)."""
    calls = []

    class MockCollection:
        def delete_many(self, query):
            calls.append(("delete_many", query))
            return SimpleNamespace(deleted_count=0)

        def count_documents(self, query):
            return 100  # Exactly max_docs

    collection = MockCollection()
    _enforce_monitor_db_limit(collection, max_docs=100, min_priority=0.0)

    # Should not delete for max_docs (extras = 0)
    delete_calls = [c for c in calls if "$in" in str(c[1])]
    assert len(delete_calls) == 0

