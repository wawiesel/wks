import mongomock
import pytest

from wks.dbmeta import (
    ensure_db_compat,
    resolve_db_compatibility,
    IncompatibleDatabase,
    SPACE_COMPAT_DEFAULT,
    TIME_COMPAT_DEFAULT,
)


def test_ensure_db_compat_inserts_metadata():
    client = mongomock.MongoClient()
    tag = ensure_db_compat(client, "wks_similarity", "space", SPACE_COMPAT_DEFAULT, product_version="0.0.0")
    assert tag == SPACE_COMPAT_DEFAULT
    doc = client["wks_similarity"]["_wks_meta"].find_one({"_id": "space"})
    assert doc["compat_tag"] == SPACE_COMPAT_DEFAULT
    assert doc["product_version"] == "0.0.0"


def test_ensure_db_compat_detects_mismatch():
    client = mongomock.MongoClient()
    ensure_db_compat(client, "wks_similarity", "space", "space-v1")
    with pytest.raises(IncompatibleDatabase):
        ensure_db_compat(client, "wks_similarity", "space", "space-v2")


def test_resolve_db_compat_defaults():
    cfg = {}
    space_tag, time_tag = resolve_db_compatibility(cfg)
    assert space_tag == SPACE_COMPAT_DEFAULT
    assert time_tag == TIME_COMPAT_DEFAULT


def test_resolve_db_compat_overrides():
    cfg = {"mongo": {"compatibility": {"space": "legacy-space", "time": "legacy-time"}}}
    space_tag, time_tag = resolve_db_compatibility(cfg)
    assert space_tag == "legacy-space"
    assert time_tag == "legacy-time"
