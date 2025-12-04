from types import SimpleNamespace

import typer

from wks.api import base as api_base
from wks.api.monitor import app as monitor_app_module
from wks.api.monitor import (
    cmd_add,
    cmd_check,
    cmd_managed_add,
    cmd_managed_list,
    cmd_managed_remove,
    cmd_managed_set_priority,
    cmd_remove,
    cmd_show,
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
    status_obj = SimpleNamespace(
        model_dump=lambda: {
            "tracked_files": 1,
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
    )
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_status.MonitorController.get_status", lambda _cfg: status_obj)

    result = cmd_status.cmd_status()
    assert result.output["success"] is False
    assert "issue" in result.result


def test_cmd_check_reports_monitored(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_check.MonitorController.check_path",
        lambda _cfg, path: {"is_monitored": True, "priority": 5, "path": path},
    )

    result = cmd_check.cmd_check(path="/tmp/demo.txt")
    assert result.output["is_monitored"] is True
    assert "priority" in result.result


def test_cmd_sync_wraps_output(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.api.monitor.cmd_sync.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.MonitorController.sync_path",
        lambda _cfg, path, recursive, progress_cb=None: {
            "success": True,
            "message": f"synced {path}",
            "files_synced": 1,
            "files_skipped": 0,
        },
    )

    result = cmd_sync.cmd_sync(path=".", recursive=False)
    assert result.output["files_synced"] == 1
    assert result.success is True


def test_cmd_show_lists_available_when_no_arg(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_show.cmd_show()
    assert result.output["available_lists"]
    assert result.output["success"] is True


def test_cmd_show_returns_list(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_show.MonitorController.get_list",
        lambda _cfg, list_name: {"success": True, "count": 2, "list_name": list_name},
    )

    result = cmd_show.cmd_show(list_name="include_paths")
    assert result.output["count"] == 2
    assert "Showing" in result.result


def test_cmd_add_saves_on_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(monitor=SimpleNamespace()))
    cfg.monitor = SimpleNamespace()  # type: ignore[attr-defined]
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    class DummyResult:
        def model_dump(self):
            return {"success": True, "message": "added"}

    monkeypatch.setattr(
        "wks.api.monitor.cmd_add.MonitorOperations.add_to_list",
        lambda monitor_cfg, list_name, value, resolve_path=False: DummyResult(),
    )

    result = cmd_add.cmd_add(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_remove_saves_on_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(monitor=SimpleNamespace()))
    cfg.monitor = SimpleNamespace()  # type: ignore[attr-defined]
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    class DummyResult:
        def model_dump(self):
            return {"success": True, "message": "removed"}

    monkeypatch.setattr(
        "wks.api.monitor.cmd_remove.MonitorOperations.remove_from_list",
        lambda monitor_cfg, list_name, value, resolve_path=False: DummyResult(),
    )

    result = cmd_remove.cmd_remove(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_managed_add_existing_returns_flag(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"existing": 1}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_add.find_matching_path_key", lambda mapping, path: path)

    result = cmd_managed_add.cmd_managed_add(path="existing", priority=5)
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 0


def test_cmd_managed_add_stores_and_saves(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_add.find_matching_path_key", lambda mapping, path: None)

    result = cmd_managed_add.cmd_managed_add(path="/tmp/new", priority=2)
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/new" in cfg.monitor.managed_directories


def test_cmd_managed_remove_not_found(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_remove.find_matching_path_key", lambda mapping, path: None)

    result = cmd_managed_remove.cmd_managed_remove(path="/tmp/miss")
    assert result.output["not_found"] is True
    assert cfg.save_calls == 0


def test_cmd_managed_remove_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"/tmp/a": 3}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_remove.find_matching_path_key", lambda mapping, path: path)

    result = cmd_managed_remove.cmd_managed_remove(path="/tmp/a")
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/a" not in cfg.monitor.managed_directories


def test_cmd_managed_set_priority_not_found(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_set_priority.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_set_priority.find_matching_path_key", lambda mapping, path: None)

    result = cmd_managed_set_priority.cmd_managed_set_priority(path="/tmp/a", priority=5)
    assert result.output["not_found"] is True


def test_cmd_managed_set_priority_success(monkeypatch):
    cfg = DummyConfig(SimpleNamespace(managed_directories={"/tmp/a": 1}))
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_set_priority.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_managed_set_priority.find_matching_path_key", lambda mapping, path: path)

    result = cmd_managed_set_priority.cmd_managed_set_priority(path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert cfg.monitor.managed_directories["/tmp/a"] == 7
    assert cfg.save_calls == 1


def test_cmd_managed_list_returns_stage_result(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    dummy_result = SimpleNamespace(model_dump=lambda: {"managed_directories": {}, "count": 0, "validation": {}})
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr(
        "wks.api.monitor.cmd_managed_list.MonitorController.get_managed_directories", lambda _cfg: dummy_result
    )

    result = cmd_managed_list.cmd_managed_list()
    assert result.output["count"] == 0


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

