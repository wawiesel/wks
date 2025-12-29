"""Unit tests for prune timer utilities."""

import json
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.database


def test_get_last_prune_timestamp_empty(tmp_path, monkeypatch):
    """Returns None when status file doesn't exist."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import get_last_prune_timestamp

    result = get_last_prune_timestamp("transform")
    assert result is None


def test_set_and_get_prune_timestamp(tmp_path, monkeypatch):
    """Can set and retrieve prune timestamp."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import (
        get_last_prune_timestamp,
        set_last_prune_timestamp,
    )

    # Set timestamp
    set_last_prune_timestamp("transform")

    # Get timestamp
    result = get_last_prune_timestamp("transform")
    assert result is not None
    assert isinstance(result, datetime)

    # Should be recent (within last minute)
    now = datetime.now(timezone.utc)
    assert (now - result).total_seconds() < 60


def test_set_prune_timestamp_specific_time(tmp_path, monkeypatch):
    """Can set specific timestamp."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import (
        get_last_prune_timestamp,
        set_last_prune_timestamp,
    )

    specific_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    set_last_prune_timestamp("nodes", specific_time)

    result = get_last_prune_timestamp("nodes")
    assert result is not None
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 1


def test_multiple_databases_independent(tmp_path, monkeypatch):
    """Each database has independent timer."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import (
        get_last_prune_timestamp,
        set_last_prune_timestamp,
    )

    time1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    time2 = datetime(2025, 6, 15, tzinfo=timezone.utc)

    set_last_prune_timestamp("transform", time1)
    set_last_prune_timestamp("nodes", time2)

    result1 = get_last_prune_timestamp("transform")
    result2 = get_last_prune_timestamp("nodes")

    assert result1 is not None
    assert result2 is not None
    assert result1.month == 1
    assert result2.month == 6


def test_should_prune_never_pruned(tmp_path, monkeypatch):
    """Should prune if never pruned before."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import should_prune

    result = should_prune("transform", 3600)
    assert result is True


def test_should_prune_disabled(tmp_path, monkeypatch):
    """Should not prune if frequency is 0."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import should_prune

    result = should_prune("transform", 0)
    assert result is False


def test_should_prune_after_interval(tmp_path, monkeypatch):
    """Should prune after interval has elapsed."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import (
        set_last_prune_timestamp,
        should_prune,
    )

    # Set timestamp 2 hours ago
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    set_last_prune_timestamp("transform", old_time)

    # Frequency is 1 hour - should prune
    result = should_prune("transform", 3600)
    assert result is True


def test_should_prune_before_interval(tmp_path, monkeypatch):
    """Should not prune before interval has elapsed."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import (
        set_last_prune_timestamp,
        should_prune,
    )

    # Set timestamp just now
    set_last_prune_timestamp("transform")

    # Frequency is 1 hour - should not prune
    result = should_prune("transform", 3600)
    assert result is False


def test_status_file_persists(tmp_path, monkeypatch):
    """Status file is correctly written to disk."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune_timer import set_last_prune_timestamp

    set_last_prune_timestamp("transform")
    set_last_prune_timestamp("nodes")

    status_file = tmp_path / "database.json"
    assert status_file.exists()

    data = json.loads(status_file.read_text())
    assert "prune_timestamps" in data
    assert "transform" in data["prune_timestamps"]
    assert "nodes" in data["prune_timestamps"]
