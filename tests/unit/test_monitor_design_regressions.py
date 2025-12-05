import types
from pathlib import Path

import pytest

from wks.api.monitor import cmd_sync
from wks.api.monitor.MonitorConfig import MonitorConfig
from wks.monitor_rules import MonitorRules


@pytest.mark.monitor
def test_monitor_sync_uses_mongo_settings_and_returns_stage_result(monkeypatch, tmp_path):
    """Sync should use config.mongo.uri and build StageResult without TypeError."""

    file_path = tmp_path / "doc.txt"
    file_path.write_text("hello")

    monitor_cfg = MonitorConfig(
        include_paths=[str(tmp_path)],
        exclude_paths=[],
        include_dirnames=[],
        exclude_dirnames=[],
        include_globs=[],
        exclude_globs=[],
        database="wks.monitor",
        managed_directories={},
        priority={},
        max_documents=1000000,
        prune_interval_secs=300.0,
    )
    config = types.SimpleNamespace(monitor=monitor_cfg, mongo=types.SimpleNamespace(uri="mongodb://example"))

    calls: dict[str, object] = {}

    class DummyCollection:
        def __init__(self):
            self.docs = {}

        def find_one(self, _query, _projection=None):
            return None

        def update_one(self, _query, update, **_kwargs):
            # capture what would be written
            calls["last_doc"] = update.get("$set", update)

    class DummyDB(dict):
        def __getitem__(self, name):
            return DummyCollection()

    class DummyClient:
        def __init__(self, uri, *_args, **_kwargs):
            calls["uri"] = uri
            self.db = DummyDB()

        def __getitem__(self, name):
            return self.db

        def server_info(self):
            return {}

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr("pymongo.MongoClient", DummyClient)
    monkeypatch.setattr("wks.monitor.controller.MongoClient", DummyClient)
    monkeypatch.setattr("wks.api.monitor.cmd_sync.WKSConfig.load", lambda: config)

    result = cmd_sync.cmd_sync(str(file_path))

    assert calls["uri"] == config.mongo.uri
    assert isinstance(result.output, dict)
    assert result.output.get("success") is True
    assert calls.get("last_doc") is not None
    assert calls.get("closed") is True


@pytest.mark.monitor
def test_monitor_rules_default_to_exclude_without_matching_root(tmp_path):
    """Spec requires paths with no include/exclude ancestor be excluded."""

    path_outside = Path(tmp_path / "outside.txt")
    path_outside.write_text("x")

    rules = MonitorRules(
        include_paths=[],
        exclude_paths=[],
        include_dirnames=[],
        exclude_dirnames=[],
        include_globs=[],
        exclude_globs=[],
    )

    allowed, trace = rules.explain(path_outside)

    assert allowed is False
    assert any("outside include_paths" in msg.lower() or "exclude" in msg.lower() for msg in trace)
