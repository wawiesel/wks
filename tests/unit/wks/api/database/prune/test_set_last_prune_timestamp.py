"""Unit tests for set_last_prune_timestamp."""

import json
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.database


def test_set_prune_timestamp_default_now(tmp_path, monkeypatch):
    """Sets timestamp to now by default."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.get_last_prune_timestamp import get_last_prune_timestamp
    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp

    set_last_prune_timestamp("transform")
    result = get_last_prune_timestamp("transform")

    assert result is not None
    # Should be recent
    now = datetime.now(timezone.utc)
    assert (now - result).total_seconds() < 60


def test_set_prune_timestamp_specific_time(tmp_path, monkeypatch):
    """Can set specific timestamp."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.get_last_prune_timestamp import get_last_prune_timestamp
    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp

    specific_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    set_last_prune_timestamp("nodes", specific_time)

    result = get_last_prune_timestamp("nodes")
    assert result is not None
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 1


def test_status_file_persists(tmp_path, monkeypatch):
    """Status file is correctly written to disk."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    from wks.api.database.prune.set_last_prune_timestamp import set_last_prune_timestamp

    set_last_prune_timestamp("transform")
    set_last_prune_timestamp("nodes")

    status_file = tmp_path / "database.json"
    assert status_file.exists()

    data = json.loads(status_file.read_text())
    assert "prune_timestamps" in data
    assert "transform" in data["prune_timestamps"]
    assert "nodes" in data["prune_timestamps"]
