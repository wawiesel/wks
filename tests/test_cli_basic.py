import argparse
import io
import json
import os
import signal
from contextlib import redirect_stdout
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

import mongomock
import pytest


def run_cli(args, monkeypatch=None):
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            rc = main(args)
        except SystemExit as exc:
            code = exc.code
            rc = code if isinstance(code, int) else 0
    return rc, buf.getvalue()


def test_cli_config_print_basic(monkeypatch):
    cfg = {"vault_path": "~/obsidian", "similarity": {"enabled": True}}
    monkeypatch.setattr('wks.cli.load_config', lambda: cfg)
    rc, out = run_cli(['--display','basic','config','print'], monkeypatch)
    assert rc == 0
    data = json.loads(out)
    assert data["vault_path"] == "~/obsidian"
    assert "mongo" in data
    assert data["mongo"]["uri"].startswith("mongodb://")
    assert "mongo_uri" not in data["similarity"]
    assert data["display"]["timestamp_format"] == "%Y-%m-%d %H:%M:%S"


def test_cli_version_flag():
    rc, out = run_cli(['--version'])
    assert rc == 0
    expected = importlib_metadata.version('wks')
    assert f"wkso {expected}" in out
    # git SHA is optional but when present must be within parentheses
    if '(' in out:
        assert out.strip().endswith(')')


def test_cli_db_query_space_basic(monkeypatch):
    # Minimal config
    monkeypatch.setattr('wks.cli.load_config', lambda: {
        'similarity': {
            'mongo_uri': 'mongodb://localhost:27027/',
            'database': 'wks_similarity',
            'collection': 'file_embeddings',
        }
    })
    # Seed DB
    client = mongomock.MongoClient()
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_one({'path': '/tmp/x.txt', 'timestamp': '2025-10-28T10:00:00.000000'})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    rc, out = run_cli(['--display','basic','db','query','--space','--filter','{}','--limit','1'])
    assert rc == 0
    assert '/tmp/x.txt' in out


def test_cli_service_status_basic_parsed(tmp_path, monkeypatch):
    # Prepare health.json under fake HOME
    home = tmp_path
    (home/'.wks').mkdir(parents=True, exist_ok=True)
    health = {
        'heartbeat_iso':'2025-10-28 12:00:00','uptime_hms':'00:01:00','pid': '12345',
        'avg_beats_per_min': 30.0, 'pending_deletes':0, 'pending_mods':0, 'last_error': None,
        'lock_present': True
    }
    (home/'.wks'/'health.json').write_text(json.dumps(health))
    monkeypatch.setattr('pathlib.Path.home', lambda: home)
    # Fake launchctl print
    def _fake_check_output(args, stderr=None):
        return ("""
gui/XXXX/com.wieselquist.wkso = {
    active count = 1
    path = /Users/you/Library/LaunchAgents/com.wieselquist.wkso.plist
    type = LaunchAgent
    state = running

    program = /path/to/python
    arguments = {
        /path/to/python
        -m
        wks.daemon
    }

    working directory = /path/to/cwd
    stdout path = /tmp/daemon.log
    stderr path = /tmp/daemon.error.log
    runs = 2
    pid = 12345
    last exit code = 0
}
""").encode('utf-8')
    monkeypatch.setattr('subprocess.check_output', _fake_check_output)
    monkeypatch.setattr('wks.cli._agent_installed', lambda: True)
    rc, out = run_cli(['--display','basic','service','status'])
    assert rc == 0
    # Parsed launch agent fields should appear
    assert 'Launch Agent:' in out
    assert 'state: running' in out
    assert 'pid: 12345' in out
    # Health metrics
    assert 'Heartbeat: 2025-10-28 12:00:00' in out


def test_cli_db_reset_drops_and_removes(tmp_path, monkeypatch):
    # Fake HOME for ~/.wks/mongodb
    home = tmp_path
    dbdir = home/'.wks'/'mongodb'/'db'
    dbdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr('pathlib.Path.home', lambda: home)
    # Config
    monkeypatch.setattr('wks.cli.load_config', lambda: {
        'similarity': {'mongo_uri':'mongodb://localhost:27027/','database':'wks_similarity','collection':'file_embeddings'}
    })
    # Fake Mongo drop
    class FakeClient:
        def __init__(self, *a, **k): pass
        class admin:
            @staticmethod
            def command(x): return {'ok':1}
        def drop_database(self, name): self.dropped = name
    monkeypatch.setattr('wks.cli.pymongo.MongoClient', FakeClient)
    rc, out = run_cli(['--display','basic','db','reset'])
    assert rc == 0
    assert not (home/'.wks'/'mongodb').exists()


def test_cli_index_basic_progress(monkeypatch):
    # Fake similarity loader and iter_files
    class FakeDB:
        def __init__(self): self.count=0
        def add_file(self, p): self.count+=1; return True
        def get_last_add_result(self): return {'content_hash':'abc','text':'content'}
        def get_stats(self): return {'database':'wks_similarity','collection':'file_embeddings','total_files': self.count}
    monkeypatch.setattr('wks.cli._load_similarity_required', lambda: (FakeDB(), {}))
    monkeypatch.setattr('wks.cli._iter_files', lambda paths, exts, cfg: [Path('a.txt'), Path('b.txt')])
    # Vault writer
    class FakeVault:
        def write_doc_text(self, *a, **k): pass
    monkeypatch.setattr('wks.cli._load_vault', lambda: FakeVault())
    rc, out = run_cli(['--display','basic','index','a.txt','b.txt'])
    assert rc == 0
    # Expect basic progress lines
    assert '[1/2]' in out or '[2/2]' in out


def test_ensure_mongo_running_autostarts(monkeypatch, tmp_path):
    import wks.cli as cli
    calls = []
    def fake_ping(uri, timeout_ms=500):
        calls.append((uri, timeout_ms))
        return len(calls) > 1
    monkeypatch.setattr(cli, "_mongo_ping", fake_ping)
    starts = []
    monkeypatch.setattr(cli.shutil, "which", lambda exe: "/usr/bin/mongod" if exe == "mongod" else None)
    def fake_check_call(cmd):
        starts.append(cmd)
    monkeypatch.setattr(cli.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(cli.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    cli._ensure_mongo_running("mongodb://localhost:27027/")
    assert starts, "mongod should be started when initial ping fails"
    assert len(calls) >= 2


def test_ensure_mongo_running_fails_without_mongod(monkeypatch):
    import wks.cli as cli
    monkeypatch.setattr(cli, "_mongo_ping", lambda uri, timeout_ms=500: False)
    monkeypatch.setattr(cli.shutil, "which", lambda exe: None)
    with pytest.raises(SystemExit):
        cli._ensure_mongo_running("mongodb://localhost:27027/")


def test_mongo_client_params_calls_ensure(monkeypatch, tmp_path):
    import wks.cli as cli
    called = {}
    def fake_ensure(uri):
        called['uri'] = uri
    monkeypatch.setattr(cli, "_ensure_mongo_running", fake_ensure)
    monkeypatch.setattr(cli, "MONGO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "MONGO_PID_FILE", tmp_path / 'mongod.pid')
    monkeypatch.setattr(cli, "MONGO_MANAGED_FLAG", tmp_path / 'managed')
    monkeypatch.setattr('wks.cli.load_config', lambda: {
        'mongo': {
            'uri': 'mongodb://localhost:27027/',
            'space_database': 'wks_similarity',
            'space_collection': 'file_embeddings',
        }
    })
    client, mongo_cfg = cli._mongo_client_params()
    assert called['uri'] == 'mongodb://localhost:27027/'
    assert mongo_cfg['space_database'] == 'wks_similarity'


def test_stop_managed_mongo(monkeypatch, tmp_path):
    import wks.cli as cli
    flag = tmp_path / 'managed'
    pidfile = tmp_path / 'mongod.pid'
    flag.write_text('123')
    pidfile.write_text('123')
    monkeypatch.setattr(cli, "MONGO_MANAGED_FLAG", flag)
    monkeypatch.setattr(cli, "MONGO_PID_FILE", pidfile)
    killed = []
    monkeypatch.setattr(cli, "_pid_running", lambda pid: False)
    monkeypatch.setattr(cli.os, 'kill', lambda pid, sig: killed.append((pid, sig)))
    cli._stop_managed_mongo()
    assert killed == [(123, signal.SIGTERM)]
    assert not flag.exists()
    assert not pidfile.exists()


def test_db_reset_restarts_mongo(monkeypatch, tmp_path):
    import wks.cli as cli
    calls = {}
    def fake_ensure(uri, record_start=False):
        calls['uri'] = uri
        calls['record'] = record_start
    monkeypatch.setattr(cli, "_ensure_mongo_running", fake_ensure)
    monkeypatch.setattr(cli, "_stop_managed_mongo", lambda: None)
    monkeypatch.setattr(cli, "mongo_settings", lambda cfg: {
        "uri": "mongodb://localhost:27027/",
        "space_database": "wks_similarity",
        "space_collection": "file_embeddings",
        "time_database": "wks_similarity",
        "time_collection": "file_snapshots",
    })
    class FakeClient:
        def __init__(self, *a, **k):
            pass
        class admin:
            @staticmethod
            def command(_):
                return {"ok": 1}
        def drop_database(self, name):
            pass
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: FakeClient())
    monkeypatch.setattr('wks.cli.load_config', lambda: {})
    rc, _ = run_cli(['--display','basic','db','reset'])
    assert rc == 0
    assert calls["uri"] == "mongodb://localhost:27027/"
    assert calls["record"] is True
