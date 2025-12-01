"""Tests for CLI commands: diff, transform, cat."""

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wks.cli.commands.diff import diff_cmd
from wks.cli.commands.transform import transform_cmd
from wks.cli.commands.cat import cat_cmd
from wks.config import WKSConfig, TransformConfig, MongoSettings


@pytest.fixture
def mock_config(monkeypatch):
    """Mock WKSConfig.load()."""
    config = MagicMock(spec=WKSConfig)
    
    # Create valid TransformConfig structure
    from wks.transform.config import CacheConfig
    config.transform = TransformConfig(
        cache=CacheConfig(location=".wks/cache", max_size_bytes=1024*1024*100),
        engines={},
        database="wks.transform"
    )
    config.mongo = MongoSettings(uri="mongodb://localhost:27017")
    
    # Mock database config strings
    config.transform.database = "wks_transform"
    
    # Mock cache_max_size_bytes access if commands still use it directly
    # The commands should be updated to use config.transform.cache.max_size_bytes
    # but for now let's ensure the mock has what's needed.
    # If commands access config.transform.cache_max_size_bytes, we can mock it:
    # config.transform.cache_max_size_bytes = ... 
    # But TransformConfig is a dataclass, so we can't easily add attributes unless we mock the instance.
    # However, config.transform IS a real instance here.
    # Let's check if we need to patch the commands or if they use the new structure.
    # The commands use TransformController which takes cache_dir and max_size_bytes.
    # They get these from config.transform.cache.location etc.
    
    monkeypatch.setattr(WKSConfig, "load", lambda path=None: config)
    return config


@pytest.fixture
def mock_display(monkeypatch):
    """Mock display object."""
    display = MagicMock()
    return display


@pytest.fixture
def mock_controller(monkeypatch):
    """Mock controllers."""
    diff_controller = MagicMock()
    monkeypatch.setattr("wks.cli.commands.diff.DiffController", lambda *args: diff_controller)
    
    transform_controller = MagicMock()
    # Patch globally for runtime imports
    monkeypatch.setattr("wks.transform.TransformController", lambda *args: transform_controller)
    # Patch in modules where it is imported at top level
    monkeypatch.setattr("wks.cli.commands.transform.TransformController", lambda *args: transform_controller)
    monkeypatch.setattr("wks.cli.commands.cat.TransformController", lambda *args: transform_controller)
    
    return {"diff": diff_controller, "transform": transform_controller}


@pytest.fixture
def mock_mongo(monkeypatch):
    """Mock MongoDB connection."""
    client = MagicMock()
    # Patch original source (for diff command which imports inside function)
    monkeypatch.setattr("wks.db_helpers.connect_to_mongo", lambda uri: client)
    # Patch in modules where it is imported at top level
    monkeypatch.setattr("wks.cli.commands.transform.connect_to_mongo", lambda uri: client)
    monkeypatch.setattr("wks.cli.commands.cat.connect_to_mongo", lambda uri: client)
    return client


class TestDiffCommand:
    """Test diff command."""

    def test_diff_success(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test successful diff."""
        # We don't need real files if we mock the controller
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        mock_controller["diff"].diff.return_value = "Diff result"

        args = argparse.Namespace(
            engine="unified",
            file1=str(file1),
            file2=str(file2),
            display_obj=None
        )

        rc = diff_cmd(args)
        
        assert rc == 0
        captured = capsys.readouterr()
        assert "Diff result" in captured.out
        mock_controller["diff"].diff.assert_called_once()

    # Removed test_diff_file_not_found because validation is now inside controller
    # and we are mocking the controller.
    # If we want to test controller validation, we should test controller directly.
    # Or we can make the mock raise error.
    
    def test_diff_error(self, mock_config, mock_controller, mock_mongo, tmp_path):
        """Test diff execution error."""
        mock_controller["diff"].diff.side_effect = RuntimeError("Diff failed")

        args = argparse.Namespace(
            engine="unified",
            file1="file1",
            file2="file2",
            display_obj=None
        )

        rc = diff_cmd(args)
        assert rc == 2


class TestTransformCommand:
    """Test transform command."""

    def test_transform_success(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test successful transform."""
        file_path = tmp_path / "test.pdf"
        file_path.write_text("content")

        mock_controller["transform"].transform.return_value = "cache_key_123"

        args = argparse.Namespace(
            engine="docling",
            file_path=str(file_path),
            output=None
        )

        rc = transform_cmd(args)

        assert rc == 0
        captured = capsys.readouterr()
        assert "cache_key_123" in captured.out
        mock_controller["transform"].transform.assert_called_once()

    def test_transform_with_output(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test transform with output file."""
        file_path = tmp_path / "test.pdf"
        file_path.write_text("content")
        output_path = tmp_path / "output.md"

        mock_controller["transform"].transform.return_value = "cache_key_123"

        args = argparse.Namespace(
            engine="docling",
            file_path=str(file_path),
            output=str(output_path)
        )

        rc = transform_cmd(args)

        assert rc == 0
        captured = capsys.readouterr()
        assert "cache_key_123" in captured.out
        assert f"Transformed to {output_path}" in captured.err

    def test_transform_file_not_found(self, mock_config, mock_controller, mock_mongo, tmp_path):
        """Test transform missing file."""
        args = argparse.Namespace(
            engine="docling",
            file_path=str(tmp_path / "missing.pdf"),
            output=None
        )

        rc = transform_cmd(args)
        assert rc == 2


class TestCatCommand:
    """Test cat command."""

    def test_cat_checksum_success(self, mock_config, mock_controller, mock_mongo, capsys):
        """Test cat with checksum."""
        checksum = "a" * 64
        mock_controller["transform"].get_content.return_value = "Cached content"

        args = argparse.Namespace(
            input=checksum,
            output=None
        )

        rc = cat_cmd(args)

        assert rc == 0
        captured = capsys.readouterr()
        assert "Cached content" in captured.out
        mock_controller["transform"].get_content.assert_called_with(checksum, None)

    def test_cat_checksum_not_found(self, mock_config, mock_controller, mock_mongo):
        """Test cat with missing checksum."""
        checksum = "a" * 64
        mock_controller["transform"].get_content.side_effect = ValueError("Not found")

        args = argparse.Namespace(
            input=checksum,
            output=None
        )

        rc = cat_cmd(args)
        assert rc == 2

    def test_cat_file_success(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test cat with file path."""
        file_path = str(tmp_path / "test.pdf")
        mock_controller["transform"].get_content.return_value = "Transformed content"

        args = argparse.Namespace(
            input=file_path,
            output=None
        )

        rc = cat_cmd(args)

        assert rc == 0
        captured = capsys.readouterr()
        assert "Transformed content" in captured.out
        mock_controller["transform"].get_content.assert_called_with(file_path, None)

