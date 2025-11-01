import os
from pathlib import Path

import mongomock
import pytest


def dummy_encode(text: str):
    # Deterministic small vector based on text content
    import hashlib
    h = hashlib.sha256(text.encode('utf-8')).digest()
    # 8 floats in [0,1)
    return [b/255.0 for b in h[:8]]


@pytest.fixture(autouse=True)
def patch_mongo_and_model(monkeypatch):
    # Patch MongoClient to in-memory mongomock
    monkeypatch.setattr('wks.similarity.MongoClient', mongomock.MongoClient)

    # Patch SentenceTransformer to a dummy with encode()
    class DummyModel:
        def __init__(self, *a, **k):
            pass
        def encode(self, text):
            return dummy_encode(text)

    monkeypatch.setattr('wks.similarity.SentenceTransformer', DummyModel)


@pytest.fixture()
def tmpdir(tmp_path):
    return tmp_path


def make_file(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    # Ensure enough content length for embedding path (>=10 chars)
    if len(content) < 12:
        content = content * ((12 // max(1, len(content))) + 1)
    p.write_text(content, encoding='utf-8')
    return p


def test_index_and_stats_and_move(tmpdir, monkeypatch):
    from wks.similarity import SimilarityDB

    # Build DB with builtin extractor to avoid heavy dependencies during tests
    db = SimilarityDB(
        database_name='testdb',
        collection_name='file_embeddings',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
        extract_ocr=False,
        extract_timeout_secs=5,
    )

    src = make_file(tmpdir / 'src' / 'file.txt', 'alpha')

    # Index
    updated = db.add_file(src)
    assert updated is True
    stats = db.get_stats()
    assert stats['total_files'] == 1

    # Move (daemon-like path update)
    dst = tmpdir / 'dst' / 'file.txt'
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)
    # Simulate daemon move handling
    db.rename_file(src, dst)
    stats2 = db.get_stats()
    assert stats2['total_files'] == 1  # no duplicate
    doc = db.collection.find_one({'path': dst.resolve().as_uri()})
    assert doc is not None
    assert doc['filename'] == dst.name


def test_index_time_rename_detection(tmpdir):
    from wks.similarity import SimilarityDB

    db = SimilarityDB(
        database_name='testdb2',
        collection_name='file_embeddings',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
        extract_ocr=False,
        extract_timeout_secs=5,
    )

    old = make_file(tmpdir / 'old' / 'a.txt', 'beta')
    assert db.add_file(old) is True
    # Move the file physically without calling rename_file (daemon absent in this scenario)
    new = tmpdir / 'new' / 'a.txt'
    new.parent.mkdir(parents=True, exist_ok=True)
    os.rename(old, new)
    # Now indexing the new path should detect same checksum and treat as rename (old path gone)
    assert db.add_file(new) is True
    stats = db.get_stats()
    assert stats['total_files'] == 1
    assert db.collection.find_one({'path': new.resolve().as_uri()}) is not None
    assert db.collection.find_one({'path': old.resolve().as_uri()}) is None


def test_rename_folder_updates_descendants(tmpdir):
    from wks.similarity import SimilarityDB

    db = SimilarityDB(
        database_name='testdb3',
        collection_name='file_embeddings',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
        extract_ocr=False,
        extract_timeout_secs=5,
    )

    base = tmpdir / 'dir'
    f1 = make_file(base / 'a.txt', 'one')
    f2 = make_file(base / 'sub' / 'b.txt', 'two')
    assert db.add_file(f1)
    assert db.add_file(f2)
    # Move the directory
    new_base = tmpdir / 'dir-moved'
    os.rename(base, new_base)
    # Update DB paths in-place
    updated = db.rename_folder(base, new_base)
    assert updated >= 2
    # Verify records now reference moved paths
    assert db.collection.find_one({'path': (new_base / 'a.txt').resolve().as_uri()})
    assert db.collection.find_one({'path': (new_base / 'sub' / 'b.txt').resolve().as_uri()})


def test_similarity_audit_removes_missing_file(tmpdir):
    from wks.similarity import SimilarityDB

    db = SimilarityDB(
        database_name='audit_remove',
        collection_name='audit_remove_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    missing = (tmpdir / 'missing.txt').resolve()
    db.collection.insert_one({
        'path': f"file://{missing.as_posix()}",
        'path_local': str(missing),
        'bytes': None,
    })

    summary = db.audit_documents()
    assert summary['removed'] == 1
    assert db.collection.count_documents({}) == 0


def test_similarity_audit_fills_missing_bytes(tmpdir):
    from wks.similarity import SimilarityDB

    db = SimilarityDB(
        database_name='audit_fix',
        collection_name='audit_fix_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    file_path = (tmpdir / 'existing.txt').resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('hello index audit', encoding='utf-8')

    db.collection.insert_one({
        'path': f"file://{file_path.as_posix()}",
        'path_local': str(file_path),
        'bytes': None,
    })

    summary = db.audit_documents()
    doc = db.collection.find_one({'path_local': str(file_path)})
    assert summary['updated'] >= 1
    assert doc['bytes'] == file_path.stat().st_size


def test_similarity_audit_handles_plain_paths(tmpdir):
    from wks.similarity import SimilarityDB

    db = SimilarityDB(
        database_name='audit_fix_plain',
        collection_name='audit_fix_plain_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    file_path = (tmpdir / 'plain_path.txt').resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text('plain path bytes', encoding='utf-8')

    db.collection.insert_one({
        'path': str(file_path),  # stored without file:// prefix
        'bytes': None,
    })

    summary = db.audit_documents()
    assert summary['updated'] >= 1
    updated_doc = db.collection.find_one({'path_local': str(file_path)})
    assert updated_doc['bytes'] == file_path.stat().st_size
    # path should now be normalized to file URI
    assert updated_doc['path'].startswith('file://')
