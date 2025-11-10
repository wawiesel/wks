"""Tests for MongoDB retry logic."""

import pytest
import pymongo.errors

from wks.mongo_retry import mongo_retry, MongoRetryWrapper


def test_mongo_retry_success_first_attempt():
    """Test that successful operation doesn't retry."""
    call_count = 0

    @mongo_retry(max_attempts=3, delay_secs=0.01)
    def operation():
        nonlocal call_count
        call_count += 1
        return "success"

    result = operation()
    assert result == "success"
    assert call_count == 1


def test_mongo_retry_success_after_failures():
    """Test that operation succeeds after transient failures."""
    call_count = 0

    @mongo_retry(max_attempts=3, delay_secs=0.01)
    def operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise pymongo.errors.ConnectionFailure("Transient failure")
        return "success"

    result = operation()
    assert result == "success"
    assert call_count == 3


def test_mongo_retry_max_attempts_exceeded():
    """Test that operation raises after max attempts."""
    call_count = 0

    @mongo_retry(max_attempts=3, delay_secs=0.01)
    def operation():
        nonlocal call_count
        call_count += 1
        raise pymongo.errors.ConnectionFailure("Persistent failure")

    with pytest.raises(pymongo.errors.ConnectionFailure):
        operation()

    assert call_count == 3


def test_mongo_retry_non_retryable_exception():
    """Test that non-retryable exceptions are raised immediately."""
    call_count = 0

    @mongo_retry(max_attempts=3, delay_secs=0.01)
    def operation():
        nonlocal call_count
        call_count += 1
        raise ValueError("Not a MongoDB error")

    with pytest.raises(ValueError):
        operation()

    assert call_count == 1


def test_mongo_retry_wrapper_read_operation():
    """Test that MongoRetryWrapper retries read operations."""

    class MockCollection:
        def __init__(self):
            self.find_one_calls = 0
            self.name = "test_collection"

        def find_one(self, query):
            self.find_one_calls += 1
            if self.find_one_calls < 2:
                raise pymongo.errors.ConnectionFailure("Transient")
            return {"_id": "123", "data": "value"}

    mock_coll = MockCollection()
    wrapped = MongoRetryWrapper(mock_coll, max_attempts=3, delay_secs=0.01)

    result = wrapped.find_one({"_id": "123"})
    assert result == {"_id": "123", "data": "value"}
    assert mock_coll.find_one_calls == 2


def test_mongo_retry_wrapper_write_operation():
    """Test that MongoRetryWrapper does NOT retry write operations."""

    class MockCollection:
        def __init__(self):
            self.insert_one_calls = 0
            self.name = "test_collection"

        def insert_one(self, document):
            self.insert_one_calls += 1
            raise pymongo.errors.ConnectionFailure("Failure")

    mock_coll = MockCollection()
    wrapped = MongoRetryWrapper(mock_coll, max_attempts=3, delay_secs=0.01)

    # Write operations should NOT be retried
    with pytest.raises(pymongo.errors.ConnectionFailure):
        wrapped.insert_one({"data": "value"})

    # Should only be called once (no retry)
    assert mock_coll.insert_one_calls == 1


def test_mongo_retry_backoff():
    """Test that retry delay increases with backoff multiplier."""
    import time

    call_times = []

    @mongo_retry(max_attempts=3, delay_secs=0.1, backoff_multiplier=2.0)
    def operation():
        call_times.append(time.time())
        raise pymongo.errors.ConnectionFailure("Failure")

    with pytest.raises(pymongo.errors.ConnectionFailure):
        operation()

    # Verify exponential backoff
    assert len(call_times) == 3

    # First retry after ~0.1s
    delay1 = call_times[1] - call_times[0]
    assert 0.08 < delay1 < 0.15

    # Second retry after ~0.2s (2.0 * 0.1)
    delay2 = call_times[2] - call_times[1]
    assert 0.18 < delay2 < 0.25
