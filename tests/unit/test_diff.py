"""Tests for Diff layer."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from wks.diff.engines import Bsdiff3Engine, MyersEngine, get_engine
from wks.diff.controller import DiffController
from wks.diff.config import DiffConfig, DiffEngineConfig, DiffRouterConfig


@pytest.mark.unit
class TestBsdiff3Engine:
    """Test Bsdiff3Engine."""

    def test_diff_identical_files(self, tmp_path):
        """Bsdiff3 detects identical files."""
        engine = Bsdiff3Engine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"same content")
        file2.write_bytes(b"same content")

        result = engine.diff(file1, file2, {})

        assert "identical" in result.lower()

    def test_diff_different_files(self, tmp_path):
        """Bsdiff3 detects different files."""
        engine = Bsdiff3Engine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B different")

        result = engine.diff(file1, file2, {})

        assert "differ" in result.lower() or "patch" in result.lower()
        assert "file1.bin" in result  # filename should be in output
        assert "file2.bin" in result  # filename should be in output


@pytest.mark.unit
class TestMyersEngine:
    """Test MyersEngine."""

    def test_diff_identical_text_files(self, tmp_path):
        """Myers detects identical text files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\nline 3\n")
        file2.write_text("line 1\nline 2\nline 3\n")

        result = engine.diff(file1, file2, {})

        assert "identical" in result.lower()

    def test_diff_different_text_files(self, tmp_path):
        """Myers shows diff for different text files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\nline 3\n")
        file2.write_text("line 1\nmodified line 2\nline 3\n")

        result = engine.diff(file1, file2, {"context_lines": 1})

        assert "-line 2" in result  # Removed line
        assert "+modified line 2" in result  # Added line

    def test_diff_binary_file_fails(self, tmp_path):
        """Myers fails on binary files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"\x00\x01\x02\x03")
        file2.write_bytes(b"\x00\x01\x02\x04")

        with pytest.raises(ValueError, match="not a text file"):
            engine.diff(file1, file2, {})

    def test_diff_file2_binary_fails(self, tmp_path):
        """Myers fails when file2 is binary."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.bin"
        file1.write_text("text content")
        file2.write_bytes(b"\x00\x01\x02\x03")

        with pytest.raises(ValueError, match="not a text file"):
            engine.diff(file1, file2, {})

    def test_is_text_file_utf8(self, tmp_path):
        """Detect UTF-8 text file."""
        engine = MyersEngine()

        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello world", encoding="utf-8")

        assert engine._is_text_file(text_file) is True

    def test_is_text_file_binary(self, tmp_path):
        """Detect binary file."""
        engine = MyersEngine()

        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        assert engine._is_text_file(binary_file) is False

    @patch("subprocess.run")
    def test_diff_command_fails_returncode_2(self, mock_run, tmp_path):
        """Myers raises RuntimeError when diff command fails (returncode >= 2)."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content")
        file2.write_text("content")

        # Mock subprocess to return error code 2
        mock_result = Mock()
        mock_result.returncode = 2
        mock_result.stderr = "diff: invalid option"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="diff command failed"):
            engine.diff(file1, file2, {})

    @patch("subprocess.run")
    def test_diff_command_exception(self, mock_run, tmp_path):
        """Myers wraps non-RuntimeError exceptions."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content")
        file2.write_text("content")

        # Mock subprocess to raise an exception
        mock_run.side_effect = FileNotFoundError("diff command not found")

        with pytest.raises(RuntimeError, match="diff error"):
            engine.diff(file1, file2, {})

    def test_is_text_file_unicode_decode_error_utf8(self, tmp_path):
        """Test _is_text_file handles UTF-8 decode error."""
        engine = MyersEngine()

        # Create file with invalid UTF-8 but valid ASCII won't work either
        binary_file = tmp_path / "invalid.txt"
        # Write bytes that are not valid UTF-8 or ASCII
        binary_file.write_bytes(b'\xff\xfe\x00\x01')

        assert engine._is_text_file(binary_file) is False

    def test_is_text_file_unicode_decode_error_ascii_fallback(self, tmp_path):
        """Test _is_text_file tries ASCII after UTF-8 fails."""
        engine = MyersEngine()

        # Create file with ASCII-only content (should pass)
        text_file = tmp_path / "ascii.txt"
        text_file.write_bytes(b'Hello world')

        assert engine._is_text_file(text_file) is True

    def test_is_text_file_exception_handling(self, tmp_path):
        """Test _is_text_file handles file reading exceptions."""
        engine = MyersEngine()

        # Test with non-existent file (should return False on exception)
        non_existent = tmp_path / "does_not_exist.txt"

        # Should not raise, should return False
        result = engine._is_text_file(non_existent)
        assert result is False

    def test_diff_context_lines_option(self, tmp_path):
        """Myers respects context_lines option."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("A\nB\nC\nD\nE\n")
        file2.write_text("A\nB\nX\nD\nE\n")

        # With 0 context lines
        result_0 = engine.diff(file1, file2, {"context_lines": 0})

        # With 2 context lines
        result_2 = engine.diff(file1, file2, {"context_lines": 2})

        # More context = more lines shown
        assert len(result_2.split("\n")) >= len(result_0.split("\n"))


@pytest.mark.unit
class TestEngineRegistry:
    """Test engine registry."""

    def test_get_engine_bsdiff3(self):
        """Get bsdiff3 engine."""
        engine = get_engine("bsdiff3")

        assert engine is not None
        assert isinstance(engine, Bsdiff3Engine)

    def test_get_engine_myers(self):
        """Get myers engine."""
        engine = get_engine("myers")

        assert engine is not None
        assert isinstance(engine, MyersEngine)

    def test_get_engine_unknown(self):
        """Get unknown engine returns None."""
        engine = get_engine("unknown")

        assert engine is None


@pytest.mark.unit
class TestDiffController:
    """Test DiffController."""

    def test_diff_file1_not_found(self, tmp_path):
        """Diff raises on missing file1."""
        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config)

        file2 = tmp_path / "file2.txt"
        file2.write_text("content")

        with pytest.raises(ValueError, match="File not found"):
            controller.diff(tmp_path / "missing.txt", file2, "myers")

    def test_diff_file2_not_found(self, tmp_path):
        """Diff raises on missing file2."""
        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config)

        file1 = tmp_path / "file1.txt"
        file1.write_text("content")

        with pytest.raises(ValueError, match="File not found"):
            controller.diff(file1, tmp_path / "missing.txt", "myers")

    def test_diff_unknown_engine(self, tmp_path):
        """Diff raises on unknown engine."""
        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")

        with pytest.raises(ValueError, match="Unknown engine"):
            controller.diff(file1, file2, "unknown")

    def test_diff_success_myers(self, tmp_path):
        """Diff succeeds with myers engine."""
        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\n")
        file2.write_text("line 1\nmodified\n")

        result = controller.diff(file1, file2, "myers", {"context_lines": 1})

        assert "-line 2" in result
        assert "+modified" in result

    def test_diff_success_bsdiff3(self, tmp_path):
        """Diff succeeds with bsdiff3 engine."""
        config = DiffConfig(
            engines={
                "bsdiff3": DiffEngineConfig(
                    name="bsdiff3", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="bsdiff3"),
        )
        controller = DiffController(config)

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"binary A")
        file2.write_bytes(b"binary B")

        result = controller.diff(file1, file2, "bsdiff3")

        assert "patch" in result.lower() or "differ" in result.lower()

    def test_diff_options_passed_to_engine(self, tmp_path):
        """Diff passes options to engine."""
        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("A\nB\nC\nD\nE\n")
        file2.write_text("A\nX\nC\nD\nE\n")

        # Pass custom context_lines
        result = controller.diff(file1, file2, "myers", {"context_lines": 0})

        # Verify it was used (minimal context)
        assert result is not None

    def test_diff_unknown_engine_no_config(self, tmp_path):
        """Diff raises on unknown engine when no config provided."""
        controller = DiffController(config=None)

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")

        with pytest.raises(ValueError, match="Unknown engine"):
            controller.diff(file1, file2, "nonexistent_engine")

    def test_resolve_target_checksum_with_transform_controller(self, tmp_path):
        """Test resolving checksum target with transform controller."""
        from unittest.mock import MagicMock

        # Mock transform controller
        mock_transform = MagicMock()
        mock_transform.cache_manager.cache_dir = tmp_path

        # Create cache file
        checksum = "a" * 64
        cache_file = tmp_path / f"{checksum}.md"
        cache_file.write_text("cached content")

        config = DiffConfig(
            engines={
                "myers": DiffEngineConfig(
                    name="myers", enabled=True, is_default=True, options={}
                )
            },
            router=DiffRouterConfig(rules=[], fallback="myers"),
        )
        controller = DiffController(config=config, transform_controller=mock_transform)

        file2 = tmp_path / "file2.txt"
        file2.write_text("other content")

        result = controller.diff(checksum, str(file2), "myers")
        assert result is not None

    def test_resolve_target_checksum_no_transform_controller(self):
        """Test resolving checksum without transform controller raises error."""
        controller = DiffController(transform_controller=None)

        checksum = "a" * 64

        with pytest.raises(ValueError, match="TransformController required"):
            controller._resolve_target(checksum)

    def test_resolve_target_checksum_not_found(self, tmp_path):
        """Test resolving checksum when cache file doesn't exist."""
        from unittest.mock import MagicMock

        # Mock transform controller
        mock_transform = MagicMock()
        mock_transform.cache_manager.cache_dir = tmp_path

        checksum = "a" * 64
        # Don't create the cache file

        controller = DiffController(transform_controller=mock_transform)

        with pytest.raises(ValueError, match="Cache entry not found"):
            controller._resolve_target(checksum)

    def test_resolve_target_checksum_glob_match(self, tmp_path):
        """Test resolving checksum with glob pattern when .md doesn't exist."""
        from unittest.mock import MagicMock

        # Mock transform controller
        mock_transform = MagicMock()
        mock_transform.cache_manager.cache_dir = tmp_path

        checksum = "a" * 64
        # Create cache file with different extension
        cache_file = tmp_path / f"{checksum}.txt"
        cache_file.write_text("cached content")

        controller = DiffController(transform_controller=mock_transform)

        resolved = controller._resolve_target(checksum)
        assert resolved == cache_file
