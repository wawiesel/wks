"""Unit tests for _SyncConfig validation."""

import pytest

from pydantic import ValidationError

from wks.api.monitor._SyncConfig import _SyncConfig
pytestmark = pytest.mark.monitor


def test_sync_config_database_no_dot():
    """Test _SyncConfig validation when database has no dot."""
    with pytest.raises(ValidationError) as exc:
        _SyncConfig(database="nodot", max_documents=1000, min_priority=0.0, prune_interval_secs=300.0)
    assert "must be in format 'database.collection'" in str(exc.value)


def test_sync_config_database_empty_parts():
    """Test _SyncConfig validation when database has empty parts."""
    with pytest.raises(ValidationError) as exc:
        _SyncConfig(database=".collection", max_documents=1000, min_priority=0.0, prune_interval_secs=300.0)
    assert "must be in format 'database.collection'" in str(exc.value)


def test_sync_config_database_empty_collection():
    """Test _SyncConfig validation when collection part is empty."""
    with pytest.raises(ValidationError) as exc:
        _SyncConfig(database="database.", max_documents=1000, min_priority=0.0, prune_interval_secs=300.0)
    assert "must be in format 'database.collection'" in str(exc.value)

