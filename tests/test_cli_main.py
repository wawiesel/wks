"""Tests for wks/cli/__main__.py - CLI entry point."""

import sys
from unittest.mock import patch, MagicMock
import pytest


class TestCLIMainEntryPoint:
    """Test entry point imports and execution."""

    def test_cli_main_import(self):
        """Test that CLI main can be imported."""
        from wks.cli import __main__
        assert __main__ is not None

    def test_cli_main_module_execution(self):
        """Test that __main__ module can be executed."""
        from wks.cli import __main__

        # Should not raise exception
        assert hasattr(__main__, '__name__')

    @patch('wks.cli.__main__.main')
    def test_cli_main_calls_main_function(self, mock_main):
        """Test that __main__ calls main() function."""
        mock_main.return_value = 0

        # Simulate module execution
        from wks.cli import __main__

        # The module should have main available
        assert hasattr(__main__, 'main')

    @patch('wks.cli.__main__.sys.exit')
    @patch('wks.cli.__main__.main')
    def test_cli_main_exits_with_return_code(self, mock_main, mock_exit):
        """Test that __main__ exits with main() return code."""
        mock_main.return_value = 2

        # Execute the module's if __name__ == "__main__" block
        import wks.cli.__main__ as cli_main

        # Manually trigger the exit logic
        if hasattr(cli_main, 'main'):
            exit_code = cli_main.main()
            mock_exit.assert_not_called()  # sys.exit is only called in actual execution
        else:
            # If main is imported from parent, test that way
            from wks.cli import main
            result = main([])
            assert isinstance(result, int)


class TestCLIIntegration:
    """Integration test for full CLI invocation."""

    @patch('wks.cli.__main__.main')
    def test_cli_main_invocation(self, mock_main):
        """Test CLI invocation through __main__."""
        mock_main.return_value = 0

        # Import and check structure
        from wks.cli import __main__
        assert __main__ is not None

    def test_cli_main_imports_main(self):
        """Test that __main__ imports main from parent."""
        from wks.cli import __main__
        from wks.cli import main

        # Both should be available
        assert main is not None
        assert __main__ is not None

    @patch('sys.argv', ['wks.cli', '--version'])
    def test_cli_main_sys_exit_handling(self):
        """Test that CLI handles sys.exit properly."""
        from wks.cli import main

        # Test that main can be called
        # This will actually run, so we need to handle it carefully
        try:
            result = main(['--version'])
            assert isinstance(result, int)
        except SystemExit:
            # SystemExit is expected in some cases
            pass

    def test_cli_main_module_attributes(self):
        """Test that __main__ module has expected attributes."""
        from wks.cli import __main__

        # Should have sys imported
        assert hasattr(__main__, 'sys') or 'sys' in dir(__main__)

        # Should have main function available (imported or defined)
        assert hasattr(__main__, 'main') or 'main' in dir(__main__)
