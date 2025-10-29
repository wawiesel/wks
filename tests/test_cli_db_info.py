import io
from contextlib import redirect_stdout

import mongomock
import pytest


@pytest.fixture()
def singleton_client():
    # One shared in-memory client for the test
    return mongomock.MongoClient()


def test_db_info_basic_lists_tracked_and_latest(monkeypatch, singleton_client):
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
        {'path': '/tmp/x.txt', 'timestamp': '2025-10-28T10:00:00.000000'},
        {'path': '/tmp/y.txt', 'timestamp': '2025-10-28T11:00:00.000000'},
    ])

    # Ensure the CLI uses the same singleton client
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)

    # Run CLI
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','basic','db','info','-n','2','--space'])
    out = buf.getvalue()
    assert rc == 0
    assert 'tracked files:' in out
    assert '2025-10-28 11:00:00' in out or '2025-10-28 10:00:00' in out
    assert '/tmp/x.txt' in out or '/tmp/y.txt' in out
    assert 'checksum=' in out
    assert 'chunks=' in out


def test_db_info_uses_top_level_mongo(monkeypatch, singleton_client):
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
    coll.insert_one({'path': '/tmp/z.txt', 'timestamp': '2025-10-28T12:00:00.000000'})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','basic','db','info','--space'])
    assert rc == 0
    output = buf.getvalue()
    assert '/tmp/z.txt' in output
    assert 'checksum=' in output


def test_db_info_respects_timestamp_format(monkeypatch, singleton_client):
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
    coll.insert_one({'path': '/tmp/f.txt', 'timestamp': '2025-10-28T08:15:00.000000', 'content_hash': 'abc', 'num_chunks': 1})
    monkeypatch.setattr('pymongo.MongoClient', lambda *a, **k: client)
    from wks.cli import main
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(['--display','basic','db','info','--space'])
    assert rc == 0
    output = buf.getvalue()
    assert '10/28/2025 08:15' in output
