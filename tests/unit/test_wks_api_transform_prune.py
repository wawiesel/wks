"""Unit tests for prune module."""

from unittest.mock import MagicMock, patch

import pytest

from wks.api.transform.prune import prune


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock()
    config.database = MagicMock()
    config.transform.cache.base_dir = str(tmp_path / "cache")
    return config


@pytest.fixture
def mock_db_cls():
    with patch("wks.api.transform.prune.Database") as mock:
        yield mock


def test_prune_empty(mock_config, mock_db_cls):
    """Test prune with empty directory and database."""
    # Setup
    transform_db = mock_db_cls.return_value.__enter__.return_value
    transform_db.find.return_value = []

    # Run
    result = prune(mock_config)

    assert result["deleted_count"] == 0
    assert result["checked_count"] == 0
    assert result["warnings"] == []


def test_prune_stale_db_records(mock_config, mock_db_cls, tmp_path):
    """Test pruning DB records that point to missing files."""
    transform_db = mock_db_cls.return_value.__enter__.return_value

    # DB has record, but file does not exist
    docs = [{"_id": "1", "checksum": "c1", "cache_uri": "file:///missing"}]
    transform_db.find.return_value = docs

    # Mock delete_many
    transform_db.delete_many.return_value = 5  # count

    result = prune(mock_config)

    assert result["deleted_count"] == 5
    assert result["checked_count"] == 1
    transform_db.delete_many.assert_called_with({"_id": {"$in": ["1"]}})


def test_prune_orphaned_files(mock_config, mock_db_cls, tmp_path):
    """Test pruning files that are not in DB."""
    transform_db = mock_db_cls.return_value.__enter__.return_value
    transform_db.find.return_value = []  # DB empty

    # Create orphaned file
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "c1.md").touch()

    result = prune(mock_config)

    assert result["deleted_count"] == 1
    assert result["checked_count"] == 0
    assert not (cache_dir / "c1.md").exists()


def test_prune_valid_files(mock_config, mock_db_cls, tmp_path):
    """Test valid files are kept."""
    transform_db = mock_db_cls.return_value.__enter__.return_value
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # Create valid file
    file_path = cache_dir / "c1.md"
    file_path.touch()

    # DB has matching record
    docs = [{"_id": "1", "checksum": "c1", "cache_uri": f"file://{file_path}"}]
    transform_db.find.return_value = docs

    result = prune(mock_config)

    assert result["deleted_count"] == 0
    assert result["checked_count"] == 1
    assert file_path.exists()


def test_prune_invalid_uri_warning(mock_config, mock_db_cls):
    """Test warning on invalid URI."""
    transform_db = mock_db_cls.return_value.__enter__.return_value

    # DB has invalid URI that causes ValueError in uri_to_path (mocked logic or real)
    # The real uri_to_path raises ValueError if scheme is wrong
    docs = [{"_id": "1", "checksum": "c1", "cache_uri": "invalid://uri"}]
    transform_db.find.return_value = docs

    # Run
    with patch("wks.api.transform.prune.uri_to_path", side_effect=ValueError("Invalid scheme")):
        result = prune(mock_config)

    # Assert
    # We expect delete_many to be called with "1" because the exception block appends to stale_db_records
    transform_db.delete_many.assert_called_with({"_id": {"$in": ["1"]}})

    assert len(result["warnings"]) == 1
    assert "Error checking cache file" in result["warnings"][0]
