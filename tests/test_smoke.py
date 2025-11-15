"""
Smoke tests matching AGENTS.md requirements.

These tests verify core Space DB operations as specified in the
"Required Smoke Tests (Space DB)" section of AGENTS.md.
"""

import os
from pathlib import Path

import mongomock
import pytest


@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    """Patch MongoClient to use in-memory mongomock."""
    monkeypatch.setattr('wks.similarity.MongoClient', mongomock.MongoClient)


@pytest.fixture
def patch_model(monkeypatch):
    """Patch SentenceTransformer with dummy model."""
    class DummyModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, text, **kwargs):
            import hashlib
            h = hashlib.sha256(text.encode('utf-8')).digest()
            return [b / 255.0 for b in h[:8]]

    monkeypatch.setattr('wks.similarity.SentenceTransformer', DummyModel)


def test_smoke_index_new_file(tmp_path, patch_model):
    """
    Index new file → wks0 db info -n 5 shows it.

    AGENTS.md requirement:
    "Index new file: `wks0 --display rich index ~/test/file.txt` →
    `wks0 --display rich db info -n 5` shows it."
    """
    from wks.similarity import SimilarityDB

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test document for indexing." * 10)

    # Build DB and index file
    db = SimilarityDB(
        database_name='smoke_test_db',
        collection_name='smoke_test_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    # Index the file
    success = db.add_file(test_file)
    assert success is True

    # Verify it appears in stats
    stats = db.get_stats()
    assert stats['total_files'] == 1

    # Verify it's in the collection
    doc = db.collection.find_one({'path': test_file.resolve().as_uri()})
    assert doc is not None
    assert doc['filename'] == 'test.txt'


def test_smoke_reindex_unchanged_skipped(tmp_path, patch_model):
    """
    Re-index unchanged file: reports skipped; totals stable.

    AGENTS.md requirement:
    "Re‑index unchanged file: reports skipped; totals stable."
    """
    from wks.similarity import SimilarityDB

    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Unchanged content for reindex test." * 10)

    # Build DB
    db = SimilarityDB(
        database_name='smoke_reindex_db',
        collection_name='smoke_reindex_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    # First index
    success = db.add_file(test_file)
    assert success is True

    stats_before = db.get_stats()
    assert stats_before['total_files'] == 1

    # Re-index without changes
    success_reindex = db.add_file(test_file)
    assert success_reindex is False  # Should report unchanged

    # Verify totals remain stable
    stats_after = db.get_stats()
    assert stats_after['total_files'] == 1
    assert stats_after['total_files'] == stats_before['total_files']


def test_smoke_file_move_daemon_running(tmp_path, patch_model):
    """
    File move (daemon running): move file → totals unchanged;
    single logical entry remains (path updated in place).

    AGENTS.md requirement:
    "File move (daemon running): move file → totals unchanged;
    single logical entry remains (path updated in place)."
    """
    from wks.similarity import SimilarityDB

    # Create test file
    src = tmp_path / 'src' / 'file.txt'
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("Content for move test." * 10)

    # Build DB
    db = SimilarityDB(
        database_name='smoke_move_db',
        collection_name='smoke_move_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    # Index original file
    db.add_file(src)
    stats_before = db.get_stats()
    assert stats_before['total_files'] == 1

    # Move file physically
    dst = tmp_path / 'dst' / 'file.txt'
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)

    # Simulate daemon move handling
    db.rename_file(src, dst)

    # Verify totals unchanged
    stats_after = db.get_stats()
    assert stats_after['total_files'] == 1

    # Verify path updated in place (no duplicate)
    old_doc = db.collection.find_one({'path': src.resolve().as_uri()})
    assert old_doc is None

    new_doc = db.collection.find_one({'path': dst.resolve().as_uri()})
    assert new_doc is not None
    assert new_doc['filename'] == 'file.txt'


def test_smoke_directory_move_daemon_running(tmp_path, patch_model):
    """
    Directory move (daemon running): move folder with files →
    totals unchanged; descendants updated in place.

    AGENTS.md requirement:
    "Directory move (daemon running): move folder with files →
    totals unchanged; descendants updated in place."
    """
    from wks.similarity import SimilarityDB

    # Create test directory with files
    base = tmp_path / 'dir'
    base.mkdir(parents=True, exist_ok=True)

    file1 = base / 'a.txt'
    file2 = base / 'sub' / 'b.txt'

    file1.write_text("File one content." * 10)
    file2.parent.mkdir(parents=True, exist_ok=True)
    file2.write_text("File two content." * 10)

    # Build DB
    db = SimilarityDB(
        database_name='smoke_dirmove_db',
        collection_name='smoke_dirmove_coll',
        mongo_uri='mongodb://localhost:27017/',
        model_name='dummy',
        extract_engine='builtin',
    )

    # Index files
    db.add_file(file1)
    db.add_file(file2)

    stats_before = db.get_stats()
    assert stats_before['total_files'] == 2

    # Move directory physically
    new_base = tmp_path / 'dir-moved'
    os.rename(base, new_base)

    # Simulate daemon directory move handling
    updated = db.rename_folder(base, new_base)
    assert updated == 2

    # Verify totals unchanged
    stats_after = db.get_stats()
    assert stats_after['total_files'] == 2

    # Verify descendants updated in place
    new_file1 = new_base / 'a.txt'
    new_file2 = new_base / 'sub' / 'b.txt'

    doc1 = db.collection.find_one({'path': new_file1.resolve().as_uri()})
    doc2 = db.collection.find_one({'path': new_file2.resolve().as_uri()})

    assert doc1 is not None
    assert doc2 is not None

    # Verify old paths gone
    old_doc1 = db.collection.find_one({'path': file1.resolve().as_uri()})
    old_doc2 = db.collection.find_one({'path': file2.resolve().as_uri()})

    assert old_doc1 is None
    assert old_doc2 is None
