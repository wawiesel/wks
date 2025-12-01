"""Tests for Transform layer."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from wks.transform.models import TransformRecord, now_iso
from wks.transform.cache import CacheManager
from wks.transform.engines import DoclingEngine, get_engine
from wks.transform.controller import TransformController


class TestTransformRecord:
    """Test TransformRecord model."""

    def test_to_dict(self):
        """TransformRecord converts to dict."""
        record = TransformRecord(
            file_uri="file:///test.pdf",
            checksum="abc123",
            size_bytes=1024,
            last_accessed="2025-01-01T00:00:00+00:00",
            created_at="2025-01-01T00:00:00+00:00",
            engine="docling",
            options_hash="def456",
            cache_location="/cache/abc123.md"
        )

        data = record.to_dict()

        assert data["file_uri"] == "file:///test.pdf"
        assert data["checksum"] == "abc123"
        assert data["size_bytes"] == 1024
        assert data["engine"] == "docling"

    def test_from_dict(self):
        """TransformRecord creates from dict."""
        data = {
            "file_uri": "file:///test.pdf",
            "checksum": "abc123",
            "size_bytes": 1024,
            "last_accessed": "2025-01-01T00:00:00+00:00",
            "created_at": "2025-01-01T00:00:00+00:00",
            "engine": "docling",
            "options_hash": "def456",
            "cache_location": "/cache/abc123.md"
        }

        record = TransformRecord.from_dict(data)

        assert record.file_uri == "file:///test.pdf"
        assert record.checksum == "abc123"
        assert record.engine == "docling"

    def test_now_iso(self):
        """now_iso returns ISO timestamp."""
        timestamp = now_iso()
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp


class TestCacheManager:
    """Test CacheManager."""

    def test_init_creates_cache_dir(self, tmp_path):
        """CacheManager creates cache directory."""
        cache_dir = tmp_path / "cache"
        db = Mock()

        manager = CacheManager(cache_dir, 1024, db)

        assert cache_dir.exists()
        assert manager.max_size_bytes == 1024

    def test_ensure_space_no_eviction_needed(self, tmp_path):
        """No eviction when space available."""
        cache_dir = tmp_path / "cache"
        db = Mock()

        manager = CacheManager(cache_dir, 1024, db)

        # Cache is empty, adding 512 bytes doesn't exceed limit
        result = manager.ensure_space(512)

        assert result is None  # No eviction

    def test_ensure_space_with_eviction(self, tmp_path):
        """Evict LRU entries when space needed."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Set up mock database
        db = Mock()
        db.transform = Mock()

        # Mock LRU query - return oldest entries
        db.transform.find.return_value.sort.return_value = [
            {
                "checksum": "old1",
                "size_bytes": 500,
                "cache_location": str(cache_dir / "old1.md"),
                "last_accessed": "2025-01-01T00:00:00+00:00"
            },
            {
                "checksum": "old2",
                "size_bytes": 400,
                "cache_location": str(cache_dir / "old2.md"),
                "last_accessed": "2025-01-02T00:00:00+00:00"
            }
        ]

        manager = CacheManager(cache_dir, 1000, db)

        # Create cache files
        (cache_dir / "old1.md").write_text("content1")
        (cache_dir / "old2.md").write_text("content2")

        # Set current size to 900
        manager._save_cache_size(900)

        # Try to add 200 bytes (total would be 1100, exceeds 1000 limit)
        evicted = manager.ensure_space(200)

        assert evicted is not None
        assert len(evicted) >= 1  # At least one entry evicted
        assert not (cache_dir / "old1.md").exists()  # Oldest file removed

    def test_add_file(self, tmp_path):
        """Add file updates cache size."""
        cache_dir = tmp_path / "cache"
        db = Mock()

        manager = CacheManager(cache_dir, 1024, db)

        manager.add_file(512)

        assert manager.get_current_size() == 512

    def test_remove_file(self, tmp_path):
        """Remove file updates cache size."""
        cache_dir = tmp_path / "cache"
        db = Mock()

        manager = CacheManager(cache_dir, 1024, db)
        manager._save_cache_size(512)

        manager.remove_file(200)

        assert manager.get_current_size() == 312


class TestDoclingEngine:
    """Test DoclingEngine."""

    def test_get_extension_default(self):
        """DoclingEngine returns default extension."""
        engine = DoclingEngine()

        ext = engine.get_extension({})

        assert ext == "md"

    def test_get_extension_custom(self):
        """DoclingEngine returns custom extension."""
        engine = DoclingEngine()

        ext = engine.get_extension({"write_extension": "txt"})

        assert ext == "txt"

    def test_compute_options_hash(self):
        """DoclingEngine computes consistent options hash."""
        engine = DoclingEngine()

        hash1 = engine.compute_options_hash({"ocr": True, "timeout_secs": 30})
        hash2 = engine.compute_options_hash({"timeout_secs": 30, "ocr": True})

        assert hash1 == hash2  # Order doesn't matter
        assert len(hash1) == 16  # Truncated to 16 chars

    @patch("subprocess.run")
    def test_transform_success(self, mock_run, tmp_path):
        """DoclingEngine transforms successfully."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")

        output_path = tmp_path / "output.md"

        # Mock successful docling run
        mock_run.return_value = Mock(stdout="# Transformed\n\nContent", returncode=0)
        
        # The DoclingEngine creates a temp directory and expects docling to write to it.
        # We need to intercept the subprocess.run call, find the temp directory argument,
        # and create the output file there.
        
        def create_output(cmd, *args, **kwargs):
            # cmd is like ["docling", input_path, "--to", "md", "--output", temp_dir]
            # Find output dir (it's after --output)
            try:
                output_idx = cmd.index("--output")
                temp_dir = Path(cmd[output_idx + 1])
                # Create the expected output file: <input_stem>.md
                expected_file = temp_dir / f"{input_path.stem}.md"
                expected_file.write_text("# Transformed\n\nContent")
            except (ValueError, IndexError):
                pass
            return Mock(stdout="Done", returncode=0)
            
        mock_run.side_effect = create_output

        engine.transform(input_path, output_path, {"ocr": False, "timeout_secs": 30})

        assert output_path.exists()
        assert "Transformed" in output_path.read_text()
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_transform_timeout(self, mock_run, tmp_path):
        """DoclingEngine raises on timeout."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")
        output_path = tmp_path / "output.md"

        # Mock timeout
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("docling", 30)

        with pytest.raises(RuntimeError, match="timed out"):
            engine.transform(input_path, output_path, {"timeout_secs": 30})


class TestEngineRegistry:
    """Test engine registry."""

    def test_get_engine_docling(self):
        """Get docling engine."""
        engine = get_engine("docling")

        assert engine is not None
        assert isinstance(engine, DoclingEngine)

    def test_get_engine_unknown(self):
        """Get unknown engine returns None."""
        engine = get_engine("unknown")

        assert engine is None


class TestTransformController:
    """Test TransformController."""

    def test_transform_file_not_found(self, tmp_path):
        """Transform raises on missing file."""
        db = Mock()
        controller = TransformController(db, tmp_path / "cache", 1024)

        with pytest.raises(ValueError, match="File not found"):
            controller.transform(tmp_path / "missing.pdf", "docling")

    def test_transform_unknown_engine(self, tmp_path):
        """Transform raises on unknown engine."""
        db = Mock()
        controller = TransformController(db, tmp_path / "cache", 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        with pytest.raises(ValueError, match="Unknown engine"):
            controller.transform(test_file, "unknown")

    @patch("wks.transform.controller.get_engine")
    def test_transform_uses_cached(self, mock_get_engine, tmp_path):
        """Transform uses cached result if available."""
        db = Mock()
        db.transform = Mock()

        # Mock cached entry exists
        db.transform.find.return_value = [
            {
                "file_uri": "file:///test.pdf",
                "checksum": "abc123",
                "size_bytes": 1024,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
                "engine": "docling",
                "options_hash": "def456",
                "cache_location": str(tmp_path / "cache" / "key123.md"),
            }
        ]

        # Create cached file
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "key123.md").write_text("Cached content")

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        # Mock engine
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = "def456"
        mock_get_engine.return_value = mock_engine

        cache_key = controller.transform(test_file, "docling")

        assert cache_key is not None
        db.transform.update_one.assert_called_once()  # Updated last_accessed
        mock_engine.transform.assert_not_called()  # Didn't re-transform

    def test_remove_by_uri(self, tmp_path):
        """Remove all transforms for a URI."""
        db = Mock()
        db.transform = Mock()

        # Mock two entries for this URI
        db.transform.find.return_value = [
            {
                "_id": "id1",
                "file_uri": "file:///test.pdf",
                "cache_location": str(tmp_path / "cache1.md"),
                "size_bytes": 100
            },
            {
                "_id": "id2",
                "file_uri": "file:///test.pdf",
                "cache_location": str(tmp_path / "cache2.md"),
                "size_bytes": 200
            }
        ]

        # Create cache files
        (tmp_path / "cache1.md").write_text("content1")
        (tmp_path / "cache2.md").write_text("content2")

        controller = TransformController(db, tmp_path / "cache", 1024)

        count = controller.remove_by_uri("file:///test.pdf")

        assert count == 2
        assert not (tmp_path / "cache1.md").exists()
        assert not (tmp_path / "cache2.md").exists()

    def test_update_uri(self, tmp_path):
        """Update URI in transform records."""
        db = Mock()
        db.transform = Mock()
        db.transform.update_many.return_value = Mock(modified_count=3)

        controller = TransformController(db, tmp_path / "cache", 1024)

        count = controller.update_uri("file:///old.pdf", "file:///new.pdf")

        assert count == 3
        db.transform.update_many.assert_called_once_with(
            {"file_uri": "file:///old.pdf"},
            {"$set": {"file_uri": "file:///new.pdf"}}
        )
