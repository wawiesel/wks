"""Tests for Transform layer (controller, models, cache)."""

from unittest.mock import Mock, patch

import pytest

from wks.transform.cache import CacheManager
from wks.transform.controller import TransformController
from wks.transform.models import TransformRecord, now_iso


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
            cache_location="/cache/abc123.md",
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
            "cache_location": "/cache/abc123.md",
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
                "last_accessed": "2025-01-01T00:00:00+00:00",
            },
            {
                "checksum": "old2",
                "size_bytes": 400,
                "cache_location": str(cache_dir / "old2.md"),
                "last_accessed": "2025-01-02T00:00:00+00:00",
            },
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

    def test_load_cache_size_json_error(self, tmp_path):
        """Test _load_cache_size handles JSON load error."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db = Mock()

        manager = CacheManager(cache_dir, 1024, db)

        # Create invalid JSON file
        manager.cache_json.write_text("invalid json {")

        # Should return 0 on error
        size = manager._load_cache_size()
        assert size == 0

    def test_ensure_space_no_entries_to_evict(self, tmp_path):
        """Test ensure_space returns None when no entries to evict."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db = Mock()
        db.transform = Mock()

        manager = CacheManager(cache_dir, 1000, db)

        # Set current size above limit but no entries in DB
        manager._save_cache_size(1200)

        # Mock empty database result
        db.transform.find.return_value.sort.return_value = []

        # Should return None when no entries to evict
        result = manager.ensure_space(100)
        assert result is None


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

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        # Compute actual checksum and cache key
        file_checksum = controller._compute_file_checksum(test_file)
        options_hash = "def456"
        cache_key = controller._compute_cache_key(file_checksum, "docling", options_hash)

        # Mock cached entry exists with correct cache key
        db.transform.find.return_value = [
            {
                "file_uri": f"file://{test_file}",
                "checksum": file_checksum,
                "size_bytes": 1024,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
                "engine": "docling",
                "options_hash": options_hash,
                "cache_location": str(cache_dir / f"{cache_key}.md"),
            }
        ]

        # Create cached file with correct cache key
        (cache_dir / f"{cache_key}.md").write_text("Cached content")

        # Mock engine
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = options_hash
        mock_get_engine.return_value = mock_engine

        result_cache_key = controller.transform(test_file, "docling")

        assert result_cache_key == cache_key
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
                "size_bytes": 100,
            },
            {
                "_id": "id2",
                "file_uri": "file:///test.pdf",
                "cache_location": str(tmp_path / "cache2.md"),
                "size_bytes": 200,
            },
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
            {"file_uri": "file:///old.pdf"}, {"$set": {"file_uri": "file:///new.pdf"}}
        )

    @patch("wks.transform.controller.get_engine")
    def test_transform_not_cached_with_output_path(self, mock_get_engine, tmp_path):
        """Transform when not cached and output_path provided."""
        db = Mock()
        db.transform = Mock()
        db.transform.find.return_value = []  # Not cached
        db.transform.insert_one = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        output_path = tmp_path / "output.md"

        # Mock engine
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = "optshash"
        mock_engine.get_extension.return_value = "md"

        def transform_side_effect(input_path, output_path_internal, options):  # noqa: ARG001
            output_path_internal.write_text("Transformed content")

        mock_engine.transform.side_effect = transform_side_effect
        mock_get_engine.return_value = mock_engine

        cache_key = controller.transform(test_file, "test", {}, output_path)

        assert cache_key is not None
        assert output_path.exists()
        assert output_path.read_text() == "Transformed content"
        db.transform.insert_one.assert_called_once()

    @patch("wks.transform.controller.get_engine")
    def test_transform_not_cached_no_output_path(self, mock_get_engine, tmp_path):
        """Transform when not cached without output_path."""
        db = Mock()
        db.transform = Mock()
        db.transform.find.return_value = []  # Not cached
        db.transform.insert_one = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        # Mock engine
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = "optshash"
        mock_engine.get_extension.return_value = "md"

        def transform_side_effect(input_path, output_path_internal, options):  # noqa: ARG001
            output_path_internal.write_text("Transformed content")

        mock_engine.transform.side_effect = transform_side_effect
        mock_get_engine.return_value = mock_engine

        cache_key = controller.transform(test_file, "test")

        assert cache_key is not None
        db.transform.insert_one.assert_called_once()

    @patch("wks.transform.controller.get_engine")
    def test_transform_cached_with_output_path(self, mock_get_engine, tmp_path):
        """Transform uses cached result and copies to output_path."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        # Compute actual checksum and cache key
        file_checksum = controller._compute_file_checksum(test_file)
        options_hash = "def456"
        cache_key = controller._compute_cache_key(file_checksum, "test", options_hash)

        cache_file = cache_dir / f"{cache_key}.md"
        cache_file.write_text("Cached content")

        # Mock cached entry with correct cache key
        db.transform.find.return_value = [
            {
                "file_uri": f"file://{test_file}",
                "checksum": file_checksum,
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
                "engine": "test",
                "options_hash": options_hash,
                "cache_location": str(cache_file),
            }
        ]

        output_path = tmp_path / "output.md"

        # Mock engine
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = options_hash
        mock_get_engine.return_value = mock_engine

        result_cache_key = controller.transform(test_file, "test", {}, output_path)

        assert result_cache_key == cache_key
        assert output_path.exists()
        assert output_path.read_text() == "Cached content"
        mock_engine.transform.assert_not_called()  # Used cache

    def test_get_content_with_checksum_found_in_cache_dir(self, tmp_path):
        """get_content finds checksum file directly in cache directory."""
        db = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("Cached content")

        controller = TransformController(db, cache_dir, 1024)

        content = controller.get_content(checksum)

        assert content == "Cached content"

    def test_get_content_with_checksum_with_output_path(self, tmp_path):
        """get_content with checksum and output_path creates hard link or copies."""
        db = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("Cached content")

        controller = TransformController(db, cache_dir, 1024)

        output_path = tmp_path / "output.md"

        content = controller.get_content(checksum, output_path)

        assert content == "Cached content"
        assert output_path.exists()
        assert output_path.read_text() == "Cached content"

    def test_get_content_with_checksum_not_found(self, tmp_path):
        """get_content raises when checksum not found."""
        db = Mock()
        db.transform = Mock()
        db.transform.find.return_value = []  # No matching records

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        checksum = "a" * 64

        with pytest.raises(ValueError, match="Cache entry not found"):
            controller.get_content(checksum)

    def test_get_content_with_checksum_from_db_metadata(self, tmp_path):
        """get_content resolves checksum via database metadata."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("Cached content")

        # Mock database record that matches the checksum
        db.transform.find.return_value = [
            {
                "checksum": "file_checksum",
                "engine": "test",
                "options_hash": "opts_hash",
                "cache_location": str(cache_file),
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        # Mock the _compute_cache_key to return our checksum
        with patch.object(controller, "_compute_cache_key", return_value=checksum):
            content = controller.get_content(checksum)

            assert content == "Cached content"

    def test_get_content_with_checksum_output_path_exists_overwrites(self, tmp_path):
        """get_content overwrites existing output_path (FileExistsError is caught)."""
        db = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("Cached content")

        controller = TransformController(db, cache_dir, 1024)

        output_path = tmp_path / "output.md"
        output_path.write_text("existing")

        # FileExistsError is caught and file is copied instead
        content = controller.get_content(checksum, output_path)

        assert content == "Cached content"
        assert output_path.read_text() == "Cached content"

    def test_get_content_with_file_path_transforms(self, tmp_path):
        """get_content with file path transforms and returns content."""
        db = Mock()
        db.transform = Mock()
        db.transform.find.return_value = []  # Not cached
        db.transform.insert_one = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024, default_engine="test")

        test_file = tmp_path / "test.txt"
        test_file.write_text("Original content")

        with patch("wks.transform.controller.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_engine.compute_options_hash.return_value = "optshash"
            mock_engine.get_extension.return_value = "md"

            def transform_side_effect(input_path, output_path_internal, options):  # noqa: ARG001
                output_path_internal.write_text("Transformed: Original content")

            mock_engine.transform.side_effect = transform_side_effect
            mock_get_engine.return_value = mock_engine

            content = controller.get_content(str(test_file))

            assert "Transformed: Original content" in content
            db.transform.insert_one.assert_called_once()

    def test_get_content_with_file_path_not_found(self, tmp_path):
        """get_content raises when file path doesn't exist."""
        db = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024)

        with pytest.raises(ValueError, match="File not found"):
            controller.get_content(str(tmp_path / "nonexistent.txt"))

    def test_get_content_with_checksum_glob_fallback(self, tmp_path):
        """get_content uses glob to find file when extension differs."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        # Create file with different extension
        cache_file = cache_dir / f"{checksum}.txt"
        cache_file.write_text("Cached content")

        # Mock database record
        db.transform.find.return_value = [
            {
                "checksum": "file_checksum",
                "engine": "test",
                "options_hash": "opts_hash",
                "cache_location": str(cache_file),
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        with patch.object(controller, "_compute_cache_key", return_value=checksum):
            content = controller.get_content(checksum)

            assert content == "Cached content"

    @patch("wks.transform.controller.get_engine")
    def test_transform_cached_cache_path_not_exists(self, mock_get_engine, tmp_path):
        """Transform handles cached entry where cache file doesn't exist."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Mock cached entry but file doesn't exist
        db.transform.find.return_value = [
            {
                "file_uri": f"file://{tmp_path / 'test.pdf'}",
                "checksum": "abc123",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
                "engine": "test",
                "options_hash": "def456",
                "cache_location": str(cache_dir / "nonexistent.md"),
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        # Mock engine - should transform since cache file missing
        mock_engine = Mock()
        mock_engine.compute_options_hash.return_value = "def456"
        mock_engine.get_extension.return_value = "md"

        def transform_side_effect(input_path, output_path_internal, options):  # noqa: ARG001
            output_path_internal.write_text("Transformed content")

        mock_engine.transform.side_effect = transform_side_effect
        mock_get_engine.return_value = mock_engine

        # Should still work - will transform since cache file missing
        db.transform.find.return_value = []  # Treat as not cached
        db.transform.insert_one = Mock()

        cache_key = controller.transform(test_file, "test")

        assert cache_key is not None

    def test_find_cached_transform_not_found_returns_none(self, tmp_path):
        """_find_cached_transform returns None when cache file doesn't exist."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Mock database entry but cache file doesn't exist
        db.transform.find.return_value = [
            {
                "file_uri": "file:///test.pdf",
                "checksum": "abc123",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
                "engine": "test",
                "options_hash": "def456",
                "cache_location": str(cache_dir / "nonexistent.md"),
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        result = controller._find_cached_transform("abc123", "test", "def456")

        assert result is None

    def test_get_content_with_file_path_expand_path_fails(self, tmp_path):
        """get_content falls back to Path.resolve when expand_path fails."""
        db = Mock()
        db.transform = Mock()
        db.transform.find.return_value = []
        db.transform.insert_one = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        controller = TransformController(db, cache_dir, 1024, default_engine="test")

        test_file = tmp_path / "test.txt"
        test_file.write_text("Original content")

        with patch("wks.utils.expand_path") as mock_expand:
            mock_expand.side_effect = Exception("expand failed")

            with patch("wks.transform.controller.get_engine") as mock_get_engine:
                mock_engine = Mock()
                mock_engine.compute_options_hash.return_value = "optshash"
                mock_engine.get_extension.return_value = "md"

                def transform_side_effect(input_path, output_path_internal, options):  # noqa: ARG001
                    output_path_internal.write_text("Transformed: Original content")

                mock_engine.transform.side_effect = transform_side_effect
                mock_get_engine.return_value = mock_engine

                content = controller.get_content(str(test_file))

                assert "Transformed: Original content" in content

    def test_get_content_with_checksum_db_resolution_extension_default(self, tmp_path):
        """get_content uses default .md extension when stored path has no extension."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("Cached content")

        # Mock database record with no extension in cache_location
        db.transform.find.return_value = [
            {
                "checksum": "file_checksum",
                "engine": "test",
                "options_hash": "opts_hash",
                "cache_location": "/some/path/with/no/extension",
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        with (
            patch.object(controller, "_compute_cache_key", return_value=checksum),
            patch.object(controller, "_update_last_accessed"),
        ):
            content = controller.get_content(checksum)

        assert content == "Cached content"

    def test_get_content_with_checksum_db_resolution_finds_matching_record(self, tmp_path):
        """get_content finds matching record in database by computing cache key."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.txt"
        cache_file.write_text("Cached content from DB")

        # Mock database record - need to match the computed cache key
        file_checksum = "file_checksum_123"
        engine = "test"
        options_hash = "opts_hash_456"

        # Compute what the cache key should be
        controller = TransformController(db, cache_dir, 1024)
        expected_cache_key = controller._compute_cache_key(file_checksum, engine, options_hash)

        # Use the computed key as the checksum
        cache_file_with_key = cache_dir / f"{expected_cache_key}.txt"
        cache_file_with_key.write_text("Cached content from DB")

        db.transform.find.return_value = [
            {
                "checksum": file_checksum,
                "engine": engine,
                "options_hash": options_hash,
                "cache_location": str(cache_file_with_key),
                "file_uri": "file:///test.pdf",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]

        with patch.object(controller, "_update_last_accessed"):
            content = controller.get_content(expected_cache_key)

            assert content == "Cached content from DB"

    def test_get_content_with_checksum_db_resolution_glob_fallback(self, tmp_path):
        """get_content uses glob when reconstructed path doesn't exist."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_checksum = "file_checksum_123"
        engine = "test"
        options_hash = "opts_hash_456"

        controller = TransformController(db, cache_dir, 1024)
        expected_cache_key = controller._compute_cache_key(file_checksum, engine, options_hash)

        # Create file with .md extension (different from stored .txt)
        cache_file = cache_dir / f"{expected_cache_key}.md"
        cache_file.write_text("Cached content")

        # Store path with .txt extension but file is .md
        db.transform.find.return_value = [
            {
                "checksum": file_checksum,
                "engine": engine,
                "options_hash": options_hash,
                "cache_location": f"/some/path/{expected_cache_key}.txt",  # Different extension
                "file_uri": "file:///test.pdf",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]

        with patch.object(controller, "_update_last_accessed"):
            content = controller.get_content(expected_cache_key)

            assert content == "Cached content"

    def test_get_content_with_checksum_db_resolution_output_path(self, tmp_path):
        """get_content handles output_path when resolving via database."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_checksum = "file_checksum_123"
        engine = "test"
        options_hash = "opts_hash_456"

        controller = TransformController(db, cache_dir, 1024)
        expected_cache_key = controller._compute_cache_key(file_checksum, engine, options_hash)

        cache_file = cache_dir / f"{expected_cache_key}.md"
        cache_file.write_text("Cached content")

        output_path = tmp_path / "output" / "result.md"

        db.transform.find.return_value = [
            {
                "checksum": file_checksum,
                "engine": engine,
                "options_hash": options_hash,
                "cache_location": str(cache_file),
                "file_uri": "file:///test.pdf",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]

        with patch.object(controller, "_update_last_accessed"):
            content = controller.get_content(expected_cache_key, output_path=output_path)

            assert content == "Cached content"
            assert output_path.exists()
            assert output_path.read_text() == "Cached content"

    def test_get_content_with_checksum_db_resolution_output_path_exists_overwrites(self, tmp_path):
        """get_content overwrites output_path when it exists (FileExistsError is caught)."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_checksum = "file_checksum_123"
        engine = "test"
        options_hash = "opts_hash_456"

        controller = TransformController(db, cache_dir, 1024)
        expected_cache_key = controller._compute_cache_key(file_checksum, engine, options_hash)

        cache_file = cache_dir / f"{expected_cache_key}.md"
        cache_file.write_text("Cached content")

        output_path = tmp_path / "output.md"
        output_path.write_text("Existing content")

        db.transform.find.return_value = [
            {
                "checksum": file_checksum,
                "engine": engine,
                "options_hash": options_hash,
                "cache_location": str(cache_file),
                "file_uri": "file:///test.pdf",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]

        with patch.object(controller, "_update_last_accessed"):
            # FileExistsError is raised but caught, then file is overwritten
            content = controller.get_content(expected_cache_key, output_path=output_path)

            assert content == "Cached content"
            assert output_path.read_text() == "Cached content"  # Overwritten

    def test_get_content_with_checksum_db_resolution_no_matching_record(self, tmp_path):
        """get_content raises when no matching record found in database."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        checksum = "a" * 64

        db.transform.find.return_value = [
            {
                "checksum": "different_checksum",
                "engine": "test",
                "options_hash": "opts_hash",
                "cache_location": "/some/path",
            }
        ]

        controller = TransformController(db, cache_dir, 1024)

        with pytest.raises(ValueError, match="Cache entry not found"):
            controller.get_content(checksum)

    def test_get_content_with_checksum_db_resolution_cache_file_not_found(self, tmp_path):
        """get_content raises when cache file not found after DB resolution."""
        db = Mock()
        db.transform = Mock()

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_checksum = "file_checksum_123"
        engine = "test"
        options_hash = "opts_hash_456"

        controller = TransformController(db, cache_dir, 1024)
        expected_cache_key = controller._compute_cache_key(file_checksum, engine, options_hash)

        # Don't create the cache file
        db.transform.find.return_value = [
            {
                "checksum": file_checksum,
                "engine": engine,
                "options_hash": options_hash,
                "cache_location": str(cache_dir / f"{expected_cache_key}.md"),
                "file_uri": "file:///test.pdf",
                "size_bytes": 100,
                "last_accessed": "2025-01-01T00:00:00+00:00",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]

        with pytest.raises(ValueError, match="Cache file not found"):
            controller.get_content(expected_cache_key)
