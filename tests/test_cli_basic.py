import argparse
import io
import json
import os
import signal
import threading
from contextlib import redirect_stdout
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

import mongomock
import pytest

from wks.constants import WKS_HOME_EXT


@pytest.fixture(autouse=True)
def _temp_home(monkeypatch, tmp_path):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)


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


def test_cli_config_print_json(monkeypatch):
    cfg = {"vault_path": "~/obsidian", "similarity": {"enabled": True}}
    monkeypatch.setattr('wks.cli.load_config', lambda: cfg)
    rc, out = run_cli(['--display','json','config','print'], monkeypatch)
    assert rc == 0
    data = json.loads(out)
    assert data["vault_path"] == "~/obsidian"
    assert "mongo" in data
    assert data["mongo"]["uri"].startswith("mongodb://")
    assert data["mongo"]["compatibility"]["space"] == "space-v1"
    assert data["mongo"]["compatibility"]["time"] == "time-v1"
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


def test_cli_db_query_space_json(monkeypatch):
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
    rc, out = run_cli(['--display','json','db','query','--space','--filter','{}','--limit','1'])
    assert rc == 0
    assert '/tmp/x.txt' in out


def test_cli_service_status_json_parsed(tmp_path, monkeypatch):
    # Prepare health.json under fake HOME
    home = tmp_path
    (home / WKS_HOME_EXT).mkdir(parents=True, exist_ok=True)
    health = {
        'uptime_hms':'00:01:00','pid': '12345',
        'avg_beats_per_min': 30.0, 'pending_deletes':0, 'pending_mods':0, 'last_error': None,
        'lock_present': True
    }
    (home / WKS_HOME_EXT / 'health.json').write_text(json.dumps(health))
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
    class FakeCursor(list):
        def sort(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self

    class FakeCollection:
        def count_documents(self, *_):
            return 0
        def find(self, *args, **kwargs):
            return FakeCursor()

    class FakeDB:
        def __getitem__(self, name):
            return FakeCollection()

    class FakeClient:
        def __init__(self, *a, **k):
            self.admin = self
        def command(self, *_):
            return {"ok": 1}
        def __getitem__(self, name):
            return FakeDB()
        def close(self):
            pass

    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: FakeClient())

    rc, out = run_cli(['--display','json','service','status'])
    assert rc == 0
    data = json.loads(out)
    service = data['service']
    assert service['pid'] == 12345
    assert service['lock'] is True
    assert service['db_ops_last_minute'] >= 0
    if service['fs_rate_short'] is not None:
        assert service['fs_rate_short'] == pytest.approx(0.0)
    if service['fs_rate_long'] is not None:
        assert service['fs_rate_long'] == pytest.approx(0.0)
    if service['fs_rate_weighted'] is not None:
        assert service['fs_rate_weighted'] == pytest.approx(0.0)
    launch = data['launch_agent']
    assert launch['state'] == 'running'
    assert launch['pid'] == '12345'


def test_cli_db_reset_drops_and_removes(tmp_path, monkeypatch):
    # Fake HOME for ~/.wks/mongodb
    home = tmp_path
    dbdir = home / WKS_HOME_EXT / 'mongodb' / 'db'
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
    rc, out = run_cli(['--display','json','db','reset'])
    assert rc == 0
    assert not (home / WKS_HOME_EXT / 'mongodb').exists()


def test_cli_index_json_progress(monkeypatch):
    # Fake similarity loader and iter_files
    class FakeDB:
        def __init__(self): self.count=0
        def add_file(self, p, extraction=None, **kwargs): self.count+=1; return True
        def get_last_add_result(self): return {'content_checksum':'abc','text':'content','timings': {'embed': 0.01, 'db_update': 0.002, 'chunks': 0.001}}
        def get_stats(self): return {'database':'wks_similarity','collection':'file_embeddings','total_files': self.count, 'total_bytes': 1234}
    monkeypatch.setattr('wks.cli._load_similarity_required', lambda: (FakeDB(), {}))
    monkeypatch.setattr('wks.cli._iter_files', lambda paths, exts, cfg: [Path('a.txt'), Path('b.txt')])
    class FakeExtractor:
        def extract(self, path, persist=True):
            from types import SimpleNamespace
            return SimpleNamespace(
                text='dummy content',
                content_path=None,
                content_checksum='abc',
                content_bytes=12,
                engine='builtin',
            )
    monkeypatch.setattr('wks.cli._build_extractor', lambda cfg: FakeExtractor())
    # Vault writer
    class FakeVault:
        def write_doc_text(self, *a, **k): pass
    monkeypatch.setattr('wks.cli._load_vault', lambda: FakeVault())
    rc, out = run_cli(['--display','json','index','a.txt','b.txt'])
    assert rc == 0
    # Expect textual progress lines even in JSON mode (shows in captured output)
    assert '[1/2]' in out or '[2/2]' in out
    assert 'total_bytes=1234' in out
    # Plain timing summary should include headers and aligned units
    assert 'Timing Details' in out
    assert 'Totals' in out
    assert 'Hash' in out and 'Extract' in out and 'Embed' in out
    assert ' ms' in out or ' s' in out


def test_cli_extract_runs_extractor(monkeypatch):
    monkeypatch.setattr('wks.cli.load_config', lambda: {'similarity': {'include_extensions': ['.txt']}})
    files = [Path('/tmp/a.txt'), Path('/tmp/b.txt')]
    monkeypatch.setattr('wks.cli._iter_files', lambda paths, exts, cfg: files)

    class FakeExtractor:
        def __init__(self): self.calls = []
        def extract(self, path, persist=True):
            self.calls.append(path)
            from types import SimpleNamespace
            return SimpleNamespace(
                text='content',
                content_path=Path(f'/tmp/.wkso/{path.name}.md'),
                content_checksum='hash',
                content_bytes=42,
                engine='builtin',
            )

    fake = FakeExtractor()
    monkeypatch.setattr('wks.cli._build_extractor', lambda cfg: fake)
    rc, out = run_cli(['--display','json','extract','/tmp'])
    assert rc == 0
    assert len(fake.calls) == len(files)
    for path in files:
        assert str(path) in out
        assert f".wkso/{path.name}.md" in out


def test_cli_index_untrack(monkeypatch):
    class FakeDB:
        def __init__(self): self.removed=[]
        def remove_file(self, path, **kwargs):
            self.removed.append(path)
            return True
    fake_db = FakeDB()
    monkeypatch.setattr('wks.cli._load_similarity_required', lambda: (fake_db, {}))
    monkeypatch.setattr('wks.cli._iter_files', lambda paths, exts, cfg: [Path('one.txt'), Path('two.txt')])
    monkeypatch.setattr('wks.cli.load_config', lambda: {})
    rc, out = run_cli(['--display','json','index','--untrack','one.txt','two.txt'])
    assert rc == 0
    assert 'Untracked 2 file(s)' in out
    assert fake_db.removed == [Path('one.txt'), Path('two.txt')]


def test_ensure_mongo_running_autostarts(monkeypatch, tmp_path):
    import wks.mongoctl as mongoctl
    calls = []
    def fake_ping(uri, timeout_ms=500):
        calls.append((uri, timeout_ms))
        return len(calls) > 1
    monkeypatch.setattr(mongoctl, "mongo_ping", fake_ping)
    starts = []
    monkeypatch.setattr(mongoctl.shutil, "which", lambda exe: "/usr/bin/mongod" if exe == "mongod" else None)
    def fake_check_call(cmd, *args, **kwargs):
        starts.append(cmd)
    monkeypatch.setattr(mongoctl.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(mongoctl.time, "sleep", lambda _: None)
    mongoctl.ensure_mongo_running("mongodb://localhost:27027/")
    assert starts, "mongod should be started when initial ping fails"
    assert len(calls) >= 2


def test_ensure_mongo_running_fails_without_mongod(monkeypatch):
    import wks.mongoctl as mongoctl
    monkeypatch.setattr(mongoctl, "mongo_ping", lambda uri, timeout_ms=500: False)
    monkeypatch.setattr(mongoctl.shutil, "which", lambda exe: None)
    with pytest.raises(SystemExit):
        mongoctl.ensure_mongo_running("mongodb://localhost:27027/")


def test_mongo_client_params_calls_ensure(monkeypatch, tmp_path):
    import wks.cli as cli
    import wks.mongoctl as mongoctl
    called = {}
    def fake_ensure(uri, record_start=False):
        called['ensure_uri'] = uri
        called['record'] = record_start
    monkeypatch.setattr(mongoctl, "ensure_mongo_running", fake_ensure)
    def fake_create(uri, server_timeout=500, connect_timeout=500, ensure_running=True):
        if ensure_running:
            fake_ensure(uri)
        import mongomock
        return mongomock.MongoClient()
    monkeypatch.setattr(mongoctl, "create_client", fake_create)
    monkeypatch.setattr('wks.cli.load_config', lambda: {
        'mongo': {
            'uri': 'mongodb://localhost:27027/',
            'space_database': 'wks_similarity',
            'space_collection': 'file_embeddings',
        }
    })
    client, mongo_cfg = cli._mongo_client_params()
    assert called['ensure_uri'] == 'mongodb://localhost:27027/'
    assert mongo_cfg['space_database'] == 'wks_similarity'


def test_mongo_client_params_skip_ensure(monkeypatch, tmp_path):
    import wks.cli as cli
    import wks.mongoctl as mongoctl
    called = {"ensure": 0}
    def fail_ensure(uri, record_start=False):
        called["ensure"] += 1
        raise AssertionError("ensure should not run")
    monkeypatch.setattr(mongoctl, "ensure_mongo_running", fail_ensure)
    def fake_create(uri, server_timeout=500, connect_timeout=500, ensure_running=True):
        called["ensure_running"] = ensure_running
        import mongomock
        return mongomock.MongoClient()
    monkeypatch.setattr(mongoctl, "create_client", fake_create)
    monkeypatch.setattr('wks.cli.load_config', lambda: {
        'mongo': {
            'uri': 'mongodb://localhost:27027/',
            'space_database': 'wks_similarity',
            'space_collection': 'file_embeddings',
        }
    })
    client, mongo_cfg = cli._mongo_client_params(ensure_running=False)
    assert called.get("ensure_running") is False
    assert called["ensure"] == 0
    assert mongo_cfg['space_collection'] == 'file_embeddings'


def test_stop_managed_mongo(monkeypatch, tmp_path):
    import wks.mongoctl as mongoctl
    flag = tmp_path / 'managed'
    pidfile = tmp_path / 'mongod.pid'
    flag.write_text('123')
    pidfile.write_text('123')
    monkeypatch.setattr(mongoctl, "MONGO_MANAGED_FLAG", flag)
    monkeypatch.setattr(mongoctl, "MONGO_PID_FILE", pidfile)
    killed = []
    monkeypatch.setattr(mongoctl, "pid_running", lambda pid: False)
    monkeypatch.setattr(mongoctl.os, 'kill', lambda pid, sig: killed.append((pid, sig)))
    mongoctl.stop_managed_mongo()
    assert killed == [(123, signal.SIGTERM)]
    assert not flag.exists()
    assert not pidfile.exists()


def test_mongo_guard_restarts_local(monkeypatch):
    import wks.mongoctl as mongoctl
    ping_values = iter([False, True])
    def fake_ping(uri, timeout_ms=500):
        try:
            return next(ping_values)
        except StopIteration:
            return True
    monkeypatch.setattr(mongoctl, "mongo_ping", fake_ping)
    ensure_calls = []
    resumed = threading.Event()
    def fake_ensure(uri, record_start=False):
        ensure_calls.append(record_start)
        if len(ensure_calls) > 1:
            resumed.set()
    monkeypatch.setattr(mongoctl, "ensure_mongo_running", fake_ensure)
    guard = mongoctl.MongoGuard("mongodb://localhost:27027/", ping_interval=0.01)
    guard.start(record_start=True)
    assert resumed.wait(0.3), "Guard should trigger a restart when ping fails"
    guard.stop()
    assert len(ensure_calls) >= 2


def test_db_reset_restarts_mongo(monkeypatch, tmp_path):
    import wks.cli as cli
    import wks.mongoctl as mongoctl
    calls = {}
    def fake_ensure(uri, record_start=False):
        calls['uri'] = uri
        calls['record'] = record_start
    monkeypatch.setattr(mongoctl, "ensure_mongo_running", fake_ensure)
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
    rc, _ = run_cli(['--display','json','db','reset'])
    assert rc == 0
    assert calls["uri"] == "mongodb://localhost:27027/"
    assert calls["record"] is True
