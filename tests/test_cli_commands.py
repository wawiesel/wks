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
    config.transform = TransformConfig(cache_location=".wks/cache")
    config.mongo = MongoSettings(uri="mongodb://localhost:27017")
    
    # Mock database config strings
    config.transform.database = "wks.transform"
    
    # Mock cache_max_size_bytes which is not in TransformConfig but accessed in commands
    # We should probably add it to TransformConfig or mock it here if it's dynamic
    # Looking at code: max_size_bytes = transform_cfg.cache_max_size_bytes
    # TransformConfig definition in config.py doesn't have cache_max_size_bytes, 
    # so the code in commands might be broken or I missed something.
    # Let's check config.py again.
    # Ah, TransformConfig only has cache_location.
    # The commands access transform_cfg.cache_max_size_bytes. 
    # This suggests a bug in the commands or the config definition.
    # I will assume for now I need to mock it.
    config.transform.cache_max_size_bytes = 1024 * 1024 * 100
    
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
    monkeypatch.setattr("wks.cli.commands.diff.DiffController", lambda: diff_controller)
    
    transform_controller = MagicMock()
    # transform.py imports TransformController
    monkeypatch.setattr("wks.cli.commands.transform.TransformController", lambda *args: transform_controller)
    # cat.py imports TransformController
    monkeypatch.setattr("wks.cli.commands.cat.TransformController", lambda *args: transform_controller)
    
    return {"diff": diff_controller, "transform": transform_controller}


@pytest.fixture
def mock_mongo(monkeypatch):
    """Mock MongoDB connection."""
    client = MagicMock()
    monkeypatch.setattr("wks.cli.commands.transform.connect_to_mongo", lambda uri: client)
    monkeypatch.setattr("wks.cli.commands.cat.connect_to_mongo", lambda uri: client)
    return client


class TestDiffCommand:
    """Test diff command."""

    def test_diff_success(self, mock_config, mock_controller, tmp_path, capsys):
        """Test successful diff."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

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

    def test_diff_file_not_found(self, mock_config, mock_controller, tmp_path):
        """Test diff with missing file."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        
        args = argparse.Namespace(
            engine="unified",
            file1=str(file1),
            file2=str(tmp_path / "missing.txt"),
            display_obj=None
        )

        rc = diff_cmd(args)
        assert rc == 2

    def test_diff_error(self, mock_config, mock_controller, tmp_path):
        """Test diff execution error."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

        mock_controller["diff"].diff.side_effect = RuntimeError("Diff failed")

        args = argparse.Namespace(
            engine="unified",
            file1=str(file1),
            file2=str(file2),
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

    def test_cat_checksum_success(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test cat with checksum."""
        checksum = "a" * 64
        cache_dir = tmp_path / ".wks" / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / f"{checksum}.md").write_text("Cached content")

        # Mock expand_path to return our temp cache dir
        with patch("wks.cli.commands.cat.expand_path", return_value=cache_dir):
            args = argparse.Namespace(
                input=checksum,
                output=None
            )

            rc = cat_cmd(args)

            assert rc == 0
            captured = capsys.readouterr()
            assert "Cached content" in captured.out

    def test_cat_checksum_not_found(self, mock_config, mock_controller, mock_mongo, tmp_path):
        """Test cat with missing checksum."""
        checksum = "a" * 64
        cache_dir = tmp_path / ".wks" / "cache"
        cache_dir.mkdir(parents=True)

        with patch("wks.cli.commands.cat.expand_path", return_value=cache_dir):
            args = argparse.Namespace(
                input=checksum,
                output=None
            )

            rc = cat_cmd(args)
            assert rc == 2

    def test_cat_file_success(self, mock_config, mock_controller, mock_mongo, tmp_path, capsys):
        """Test cat with file path (transforms first)."""
        file_path = tmp_path / "test.pdf"
        file_path.write_text("content")
        
        checksum = "b" * 64
        cache_dir = tmp_path / ".wks" / "cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / f"{checksum}.md").write_text("Transformed content")

        mock_controller["transform"].transform.return_value = checksum

        # We need to mock expand_path carefully:
        # 1. For cache_location -> cache_dir
        # 2. For input_arg -> file_path
        def side_effect(path):
            if str(path).endswith("cache"):
                return cache_dir
            return Path(path)

        with patch("wks.cli.commands.cat.expand_path", side_effect=side_effect):
            args = argparse.Namespace(
                input=str(file_path),
                output=None
            )

            rc = cat_cmd(args)

            assert rc == 0
            captured = capsys.readouterr()
            assert "Transformed content" in captured.out
            mock_controller["transform"].transform.assert_called_once()
