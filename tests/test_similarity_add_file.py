"""Tests for refactored SimilarityDB.add_file() and helper methods."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from wks.similarity import SimilarityDB
from wks.extractor import ExtractResult


class TestValidateFilePath:
    """Test _validate_file_path() method."""

    def test_valid_file(self, tmp_path):
        """Valid file returns None."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        result = SimilarityDB._validate_file_path(db, test_file)
        assert result is None

    def test_missing_file(self, tmp_path):
        """Missing file returns error dict."""
        missing = tmp_path / "missing.txt"

        db = Mock(spec=SimilarityDB)
        result = SimilarityDB._validate_file_path(db, missing)

        assert result is not None
        assert result["updated"] is False
        assert result["error"] == "missing"
        assert "path_local" in result

    def test_directory_not_file(self, tmp_path):
        """Directory (not file) returns error dict."""
        db = Mock(spec=SimilarityDB)
        result = SimilarityDB._validate_file_path(db, tmp_path)

        assert result is not None
        assert result["updated"] is False
        assert result["error"] == "missing"


class TestComputeChecksum:
    """Test _compute_checksum() method."""

    def test_checksum_provided(self, tmp_path):
        """When checksum provided, return it without computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        checksum, size, elapsed = SimilarityDB._compute_checksum(
            db, test_file, "abc123", 100
        )

        assert checksum == "abc123"
        assert size == 100
        assert elapsed == 0.0

    def test_checksum_computed(self, tmp_path):
        """When checksum not provided, compute it."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        db._file_digest = Mock(return_value=("computed_hash", 7))

        checksum, size, elapsed = SimilarityDB._compute_checksum(
            db, test_file, None, None
        )

        assert checksum == "computed_hash"
        assert size == 7
        assert elapsed > 0  # Should have measured time
        db._file_digest.assert_called_once_with(test_file)


class TestFindExistingDocument:
    """Test _find_existing_document() method."""

    def test_find_by_uri(self):
        """Find existing document by URI."""
        db = Mock(spec=SimilarityDB)
        existing_doc = {"_id": "123", "path": "file:///test.txt"}
        db.collection = Mock()
        db.collection.find_one = Mock(return_value=existing_doc)

        doc, rename_uri = SimilarityDB._find_existing_document(
            db, "file:///test.txt", "/test.txt", "hash123"
        )

        assert doc == existing_doc
        assert rename_uri is None
        db.collection.find_one.assert_called_once_with({"path": "file:///test.txt"})

    def test_find_by_local_path(self):
        """Find existing document by local path."""
        db = Mock(spec=SimilarityDB)
        existing_doc = {"_id": "123", "path_local": "/test.txt"}
        db.collection = Mock()
        # First call returns None (URI), second returns doc (local path)
        db.collection.find_one = Mock(side_effect=[None, existing_doc])

        doc, rename_uri = SimilarityDB._find_existing_document(
            db, "file:///test.txt", "/test.txt", "hash123"
        )

        assert doc == existing_doc
        assert rename_uri is None

    def test_find_by_checksum_rename(self):
        """Find document by checksum (rename detection)."""
        db = Mock(spec=SimilarityDB)
        renamed_doc = {"_id": "123", "path": "file:///old.txt", "checksum": "hash123"}
        db.collection = Mock()
        # First two calls return None, third returns renamed doc
        db.collection.find_one = Mock(side_effect=[None, None, renamed_doc])

        doc, rename_uri = SimilarityDB._find_existing_document(
            db, "file:///new.txt", "/new.txt", "hash123"
        )

        assert doc == renamed_doc
        assert rename_uri == "file:///old.txt"

    def test_not_found(self):
        """No existing document found."""
        db = Mock(spec=SimilarityDB)
        db.collection = Mock()
        db.collection.find_one = Mock(return_value=None)

        doc, rename_uri = SimilarityDB._find_existing_document(
            db, "file:///test.txt", "/test.txt", "hash123"
        )

        assert doc is None
        assert rename_uri is None


class TestShouldSkipUnchanged:
    """Test _should_skip_unchanged() method."""

    def test_no_existing_document(self):
        """No existing document, don't skip."""
        db = Mock(spec=SimilarityDB)
        result = SimilarityDB._should_skip_unchanged(
            db, None, "hash123", None, False
        )
        assert result is None

    def test_force_flag_set(self):
        """Force flag set, don't skip."""
        db = Mock(spec=SimilarityDB)
        existing = {"path": "file:///test.txt", "checksum": "hash123"}
        result = SimilarityDB._should_skip_unchanged(
            db, existing, "hash123", None, True
        )
        assert result is None

    def test_rename_detected(self):
        """Rename detected, don't skip."""
        db = Mock(spec=SimilarityDB)
        existing = {"path": "file:///new.txt", "checksum": "hash123"}
        # rename_from_uri different from existing path indicates rename
        result = SimilarityDB._should_skip_unchanged(
            db, existing, "hash123", "file:///old.txt", False
        )
        assert result is None

    def test_unchanged_file_skip(self):
        """Unchanged file, should skip."""
        db = Mock(spec=SimilarityDB)
        existing = {
            "path": "file:///test.txt",
            "path_local": "/test.txt",
            "checksum": "hash123",
            "content_checksum": "content_hash",
        }
        result = SimilarityDB._should_skip_unchanged(
            db, existing, "hash123", None, False
        )

        assert result is not None
        assert result["updated"] is False
        assert result["checksum"] == "hash123"
        assert result["content_checksum"] == "content_hash"

    def test_checksum_changed(self):
        """Checksum changed, don't skip."""
        db = Mock(spec=SimilarityDB)
        existing = {"path": "file:///test.txt", "checksum": "old_hash"}
        result = SimilarityDB._should_skip_unchanged(
            db, existing, "new_hash", None, False
        )
        assert result is None


class TestExtractContent:
    """Test _extract_content() method."""

    def test_extraction_provided(self, tmp_path):
        """Pre-computed extraction provided."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        db.min_chars = 10  # Add required attribute
        extraction = Mock(spec=ExtractResult)
        extraction.text = "extracted text"

        result, error = SimilarityDB._extract_content(
            db, test_file, "file:///test.txt", "/test.txt", extraction, False
        )

        assert result == extraction
        assert error is None

    def test_extraction_computed(self, tmp_path):
        """Extraction computed from file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        extraction = Mock(spec=ExtractResult)
        extraction.text = "extracted text"
        db.extractor = Mock()
        db.extractor.extract = Mock(return_value=extraction)
        db.min_chars = 10

        result, error = SimilarityDB._extract_content(
            db, test_file, "file:///test.txt", "/test.txt", None, False
        )

        assert result == extraction
        assert error is None
        db.extractor.extract.assert_called_once_with(test_file, persist=True)

    def test_extraction_fails(self, tmp_path):
        """Extraction fails with exception."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        db.extractor = Mock()
        db.extractor.extract = Mock(side_effect=Exception("Extraction failed"))

        result, error = SimilarityDB._extract_content(
            db, test_file, "file:///test.txt", "/test.txt", None, False
        )

        assert result is None
        assert error is not None
        assert error["updated"] is False
        assert "Extraction failed" in error["error"]

    def test_text_too_short(self, tmp_path):
        """Text too short, return skip error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("ab")

        db = Mock(spec=SimilarityDB)
        extraction = Mock(spec=ExtractResult)
        extraction.text = "ab"
        db.min_chars = 10

        result, error = SimilarityDB._extract_content(
            db, test_file, "file:///test.txt", "/test.txt", extraction, False
        )

        assert result is None
        assert error is not None
        assert error["skipped"] == "min_chars"

    def test_text_too_short_force(self, tmp_path):
        """Text too short but force=True."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("ab")

        db = Mock(spec=SimilarityDB)
        extraction = Mock(spec=ExtractResult)
        extraction.text = "ab"
        db.min_chars = 10

        result, error = SimilarityDB._extract_content(
            db, test_file, "file:///test.txt", "/test.txt", extraction, True
        )

        assert result == extraction
        assert error is None


class TestBuildDocument:
    """Test _build_document() method."""

    def test_build_document(self, tmp_path):
        """Build document from inputs."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        db.model_name = "test-model"
        db.chunk_chars = 1500
        db.chunk_overlap = 200
        db.angle_from_empty = Mock(return_value=45.0)

        extraction = Mock(spec=ExtractResult)
        extraction.text = "extracted text"
        extraction.content_path = Path("/tmp/extract.md")
        extraction.content_checksum = "content_hash"
        extraction.content_bytes = 100

        embedding = [0.1, 0.2, 0.3]
        chunk_docs = [{"chunk": 1}, {"chunk": 2}]

        doc = SimilarityDB._build_document(
            db, test_file, "file:///test.txt", "/test.txt", "file_hash",
            7, extraction, embedding, chunk_docs, "2025-11-22T00:00:00Z"
        )

        assert doc["path"] == "file:///test.txt"
        assert doc["path_local"] == "/test.txt"
        assert doc["filename"] == "test.txt"
        assert doc["checksum"] == "file_hash"
        assert doc["bytes"] == 7
        assert doc["content_checksum"] == "content_hash"
        assert doc["embedding"] == embedding
        assert doc["angle"] == 45.0
        assert doc["num_chunks"] == 2
        assert "extracted text" in doc["text_preview"]


class TestUpsertDocumentAndChunks:
    """Test _upsert_document_and_chunks() method."""

    def test_upsert_new_document(self):
        """Upsert new document (no existing)."""
        db = Mock(spec=SimilarityDB)
        db.collection = Mock()
        db.collection.update_one = Mock()
        db.chunks = Mock()
        db.chunks.delete_many = Mock()
        db.chunks.insert_many = Mock()

        doc_payload = {"path": "file:///test.txt", "checksum": "hash"}
        chunk_docs = [{"chunk": 1}]

        db_time, chunks_time = SimilarityDB._upsert_document_and_chunks(
            db, "file:///test.txt", doc_payload, chunk_docs, None
        )

        db.collection.update_one.assert_called_once_with(
            {"path": "file:///test.txt"},
            {"$set": doc_payload},
            upsert=True
        )
        db.chunks.delete_many.assert_called_once()
        db.chunks.insert_many.assert_called_once_with(chunk_docs, ordered=False)
        assert db_time > 0
        assert chunks_time > 0

    def test_upsert_existing_document(self):
        """Upsert existing document with _id."""
        db = Mock(spec=SimilarityDB)
        db.collection = Mock()
        db.collection.update_one = Mock()
        db.chunks = Mock()
        db.chunks.delete_many = Mock()
        db.chunks.insert_many = Mock()

        existing = {"_id": "doc_id_123"}
        doc_payload = {"path": "file:///test.txt", "checksum": "hash"}
        chunk_docs = []

        db_time, chunks_time = SimilarityDB._upsert_document_and_chunks(
            db, "file:///test.txt", doc_payload, chunk_docs, existing
        )

        db.collection.update_one.assert_called_once_with(
            {"_id": "doc_id_123"},
            {"$set": doc_payload},
            upsert=True
        )
        assert db_time > 0


class TestRecordEmbeddingChange:
    """Test _record_embedding_change() method."""

    def test_no_previous_embedding(self):
        """No previous embedding, nothing recorded."""
        db = Mock(spec=SimilarityDB)
        db.changes = Mock()

        SimilarityDB._record_embedding_change(
            db, "file:///test.txt", None, None, [0.1, 0.2], "2025-11-22T00:00:00Z"
        )

        db.changes.insert_one.assert_not_called()

    def test_record_change(self):
        """Record embedding change with drift calculation."""
        db = Mock(spec=SimilarityDB)
        db.changes = Mock()
        db.changes.insert_one = Mock()

        prev_embedding = [1.0, 0.0, 0.0]
        new_embedding = [0.0, 1.0, 0.0]

        SimilarityDB._record_embedding_change(
            db, "file:///test.txt", prev_embedding, "2025-11-22T00:00:00Z",
            new_embedding, "2025-11-22T01:00:00Z"
        )

        db.changes.insert_one.assert_called_once()
        call_args = db.changes.insert_one.call_args[0][0]
        assert call_args["file_path"] == "file:///test.txt"
        assert "degrees" in call_args
        assert "seconds" in call_args


class TestAddFileIntegration:
    """Integration tests for full add_file() workflow."""

    def test_add_new_file_success(self, tmp_path):
        """Successfully add new file to index."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is test content for indexing")

        db = Mock(spec=SimilarityDB)
        db.min_chars = 10
        db.model_name = "test-model"
        db.chunk_chars = 1500
        db.chunk_overlap = 200
        db.collection = Mock()
        db.collection.find_one = Mock(return_value=None)
        db.collection.update_one = Mock()
        db.chunks = Mock()
        db.chunks.delete_many = Mock()
        db.chunks.insert_many = Mock()
        db.changes = Mock()

        extraction = Mock(spec=ExtractResult)
        extraction.text = "This is test content for indexing"
        extraction.content_path = Path("/tmp/test.md")
        extraction.content_checksum = "content_hash"
        extraction.content_bytes = 100

        db.extractor = Mock()
        db.extractor.extract = Mock(return_value=extraction)
        db._embed_text = Mock(return_value=([0.1, 0.2, 0.3], []))
        db.angle_from_empty = Mock(return_value=45.0)
        db._file_digest = Mock(return_value=("file_hash", 33))

        # Bind methods to instance
        db._validate_file_path = lambda path: SimilarityDB._validate_file_path(db, path)
        db._compute_checksum = lambda path, fh, fb: SimilarityDB._compute_checksum(db, path, fh, fb)
        db._find_existing_document = lambda fu, pl, fc: SimilarityDB._find_existing_document(db, fu, pl, fc)
        db._should_skip_unchanged = lambda e, fc, r, f: SimilarityDB._should_skip_unchanged(db, e, fc, r, f)
        db._extract_content = lambda p, fu, pl, ex, f: SimilarityDB._extract_content(db, p, fu, pl, ex, f)
        db._build_document = lambda *args: SimilarityDB._build_document(db, *args)
        db._upsert_document_and_chunks = lambda *args: SimilarityDB._upsert_document_and_chunks(db, *args)
        db._record_embedding_change = lambda *args: SimilarityDB._record_embedding_change(db, *args)

        result = SimilarityDB.add_file(db, test_file)

        assert result is True
        db.collection.update_one.assert_called_once()

    def test_skip_unchanged_file(self, tmp_path):
        """Skip file with unchanged checksum."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        db = Mock(spec=SimilarityDB)
        db.collection = Mock()
        existing = {
            "path": "file:///test.txt",
            "path_local": str(test_file),
            "checksum": "same_hash",
            "content_checksum": "content_hash",
        }
        db.collection.find_one = Mock(return_value=existing)
        db._file_digest = Mock(return_value=("same_hash", 7))

        db._validate_file_path = lambda path: SimilarityDB._validate_file_path(db, path)
        db._compute_checksum = lambda path, fh, fb: SimilarityDB._compute_checksum(db, path, fh, fb)
        db._find_existing_document = lambda fu, pl, fc: SimilarityDB._find_existing_document(db, fu, pl, fc)
        db._should_skip_unchanged = lambda e, fc, r, f: SimilarityDB._should_skip_unchanged(db, e, fc, r, f)

        result = SimilarityDB.add_file(db, test_file)

        assert result is False
        db.collection.update_one.assert_not_called()
