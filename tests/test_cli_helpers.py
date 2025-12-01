"""Tests for wks/cli/helpers.py - CLI helper functions."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys


class TestCLIHelpers:
    """Test CLI helper functions."""
    
    def test_maybe_write_json_no_flag(self):
        """Test JSON writing when flag not set."""
        from wks.cli.helpers import maybe_write_json
        
        args = Mock()
        args.json = False
        result = maybe_write_json(args, {"key": "value"})
        assert result is None
    
    @patch('sys.exit')
    def test_maybe_write_json_with_flag(self, mock_exit):
        """Test JSON writing when flag is set."""
        from wks.cli.helpers import maybe_write_json
        
        args = Mock()
        args.json = True
        
        with patch('sys.stdout'):
            maybe_write_json(args, {"key": "value"})
            mock_exit.assert_called_once_with(0)
    
    def test_as_file_uri_local(self, tmp_path):
        """Test file URI conversion."""
        from wks.cli.helpers import as_file_uri_local
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        uri = as_file_uri_local(test_file)
        assert uri.startswith("file://")
    
    def test_file_checksum(self, tmp_path):
        """Test file checksum calculation."""
        from wks.cli.helpers import file_checksum
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        checksum = file_checksum(test_file)
        assert len(checksum) == 64  # SHA-256
    
    def test_make_progress_cli(self):
        """Test progress bar for CLI."""
        from wks.cli.helpers import make_progress
        
        progress = make_progress(100, display="cli")
        with progress as p:
            p.update("Testing")
    
    def test_make_progress_noop(self):
        """Test no-op progress for non-CLI."""
        from wks.cli.helpers import make_progress
        
        progress = make_progress(100, display="mcp")
        with progress as p:
            p.update("Testing")
    
    @patch('wks.monitor.MonitorController.check_path')
    def test_iter_files(self, mock_check, tmp_path):
        """Test file iteration."""
        from wks.cli.helpers import iter_files
        
        test_file = tmp_path / "test.md"  
        test_file.write_text("content")
        
        mock_check.return_value = Mock(tracked=True)
        
        files = iter_files([str(tmp_path)], [".md"], {})
        assert len(files) >= 1
