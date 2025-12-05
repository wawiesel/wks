from types import SimpleNamespace

import typer

from wks.api import base as api_base
from wks.api.monitor import app as monitor_app_module
from wks.api.monitor import (
    cmd_filter_add,
    cmd_filter_show,
    cmd_filter_remove,
    cmd_check,
    cmd_priority_add,
    cmd_priority_show,
    cmd_priority_remove,
    cmd_status,
    cmd_sync,
)


class DummyConfig:
    def __init__(self, monitor):
        self.monitor = monitor
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


def test_stage_result_success_inferred():
    result = api_base.StageResult(announce="a", result="r", output={"success": False})
    assert result.success is False
    assert result.output["success"] is False


def test_inject_config_injects(monkeypatch):
    cfg = object()

    @api_base.inject_config
    def fn(config):
        return config

    monkeypatch.setattr("wks.api.base.WKSConfig.load", lambda: cfg)
    assert fn() is cfg


def test_get_typer_command_schema_skips_config_and_marks_required():
    app = typer.Typer()

    def sample(config, path: str, optional: int = 3):  # type: ignore[unused-argument]
        return path, optional

    app.command(name="sample")(sample)

    schema = api_base.get_typer_command_schema(app, "sample")
    assert "config" not in schema["properties"]
    assert "path" in schema["required"]
    assert "optional" not in (schema["required"] or [])


def test_cmd_status_sets_success_based_on_issues(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    monkeypatch.setattr(
        "wks.api.monitor.cmd_status.validator_validate_config",
        lambda _cfg: SimpleNamespace(
            model_dump=lambda: {
                "issues": ["bad"],
                "redundancies": [],
                "managed_directories": {},
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            }
        ),
    )
    monkeypatch.setattr(
        "pymongo.MongoClient",
        lambda *args, **kwargs: SimpleNamespace(
            server_info=lambda: None,
            __getitem__=lambda self, k: SimpleNamespace(__getitem__=lambda _s, _k: SimpleNamespace(count_documents=lambda _q: 1)),
            close=lambda: None,
        ),
    )  # type: ignore

    result = cmd_status.cmd_status()
    assert result.output["success"] is False
    assert "issue" in result.result


def test_cmd_check_reports_monitored(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    class DummyRules:
        def explain(self, _path):
            return True, ["Included by rule"]

    monkeypatch.setattr("wks.api.monitor.cmd_check.MonitorRules.from_config", lambda _cfg: DummyRules())
    monkeypatch.setattr(
        "wks.api.monitor._check_calculate_path_priority.priority_calculate_priority",
        lambda _path, _dirs, _weights: 5,
    )

    result = cmd_check.cmd_check(path="/tmp/demo.txt")
    assert result.output["is_monitored"] is True
    assert "priority" in result.result


def test_cmd_sync_wraps_output(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.api.monitor.cmd_sync.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync._sync_execute",
        lambda _cfg, path, recursive: {
            "success": True,
            "message": f"synced {path}",
            "files_synced": 1,
            "files_skipped": 0,
        },
    )

    result = cmd_sync.cmd_sync(path=".", recursive=False)
    assert result.output["files_synced"] == 1
    assert result.success is True


def test_cmd_filter_show_lists_available_when_no_arg(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_show.cmd_filter_show()
    assert result.output["available_lists"]
    assert result.output["success"] is True


def test_cmd_filter_show_returns_list(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_filter_show._LIST_NAMES",
        (
            "include_paths",
            "exclude_paths",
            "include_dirnames",
            "exclude_dirnames",
            "include_globs",
            "exclude_globs",
        ),
    )
    cfg.monitor.include_paths = ["a", "b"]

    result = cmd_filter_show.cmd_filter_show(list_name="include_paths")
    assert result.output["count"] == 2
    assert "Showing" in result.result


def test_cmd_filter_add_saves_on_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    cfg.monitor.include_paths = []
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_saves_on_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    cfg.monitor.include_paths = ["/tmp/x"]
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_remove.cmd_filter_remove(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_priority_add_existing_returns_flag(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"existing": 1}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_add.cmd_priority_add(path="existing", priority=5)
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 1


def test_cmd_priority_add_stores_and_saves(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/new", priority=2)
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/new" in cfg.monitor.managed_directories


def test_cmd_priority_remove_not_found(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_remove.cmd_priority_remove(path="/tmp/miss")
    assert result.output["not_found"] is True
    assert cfg.save_calls == 0


def test_cmd_priority_remove_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"/tmp/a": 3}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_remove.cmd_priority_remove(path="/tmp/a")
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/a" not in cfg.monitor.managed_directories


def test_cmd_priority_add_not_found_creates(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/a", priority=5)
    assert result.output["success"] is True
    assert cfg.monitor.managed_directories["/tmp/a"] == 5
    assert cfg.save_calls == 1


def test_cmd_priority_add_updates(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"/tmp/a": 1}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert cfg.monitor.managed_directories["/tmp/a"] == 7
    assert cfg.save_calls == 1


def test_cmd_priority_show_returns_stage_result(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"/tmp/a": 1.0}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    class DummyRules:
        def explain(self, _path):
            return True, []

    monkeypatch.setattr("wks.api.monitor.cmd_priority_show.MonitorRules.from_config", lambda _cfg: DummyRules())

    result = cmd_priority_show.cmd_priority_show()
    assert result.output["count"] == 1


def test_monitor_app_wrapper_non_cli(monkeypatch):
    calls = []

    class DummyDisplay:
        pass

    def progress_cb(callback):
        callback("step", 1.0)
        calls.append("progress")

    monkeypatch.setattr("wks.api.monitor.app.get_display", lambda *_args: DummyDisplay())
    stage = api_base.StageResult(
        announce="a",
        result="done",
        output={"success": True, "payload": 1},
        progress_callback=progress_cb,
        progress_total=2,
    )

    wrapped = monitor_app_module._handle_stage_result(lambda: stage)
    output = wrapped()
    assert output["payload"] == 1
    assert calls == ["progress"]
