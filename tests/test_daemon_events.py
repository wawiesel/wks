from __future__ import annotations

from datetime import datetime

from wks.monitor_rules import MonitorRules


class FakeCollection:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.deleted: list[str] = []

    def count_documents(self, filt, limit=None):
        path = filt.get("path")
        if isinstance(path, dict) and "$in" in path:
            return sum(1 for candidate in path["$in"] if candidate in self.docs)
        if isinstance(path, str):
            return 1 if path in self.docs else 0
        return len(self.docs)

    def find_one(self, filt, projection=None):
        path = filt.get("path")
        if not isinstance(path, str):
            return None
        doc = self.docs.get(path)
        if not doc:
            return None
        if projection:
            return {key: doc.get(key) for key in projection if key in doc}
        return doc

    def update_one(self, filt, update, upsert=False):
        path = filt.get("path")
        if not isinstance(path, str):
            return
        doc = update.get("$set", {})
        self.docs[path] = dict(doc)

    def delete_one(self, filt):
        path = filt.get("path")
        if isinstance(path, str):
            self.docs.pop(path, None)
            self.deleted.append(path)


def _build_daemon(monkeypatch, tmp_path, collection: FakeCollection):
    from wks import daemon as daemon_mod

    class DummyVault:
        def __init__(self, *args, **kwargs):
            pass

        def ensure_structure(self):
            pass

        def log_file_operation(self, *args, **kwargs):
            pass

        def update_link_on_move(self, *args, **kwargs):
            pass

        def update_vault_links_on_move(self, *args, **kwargs):
            pass

        def mark_reference_deleted(self, *args, **kwargs):
            pass

    class DummyIndexer:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_config(cls, vault, cfg):
            return cls()

        def sync(self):
            pass

    monkeypatch.setattr(daemon_mod, "ObsidianVault", DummyVault)
    monkeypatch.setattr(daemon_mod, "VaultLinkIndexer", DummyIndexer)
    monkeypatch.setattr(daemon_mod.WKSDaemon, "_enforce_monitor_db_limit", lambda self: None)

    monitor_rules = MonitorRules(
        include_paths=[str(tmp_path)],
        exclude_paths=[],
        include_dirnames=[],
        exclude_dirnames=[],
        include_globs=[],
        exclude_globs=[],
    )
    config = {
        "monitor": {
            "include_paths": [str(tmp_path)],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {str(tmp_path): 100},
            "touch_weight": 0.5,
            "database": "wks.monitor",
        },
        "vault": {
            "base_dir": str(tmp_path),
            "wks_dir": "WKS",
            "update_frequency_seconds": 10,
        },
    }

    return daemon_mod.WKSDaemon(
        config=config,
        vault_path=tmp_path,
        base_dir="WKS",
        monitor_paths=[tmp_path],
        monitor_rules=monitor_rules,
        mongo_uri="mongodb://localhost:27017/",
        monitor_collection=collection,
    )


def test_move_into_tracked_directory_records_file(monkeypatch, tmp_path):
    coll = FakeCollection()
    daemon = _build_daemon(monkeypatch, tmp_path, coll)

    dest = tmp_path / "tracked" / "report.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("new data")
    src = tmp_path / "untracked" / "report.txt"
    src.parent.mkdir(parents=True, exist_ok=True)

    daemon._handle_move_event(str(src), str(dest))

    assert dest.as_uri() in coll.docs


def test_move_directory_drops_source_but_skips_destination(monkeypatch, tmp_path):
    coll = FakeCollection()
    src = tmp_path / "projects" / "results.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    coll.docs[src.as_uri()] = {
        "path": src.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    dest_dir = tmp_path / "archive" / "results"
    dest_dir.mkdir(parents=True, exist_ok=True)

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._handle_move_event(str(src), str(dest_dir))

    assert src.as_uri() not in coll.docs
    assert dest_dir.as_uri() not in coll.docs


def test_move_tracked_file_updates_destination(monkeypatch, tmp_path):
    coll = FakeCollection()
    src = tmp_path / "reports" / "weekly.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("old")
    coll.docs[src.as_uri()] = {
        "path": src.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    dest = tmp_path / "archive" / "weekly.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("new")

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._handle_move_event(str(src), str(dest))

    assert src.as_uri() not in coll.docs
    assert dest.as_uri() in coll.docs


def test_delete_event_only_tracks_known_paths(monkeypatch, tmp_path):
    coll = FakeCollection()
    daemon = _build_daemon(monkeypatch, tmp_path, coll)

    tracked = tmp_path / "keep.txt"
    tracked.write_text("x")
    coll.docs[tracked.as_uri()] = {
        "path": tracked.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    untracked = tmp_path / "ignore.txt"

    daemon._handle_delete_event(untracked)
    assert not daemon._pending_deletes

    daemon._handle_delete_event(tracked)
    assert tracked.resolve().as_posix() in daemon._pending_deletes


def test_delete_event_flush_removes_db_row(monkeypatch, tmp_path):
    coll = FakeCollection()
    tracked = tmp_path / "remove.txt"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("bye")
    coll.docs[tracked.as_uri()] = {
        "path": tracked.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._delete_grace_secs = 0
    daemon._handle_delete_event(tracked)
    tracked.unlink()

    daemon._maybe_flush_pending_deletes()

    assert tracked.as_uri() not in coll.docs
    assert tracked.resolve().as_posix() not in daemon._pending_deletes
