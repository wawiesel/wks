"""Unit tests for should_prune."""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.database


def test_should_prune_never_pruned(tmp_path, monkeypatch):
    """Should prune if never pruned before."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.should_prune import should_prune

    result = should_prune("transform", 3600)
    assert result is True


def test_should_prune_disabled(tmp_path, monkeypatch):
    """Should not prune if frequency is 0."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.should_prune import should_prune

    result = should_prune("transform", 0)
    assert result is False


def test_should_prune_after_interval(tmp_path, monkeypatch):
    """Should prune after interval has elapsed."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp
    from wks.api.database.prune.should_prune import should_prune

    # Set timestamp 2 hours ago
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    set_last_prune_timestamp("transform", old_time)

    # Frequency is 1 hour - should prune
    result = should_prune("transform", 3600)
    assert result is True


def test_should_prune_before_interval(tmp_path, monkeypatch):
    """Should not prune before interval has elapsed."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp
    from wks.api.database.prune.should_prune import should_prune

    # Set timestamp just now
    set_last_prune_timestamp("transform")

    # Frequency is 1 hour - should not prune
    result = should_prune("transform", 3600)
    assert result is False
