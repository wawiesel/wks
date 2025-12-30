"""Unit tests for wks.api.database prune timestamp utilities."""

from datetime import datetime, timezone

from wks.api.database._get_last_prune_timestamp import get_last_prune_timestamp
from wks.api.database._get_status_path import _get_status_path
from wks.api.database._set_last_prune_timestamp import set_last_prune_timestamp
from wks.api.database._should_prune import should_prune


def test_get_status_path(monkeypatch, tmp_path):
    """Test status path generation."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    result = _get_status_path()
    assert result == wks_home / "database.json"


def test_set_and_get_prune_timestamp(monkeypatch, tmp_path):
    """Test setting and getting prune timestamp."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Initially no timestamp
    assert get_last_prune_timestamp("transform") is None

    # Set timestamp
    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    set_last_prune_timestamp("transform", ts)

    # Get it back
    result = get_last_prune_timestamp("transform")
    assert result is not None
    assert result.year == 2025


def test_set_prune_timestamp_default_now(monkeypatch, tmp_path):
    """Test that set_last_prune_timestamp defaults to now."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    set_last_prune_timestamp("nodes")

    result = get_last_prune_timestamp("nodes")
    assert result is not None
    # Should be very recent
    now = datetime.now(timezone.utc)
    assert (now - result).total_seconds() < 10


def test_should_prune_disabled(monkeypatch, tmp_path):
    """Test should_prune returns False when disabled."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # 0 = disabled
    result = should_prune("transform", 0)
    assert result is False


def test_should_prune_never_pruned(monkeypatch, tmp_path):
    """Test should_prune returns True when never pruned."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    result = should_prune("transform", 3600)  # 1 hour frequency
    assert result is True


def test_should_prune_recently_pruned(monkeypatch, tmp_path):
    """Test should_prune returns False when recently pruned."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Set timestamp to now
    set_last_prune_timestamp("transform")

    # Check with 1 hour frequency - should not prune
    result = should_prune("transform", 3600)
    assert result is False


def test_get_last_prune_timestamp_handles_invalid_json(monkeypatch, tmp_path):
    """Test handling of invalid JSON in status file."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Write invalid JSON
    (wks_home / "database.json").write_text("not valid json", encoding="utf-8")

    result = get_last_prune_timestamp("transform")
    assert result is None
