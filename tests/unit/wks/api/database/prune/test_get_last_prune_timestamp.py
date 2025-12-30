"""Unit tests for get_last_prune_timestamp."""

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.database


def test_get_last_prune_timestamp_empty(tmp_path, monkeypatch):
    """Returns None when status file doesn't exist."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.get_last_prune_timestamp import get_last_prune_timestamp

    result = get_last_prune_timestamp("transform")
    assert result is None


def test_get_prune_timestamp_exists(tmp_path, monkeypatch):
    """Can retrieve existing timestamp."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.get_last_prune_timestamp import get_last_prune_timestamp
    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp

    set_last_prune_timestamp("transform")
    result = get_last_prune_timestamp("transform")

    assert result is not None
    assert isinstance(result, datetime)

    # Should be recent
    now = datetime.now(timezone.utc)
    assert (now - result).total_seconds() < 60


def test_multiple_databases_independent(tmp_path, monkeypatch):
    """Each database has independent timestamp."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.get_last_prune_timestamp import get_last_prune_timestamp
    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp

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
