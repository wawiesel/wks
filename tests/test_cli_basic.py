import io
import json
from contextlib import redirect_stdout, redirect_stderr
import mongomock
import pytest

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

from wks.service_controller import ServiceStatusData, ServiceStatusLaunch


def run_cli(args):
    """Execute CLI command and capture stdout/stderr."""
    from wks.cli import main

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            rc = main(args)
        except SystemExit as exc:  # CLI exits on errors/--json flows
            rc = exc.code if isinstance(exc.code, int) else 0
    return rc, out_buf.getvalue(), err_buf.getvalue()


def parse_mcp_stream(payload: str):
    """Parse MCP display output (one JSON document per line)."""
    lines = [ln.strip() for ln in payload.splitlines() if ln.strip()]
    return [json.loads(line) for line in lines]


def test_cli_config_print_json(monkeypatch):
    cfg = {
        "vault": {"base_dir": "/vault", "wks_dir": "WKS"},
        "monitor": {
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {},
            "database": "wks.monitor",
            "touch_weight": 0.1,
            "priority": {},
            "max_documents": 100,
            "prune_interval_secs": 300.0,
        },
        "db": {"uri": "mongodb://localhost:27017/"},
    }
    monkeypatch.setattr('wks.cli.load_config', lambda: cfg)
    rc, out, _ = run_cli(['--display', 'mcp', 'config'])
    assert rc == 0
    data = json.loads(out)
    assert data["vault"]["base_dir"] == "/vault"
    assert data["monitor"]["database"] == "wks.monitor"


def test_cli_version_flag():
    rc, out, _ = run_cli(['--version'])
    assert rc == 0
    expected = importlib_metadata.version('wks')
    assert f"wks0 {expected}" in out


def test_cli_db_monitor_outputs_documents(monkeypatch):
    import wks.cli_db as cli_db

    config = {
        "monitor": {
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {},
            "database": "wks.monitor",
            "touch_weight": 0.1,
            "priority": {},
            "max_documents": 100,
            "prune_interval_secs": 300.0,
        },
        "db": {"uri": "mongodb://localhost:27017/"},
    }
    monkeypatch.setattr(cli_db, "load_config", lambda: config)

    client = mongomock.MongoClient()
    coll = client["wks"]["monitor"]
    coll.insert_one({"path": "/tmp/doc.txt", "priority": 10, "timestamp": "2025-01-01T00:00:00Z"})
    monkeypatch.setattr(cli_db, "connect_to_mongo", lambda uri: client)

    rc, out, _ = run_cli(['--display', 'mcp', 'db', 'monitor', '--filter', '{}', '--limit', '1'])
    assert rc == 0
    payloads = parse_mcp_stream(out)
    data_events = [evt for evt in payloads if evt.get("type") == "data"]
    assert data_events, f"No MCP data records found: {payloads}"
    assert data_events[0]["data"]["path"] == "/tmp/doc.txt"


def test_cli_db_vault_outputs_documents(monkeypatch):
    import wks.cli_db as cli_db

    config = {
        "vault": {"database": "wks.vault"},
        "db": {"uri": "mongodb://localhost:27017/"},
    }
    monkeypatch.setattr(cli_db, "load_config", lambda: config)

    client = mongomock.MongoClient()
    coll = client["wks"]["vault"]
    coll.insert_one({"doc_type": "link", "note_path": "Projects/Demo.md", "link_status": "ok"})
    monkeypatch.setattr(cli_db, "connect_to_mongo", lambda uri: client)

    rc, out, _ = run_cli(['--display', 'mcp', 'db', 'vault', '--filter', '{}', '--limit', '1'])
    assert rc == 0
    payloads = parse_mcp_stream(out)
    data_events = [evt for evt in payloads if evt.get("type") == "data"]
    assert data_events[0]["data"]["note_path"] == "Projects/Demo.md"


def test_cli_service_status_mcp(monkeypatch):
    import wks.service_controller as svc

    status = ServiceStatusData(
        running=True,
        pid=4242,
        lock=True,
        launch=ServiceStatusLaunch(state="running", pid="4242"),
        notes=["ok"],
    )
    monkeypatch.setattr(svc.ServiceController, "get_status", lambda: status)

    rc, out, _ = run_cli(['--display', 'mcp', 'service', 'status'])
    assert rc == 0
    payloads = parse_mcp_stream(out)
    success = next(evt for evt in payloads if evt.get("type") == "success")
    assert success["data"]["service"]["pid"] == 4242


def test_cli_vault_status_json(monkeypatch):
    from wks.cli.commands import vault as vault_cmd

    class FakeSummary:
        def to_dict(self):
            return {"total_links": 7}

    class FakeController:
        def __init__(self, cfg):
            self.cfg = cfg

        def summarize(self):
            return FakeSummary()

    monkeypatch.setattr(vault_cmd, "load_config", lambda: {"db": {}, "vault": {}})
    monkeypatch.setattr(vault_cmd, "VaultStatusController", lambda cfg: FakeController(cfg))

    rc, out, _ = run_cli(['--display', 'mcp', 'vault', 'status', '--json'])
    assert rc == 0
    data = json.loads(out)
    assert data["total_links"] == 7


@pytest.fixture(autouse=True)
def _temp_home(monkeypatch, tmp_path):
    """Isolate HOME for CLI tests."""
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    return tmp_path
