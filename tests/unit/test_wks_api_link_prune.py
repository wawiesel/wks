from pathlib import Path
from unittest.mock import MagicMock, patch

from wks.api.database.Database import Database
from wks.api.link.prune import prune


def test_prune_basic(tracked_wks_config, tmp_path):
    """Test basic link pruning (lines 14-88)."""
    # Seed nodes DB to define 'a' and 'b' as existing
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}, {"local_uri": "b"}])

    # Seed edges DB
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {"_id": "e1", "from_local_uri": "a", "to_local_uri": "b"},  # valid
                {"_id": "e2", "from_local_uri": "missing", "to_local_uri": "b"},  # e2.from missing
                {"_id": "e3", "from_local_uri": "a", "to_local_uri": "file:///missing.md"},  # e3.to missing on FS
                {"_id": "e4", "from_local_uri": "a", "to_local_uri": None},  # e4.to is None (line 77-79)
                {"_id": "e5", "from_local_uri": "a", "to_local_uri": "invalid-uri"},  # e5.to is invalid (line 86-87)
            ]
        )

    result = prune(tracked_wks_config)
    # e2, e3, e4, e5 should be deleted. e1 is valid.
    assert result["deleted_count"] == 4
    assert result["checked_count"] == 5

    # Check what's left
    with Database(tracked_wks_config.database, "edges") as db:
        docs = list(db.find({}))
        assert len(docs) == 1
        assert docs[0]["_id"] == "e1"


def test_prune_remote(tracked_wks_config, monkeypatch):
    """Test remote pruning and unsetting (lines 89-131)."""
    # Seed nodes
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}])

    # Seed edges with remote URIs
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "_id": "e1",
                    "from_local_uri": "a",
                    "to_local_uri": "file:///exists.txt",
                    "to_remote_uri": "http://google.com/404",
                    "from_remote_uri": "http://google.com/404",
                }
            ]
        )

    # Ensure exists.txt exists so it's not deleted due to local
    from wks.utils.path_to_uri import path_to_uri

    exists_path = Path(tracked_wks_config.vault.base_dir).expanduser() / "exists.txt"
    exists_path.parent.mkdir(parents=True, exist_ok=True)
    exists_path.touch()

    # Correct the edge in DB to use the actual URI of exists.txt
    with Database(tracked_wks_config.database, "edges") as db:
        db.update_one({"_id": "e1"}, {"$set": {"to_local_uri": path_to_uri(exists_path)}})

    # Break the local target (make it missing on disk)
    if exists_path.exists():
        exists_path.unlink()

    # Mock has_internet and requests.head
    monkeypatch.setattr("wks.api.link.prune.has_internet", lambda: True)

    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404

    with patch("requests.head", return_value=mock_resp_404):
        result = prune(tracked_wks_config, remote=True)
        # local is broken (missing file) AND remote is 404 -> delete (line 97, 114)
        assert result["deleted_count"] == 1

    # Check deletion
    with Database(tracked_wks_config.database, "edges") as db:
        doc = db.find_one({"_id": "e1"})
        assert doc is None


def test_prune_unset_from_remote(tracked_wks_config, monkeypatch):
    """Test unsetting from_remote_uri without deletion (lines 104-131)."""
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}])
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "_id": "e-from",
                    "from_local_uri": "a",
                    "to_local_uri": "a",  # local is OK
                    "from_remote_uri": "http://google.com/404",
                }
            ]
        )

    monkeypatch.setattr("wks.api.link.prune.has_internet", lambda: True)
    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404

    with patch("requests.head", return_value=mock_resp_404):
        result = prune(tracked_wks_config, remote=True)
        assert result["deleted_count"] == 0

    with Database(tracked_wks_config.database, "edges") as db:
        target_doc = db.find_one({"_id": "e-from"})
        assert target_doc is not None
        assert "from_remote_uri" not in target_doc


def test_prune_remote_error(tracked_wks_config, monkeypatch):
    """Test transient remote error doesn't delete/unset (lines 99-101, 109-110)."""
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "_id": "e1",
                    "from_local_uri": "a",
                    "to_local_uri": "file:///exists.txt",
                    "to_remote_uri": "http://fail.com",
                }
            ]
        )
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}])

    monkeypatch.setattr("wks.api.link.prune.has_internet", lambda: True)

    import requests

    with patch("requests.head", side_effect=requests.RequestException("fail")):
        result = prune(tracked_wks_config, remote=True)
        assert result["deleted_count"] == 0

    with Database(tracked_wks_config.database, "edges") as db:
        target_doc = db.find_one({"_id": "e1"})
        assert target_doc is not None
        assert "to_remote_uri" in target_doc


def test_prune_from_remote_error(tracked_wks_config, monkeypatch):
    """Test RequestException in from_remote HEAD (lines 109-110)."""
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "_id": "e-from-err",
                    "from_local_uri": "a",
                    "to_local_uri": "a",
                    "from_remote_uri": "http://err.com",
                }
            ]
        )
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}])

    monkeypatch.setattr("wks.api.link.prune.has_internet", lambda: True)
    import requests

    with patch("requests.head", side_effect=requests.RequestException("fail")):
        result = prune(tracked_wks_config, remote=True)
        assert result["deleted_count"] == 0

    with Database(tracked_wks_config.database, "edges") as db:
        target_doc = db.find_one({"_id": "e-from-err"})
        assert target_doc is not None
        assert "from_remote_uri" in target_doc


def test_prune_uri_to_path_error(tracked_wks_config, monkeypatch):
    """Test ValueError in uri_to_path (lines 86-87)."""
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many([{"_id": "e-uri-err", "from_local_uri": "a", "to_local_uri": "faulty://"}])
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_many([{"local_uri": "a"}])

    monkeypatch.setattr("wks.api.link.prune.uri_to_path", lambda x: exec("raise ValueError('bad uri')"))

    result = prune(tracked_wks_config)
    # Target is broken -> delete
    assert result["deleted_count"] == 1
