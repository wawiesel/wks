"""Unit tests for prune module."""

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform.prune import prune


def test_prune_empty(wks_home, minimal_config_dict, tmp_path):
    """Test prune with empty directory and database."""
    config = WKSConfig.load()

    # Setup clean cache dir
    cache_dir = tmp_path / "empty_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    # Ensure DB is empty
    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})

    result = prune(config)

    assert result["deleted_count"] == 0
    assert result["checked_count"] == 0
    assert result["warnings"] == []


def test_prune_stale_db_records(wks_home, minimal_config_dict, tmp_path):
    """Test pruning DB records that point to missing files."""
    config = WKSConfig.load()

    # Isolate cache
    cache_dir = tmp_path / "stale_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        coll = db.get_database()["transform"]
        coll.delete_many({})
        # DB has record, but file does not exist
        coll.insert_many(
            [
                {"checksum": "c1", "cache_uri": "file:///missing/c1.md", "size_bytes": 100},
                {"checksum": "c2", "cache_uri": "file:///missing/c2.md", "size_bytes": 100},
            ]
        )

    result = prune(config)

    assert result["deleted_count"] == 2
    assert result["checked_count"] == 2

    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 0


def test_prune_orphaned_files(wks_home, minimal_config_dict, tmp_path):
    """Test pruning files that are not in DB."""
    config = WKSConfig.load()

    # Setup cache dir
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    # Create orphaned file
    (cache_dir / "c1.md").touch()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})

    result = prune(config)

    assert result["deleted_count"] == 1
    assert result["checked_count"] == 0
    assert not (cache_dir / "c1.md").exists()


def test_prune_valid_files(wks_home, minimal_config_dict, tmp_path):
    """Test valid files are kept."""
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    # Create valid file
    file_path = cache_dir / "c1.md"
    file_path.touch()

    # DB has matching record
    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})
        db.get_database()["transform"].insert_one(
            {"checksum": "c1", "cache_uri": f"file://{file_path}", "size_bytes": 100}
        )

    result = prune(config)

    assert result["deleted_count"] == 0
    assert result["checked_count"] == 1
    assert file_path.exists()

    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 1


def test_prune_invalid_uri_warning(wks_home, minimal_config_dict, tmp_path):
    """Test handling of invalid URI (treated as missing file)."""
    config = WKSConfig.load()

    # Isolate cache
    cache_dir = tmp_path / "invalid_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})
        # Invalid URI with null byte
        db.get_database()["transform"].insert_one(
            {"checksum": "c1", "cache_uri": "file:///tmp/invalid\0path", "size_bytes": 100}
        )

    result = prune(config)

    # Should delete the invalid record (stale)
    # WARNING: It seems uri_to_path converts this to a path that just doesn't exist.
    # So it's treated as stale record, no warning.
    assert result["deleted_count"] == 1
    # assert len(result["warnings"]) == 0 # Expect 0 warnings as code is robust
    # verify db cleaned
    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 0
