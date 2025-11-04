import io
import json
from contextlib import redirect_stdout

import mongomock
import pytest


@pytest.fixture()
def singleton_client():
    # One shared in-memory client for the test
    return mongomock.MongoClient()


def test_db_info_json_lists_tracked_and_latest(monkeypatch, tmp_path, singleton_client):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    # Minimal config for space DB
    def _cfg():
        return {
            'similarity': {
                'mongo_uri': 'mongodb://localhost:27027/',
                'database': 'wks_similarity',
                'collection': 'file_embeddings',
            }
        }
    monkeypatch.setattr('wks.cli.load_config', _cfg)

    # Seed in-memory DB
    client = singleton_client
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_many([
        {'path': 'file:///tmp/x.txt', 'timestamp': '2025-10-28T10:00:00.000000', 'checksum': '0123456789abcdef', 'bytes': 1024, 'angle': 2.5},
        {'path': 'file:///tmp/y.txt', 'timestamp': '2025-10-28T11:00:00.000000', 'checksum': 'fedcba9876543210', 'bytes': 2048, 'angle': 5.0},
    ])

    # Ensure the CLI uses the same singleton client
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)

    # Run CLI
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','json','db','info','-n','2','--space'])
    out = buf.getvalue()
    data = json.loads(out)
    assert rc == 0
    assert data.get('tracked_files') == 2 or data.get('total_docs') == 2
    latest = data.get('latest') or data.get('records') or []
    assert len(latest) >= 1
    assert any('file:///tmp/x.txt' in (item.get('uri') or '') or 'file:///tmp/y.txt' in (item.get('uri') or '') for item in latest)


def test_db_info_uses_top_level_mongo(monkeypatch, tmp_path, singleton_client):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    def _cfg():
        return {
            'mongo': {
                'uri': 'mongodb://localhost:27027/',
                'space_database': 'wks_similarity',
                'space_collection': 'file_embeddings',
            }
        }
    monkeypatch.setattr('wks.cli.load_config', _cfg)
    client = singleton_client
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_one({'path': 'file:///tmp/z.txt', 'timestamp': '2025-10-28T12:00:00.000000', 'checksum': 'abcdef1234567890', 'bytes': 512, 'angle': 1.0})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','json','db','info','--space'])
    assert rc == 0
    output = buf.getvalue()
    data = json.loads(output)
    latest = data.get('latest') or []
    assert any(item.get('uri') == 'file:///tmp/z.txt' for item in latest)


def test_db_info_respects_timestamp_format(monkeypatch, tmp_path, singleton_client):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    def _cfg():
        return {
            'display': {'timestamp_format': '%m/%d/%Y %H:%M'},
            'mongo': {
                'uri': 'mongodb://localhost:27027/',
                'space_database': 'wks_similarity',
                'space_collection': 'file_embeddings',
            }
        }
    monkeypatch.setattr('wks.cli.load_config', _cfg)
    client = singleton_client
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_one({'path': 'file:///tmp/f.txt', 'timestamp': '2025-10-28T08:15:00.000000', 'checksum': '0123456789abcdef', 'bytes': 256, 'angle': 0.0})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','json','db','info','--space'])
    assert rc == 0
    output = buf.getvalue()
    data = json.loads(output)
    latest = data.get('latest') or []
    assert any('10/28/2025 08:15' in (item.get('timestamp') or '') for item in latest)


def test_db_info_reference_differences(monkeypatch, tmp_path, singleton_client):
    ref_file = tmp_path / 'ref.txt'
    ref_file.write_text('reference content', encoding='utf-8')
    ref_uri = ref_file.resolve().as_uri()

    def _cfg():
        return {
            'similarity': {
                'mongo_uri': 'mongodb://localhost:27027/',
                'database': 'wks_similarity',
                'collection': 'file_embeddings',
            },
            'extract': {
                'engine': 'builtin',
                'ocr': False,
                'timeout_secs': 30,
            }
        }

    monkeypatch.setattr('wks.cli.load_config', _cfg)

    class FakeDB:
        def __init__(self):
            class _Client:
                def close(self_inner):
                    pass
            self.client = _Client()
        def add_file(self, *a, **k):
            return True

    monkeypatch.setattr('wks.cli._load_similarity_required', lambda: (FakeDB(), {}))

    class DummyExtractor:
        def extract(self, path, persist=True):
            from types import SimpleNamespace
            return SimpleNamespace(
                text='content',
                content_path=None,
                content_checksum='hash',
                content_bytes=10,
            )

    monkeypatch.setattr('wks.cli._build_extractor', lambda cfg: DummyExtractor())

    client = singleton_client
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_many([
        {
            'path': ref_uri,
            'path_local': str(ref_file.resolve()),
            'timestamp': '2025-10-30T00:00:00Z',
            'checksum': 'aaaa',
            'bytes': 100,
            'embedding': [1.0, 0.0, 0.0],
        },
        {
            'path': 'file:///tmp/other.txt',
            'path_local': '/tmp/other.txt',
            'timestamp': '2025-10-30T01:00:00Z',
            'checksum': 'bbbb',
            'bytes': 200,
            'embedding': [0.0, 1.0, 0.0],
        },
    ])

    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)

    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main([
            '--display', 'json',
            'db', 'info', '--space',
            '--reference', str(ref_file),
            '--latest', '2',
        ])

    out = buf.getvalue()
    assert rc == 0
    data = json.loads(out)
    assert data['reference'].startswith('file://')
    entries = data['entries']
    assert len(entries) == 2
    assert any(entry['checksum_same'] is True for entry in entries)
    assert any(entry['checksum_same'] is False for entry in entries)


def test_db_info_incompatible_db_requires_override(monkeypatch, tmp_path, singleton_client):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)

    def _cfg():
        return {
            'mongo': {
                'uri': 'mongodb://localhost:27027/',
                'space_database': 'wks_similarity',
                'space_collection': 'file_embeddings',
            }
        }

    monkeypatch.setattr('wks.cli.load_config', _cfg)
    client = singleton_client
    client['wks_similarity']['_wks_meta'].insert_one({'_id': 'space', 'compat_tag': 'legacy-space'})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display', 'plain', 'db', 'info', '--space'])
    assert rc == 2
    assert "Incompatible space database" in buf.getvalue()


def test_db_info_respects_compat_override(monkeypatch, tmp_path, singleton_client):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)

    def _cfg():
        return {
            'mongo': {
                'uri': 'mongodb://localhost:27027/',
                'space_database': 'wks_similarity',
                'space_collection': 'file_embeddings',
                'compatibility': {'space': 'legacy-space'},
            }
        }

    monkeypatch.setattr('wks.cli.load_config', _cfg)
    client = singleton_client
    client['wks_similarity']['_wks_meta'].insert_one({'_id': 'space', 'compat_tag': 'legacy-space'})
    coll = client['wks_similarity']['file_embeddings']
    coll.insert_one({'path': 'file:///tmp/a.txt', 'timestamp': '2025-11-03T00:00:00Z'})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display', 'json', 'db', 'info', '--space'])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data.get('tracked_files') == 1 or data.get('total_docs') == 1
