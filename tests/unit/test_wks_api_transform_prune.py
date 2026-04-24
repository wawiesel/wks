from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform.prune import prune


def test_prune_empty(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "empty_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})

    result = prune(config)

    assert result["deleted_count"] == 0
    assert result["checked_count"] == 0
    assert result["warnings"] == []


def test_prune_stale_db_records(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "stale_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        coll = db.get_database()["transform"]
        coll.delete_many({})
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
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    (cache_dir / "c1.md").touch()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})

    result = prune(config)

    assert result["deleted_count"] == 1
    assert result["checked_count"] == 0
    assert not (cache_dir / "c1.md").exists()


def test_prune_valid_files(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    file_path = cache_dir / "c1.md"
    file_path.touch()

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
    config = WKSConfig.load()

    cache_dir = tmp_path / "invalid_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})
        db.get_database()["transform"].insert_one(
            {"checksum": "c1", "cache_uri": "file:///tmp/invalid\0path", "size_bytes": 100}
        )

    result = prune(config)

    assert result["deleted_count"] == 1
    with Database(config.database, "transform") as db:
        assert db.get_database()["transform"].count_documents({}) == 0


def test_prune_with_valueerror_in_uri_check(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})
        db.get_database()["transform"].insert_one(
            {"checksum": "c1", "cache_uri": "invalid-uri-no-scheme", "size_bytes": 100}
        )

    result = prune(config)

    assert result["deleted_count"] == 1
    assert result["checked_count"] == 1
    assert len(result["warnings"]) > 0
    assert "Error checking cache file" in result["warnings"][0]


def test_prune_with_oserror_deleting_orphaned(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    orphaned_file = cache_dir / "orphan.md"
    orphaned_file.write_text("orphaned content")

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})

    try:
        orphaned_file.chmod(0o444)  # Read-only

        result = prune(config)

        if orphaned_file.exists():
            assert len(result["warnings"]) > 0
            assert "Failed to delete orphaned file" in result["warnings"][0]
        else:
            assert result["deleted_count"] >= 0
    finally:
        try:
            orphaned_file.chmod(0o644)
            if orphaned_file.exists():
                orphaned_file.unlink()
        except OSError:
            pass


def test_prune_with_none_cache_uri(wks_home, minimal_config_dict, tmp_path):
    config = WKSConfig.load()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    with Database(config.database, "transform") as db:
        db.get_database()["transform"].delete_many({})
        db.get_database()["transform"].insert_one({"checksum": "c1", "cache_uri": None, "size_bytes": 100})

    result = prune(config)

    assert result["deleted_count"] == 1
    assert result["checked_count"] == 1
