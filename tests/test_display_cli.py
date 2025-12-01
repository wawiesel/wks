"""Tests for wks/display/cli.py - CLI display output."""
import pytest


class TestCLIDisplay:
    """Test CLI display class."""
    
    def test_creation(self):
        """Test CLIDisplay can be created."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        assert display is not None
        assert display.console is not None
    
    def test_info_message(self):
        """Test info message display."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        display.info("test message")  # Should not raise
    
    def test_success_message(self):
        """Test success message display."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        display.success("success message")
    
    def test_warning_message(self):
        """Test warning message display."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        display.warning("warning message")
    
    def test_error_message(self):
        """Test error message display."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        display.error("error message")
    
    def test_error_with_details(self):
        """Test error message with details."""
        from wks.display.cli import CLIDisplay
        
        display = CLIDisplay()
        display.error("error message", details="additional info")
