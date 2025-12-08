"""Tests for CLI display implementation."""

import io
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

from wks.cli.display import CLIDisplay


class TestCLIDisplay:
    """Test CLIDisplay methods."""

    def test_status(self):
        """Test status message (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.status("Processing...")
            output = f.getvalue()
            assert "Processing" in output
        finally:
            sys.stderr = stderr_backup

    def test_success(self):
        """Test success message (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.success("Done!")
            output = f.getvalue()
            assert "Done" in output
        finally:
            sys.stderr = stderr_backup

    def test_error_without_details(self):
        """Test error message without details (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.error("Error occurred")
            output = f.getvalue()
            assert "Error occurred" in output
        finally:
            sys.stderr = stderr_backup

    def test_error_with_details(self):
        """Test error message with details (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.error("Error occurred", details="Detailed error info")
            output = f.getvalue()
            assert "Error occurred" in output
            assert "Detailed error info" in output
        finally:
            sys.stderr = stderr_backup

    def test_warning(self):
        """Test warning message (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.warning("Warning message")
            output = f.getvalue()
            assert "Warning message" in output
        finally:
            sys.stderr = stderr_backup

    def test_info(self):
        """Test info message (goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.info("Info message")
            output = f.getvalue()
            assert "Info message" in output
        finally:
            sys.stderr = stderr_backup

    def test_table_empty(self):
        """Test table with empty data (info message goes to STDERR)."""
        from io import StringIO

        stderr_backup = sys.stderr
        try:
            f = StringIO()
            sys.stderr = f
            display = CLIDisplay()
            display.table([])
            output = f.getvalue()
            assert "No data to display" in output
        finally:
            sys.stderr = stderr_backup

    def test_table_with_data(self):
        """Test table with data."""
        display = CLIDisplay()

        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

        with redirect_stdout(io.StringIO()) as f:
            display.table(data)

        output = f.getvalue()
        assert "Alice" in output or "name" in output

    def test_table_with_headers(self):
        """Test table with explicit headers."""
        display = CLIDisplay()

        data = [{"a": 1, "b": 2}]

        with redirect_stdout(io.StringIO()) as f:
            display.table(data, headers=["a", "b"])

        output = f.getvalue()
        assert output  # Should have output

    def test_table_with_title(self):
        """Test table with title."""
        display = CLIDisplay()

        data = [{"col": "val"}]

        with redirect_stdout(io.StringIO()) as f:
            display.table(data, title="My Table")

        output = f.getvalue()
        assert output  # Should have output

    def test_table_column_justify(self):
        """Test table with column justification."""
        display = CLIDisplay()

        data = [{"col": "val"}]

        with redirect_stdout(io.StringIO()) as f:
            display.table(data, column_justify={"col": "right"})

        output = f.getvalue()
        assert output  # Should have output

    def test_table_no_header(self):
        """Test table without header."""
        display = CLIDisplay()

        data = [{"col": "val"}]

        with redirect_stdout(io.StringIO()) as f:
            display.table(data, show_header=False)

        output = f.getvalue()
        assert output  # Should have output

    def test_progress_start_update_finish(self):
        """Test progress bar lifecycle."""
        display = CLIDisplay()

        handle = display.progress_start(100, "Processing")
        assert handle is not None

        display.progress_update(handle, advance=50)

        display.progress_finish(handle)

    def test_progress_update_with_description(self):
        """Test progress update with description."""
        display = CLIDisplay()

        handle = display.progress_start(100, "Initial")
        display.progress_update(handle, advance=10, description="Updated")

        display.progress_finish(handle)

    def test_progress_update_invalid_handle(self):
        """Test progress update with invalid handle."""
        display = CLIDisplay()

        # Should not raise
        display.progress_update(999, advance=10)

    def test_progress_finish_invalid_handle(self):
        """Test progress finish with invalid handle."""
        display = CLIDisplay()

        # Should not raise
        display.progress_finish(999)

    def test_spinner_start_update_finish(self):
        """Test spinner lifecycle."""
        display = CLIDisplay()

        handle = display.spinner_start("Spinning...")
        assert handle is not None

        display.spinner_update(handle, "Still spinning")

        display.spinner_finish(handle, "Done!")

    def test_spinner_finish_without_message(self):
        """Test spinner finish without message."""
        display = CLIDisplay()

        handle = display.spinner_start("Spinning...")
        display.spinner_finish(handle)

    def test_spinner_update_none_handle(self):
        """Test spinner update with None handle."""
        display = CLIDisplay()

        # Should not raise
        display.spinner_update(None, "message")

    def test_spinner_finish_none_handle(self):
        """Test spinner finish with None handle."""
        display = CLIDisplay()

        # Should not raise
        display.spinner_finish(None)

    def test_tree_dict(self):
        """Test tree with dictionary."""
        display = CLIDisplay()

        data = {"a": 1, "b": {"c": 2}}

        with redirect_stdout(io.StringIO()) as f:
            display.tree(data)

        output = f.getvalue()
        assert output  # Should have output

    def test_tree_list(self):
        """Test tree with list."""
        display = CLIDisplay()

        data = {"items": [1, 2, {"nested": "value"}]}

        with redirect_stdout(io.StringIO()) as f:
            display.tree(data)

        output = f.getvalue()
        assert output  # Should have output

    def test_tree_with_title(self):
        """Test tree with title."""
        display = CLIDisplay()

        data = {"key": "value"}

        with redirect_stdout(io.StringIO()) as f:
            display.tree(data, title="My Tree")

        output = f.getvalue()
        assert output  # Should have output

    def test_json_output(self):
        """Test JSON output."""
        display = CLIDisplay()

        data = {"key": "value", "number": 42}

        with redirect_stdout(io.StringIO()) as f:
            display.json_output(data)

        output = f.getvalue()
        assert "key" in output or "value" in output

    def test_json_output_custom_indent(self):
        """Test JSON output with custom indent."""
        display = CLIDisplay()

        data = {"key": "value"}

        with redirect_stdout(io.StringIO()) as f:
            display.json_output(data, indent=4)

        output = f.getvalue()
        assert output  # Should have output

    def test_panel(self):
        """Test panel display."""
        display = CLIDisplay()

        with redirect_stdout(io.StringIO()) as f:
            display.panel("Panel content", title="Title")

        output = f.getvalue()
        assert output  # Should have output

    def test_panel_custom_border(self):
        """Test panel with custom border style."""
        display = CLIDisplay()

        with redirect_stdout(io.StringIO()) as f:
            display.panel("Content", border_style="green")

        output = f.getvalue()
        assert output  # Should have output

    def test_init_terminal_width_exception(self):
        """Test CLIDisplay init handles terminal width exception."""
        with patch("shutil.get_terminal_size") as mock_terminal:
            mock_terminal.side_effect = Exception("No terminal")

            # Should still work, using default width
            display = CLIDisplay()
            assert display.console is not None
