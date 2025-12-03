"""Extended tests for CLIDisplay formatting and rendering."""

import pytest

from wks.display.cli import CLIDisplay


@pytest.mark.unit
class TestCLIDisplayProgressExtended:
    """Extended tests for progress tracking."""

    def test_progress_with_zero_total(self):
        """progress_start handles zero total gracefully."""
        display = CLIDisplay()

        handle = display.progress_start(total=0, description="Empty task")

        assert handle is not None
        display.progress_finish(handle)

    def test_progress_update_beyond_total(self):
        """progress_update handles advancing beyond total."""
        display = CLIDisplay()

        handle = display.progress_start(total=10, description="Task")
        display.progress_update(handle, advance=20)  # Beyond total

        # Should not crash
        display.progress_finish(handle)

    def test_multiple_progress_bars(self):
        """Multiple progress bars can coexist."""
        display = CLIDisplay()

        handle1 = display.progress_start(total=100, description="Task 1")
        handle2 = display.progress_start(total=50, description="Task 2")

        display.progress_update(handle1, advance=10)
        display.progress_update(handle2, advance=5)

        display.progress_finish(handle1)
        display.progress_finish(handle2)


@pytest.mark.unit
class TestCLIDisplayTableExtended:
    """Extended tests for table rendering."""

    def test_table_with_none_values(self, capsys):
        """table handles None values in data."""
        display = CLIDisplay()

        data = [{"name": "Alice", "age": None}, {"name": None, "age": 25}]

        display.table(data, title="Users with None")

        captured = capsys.readouterr()
        assert "Alice" in captured.out

    def test_table_with_mixed_types(self, capsys):
        """table handles mixed data types."""
        display = CLIDisplay()

        data = [
            {"id": 1, "value": "text", "flag": True, "score": 3.14},
        ]

        display.table(data, title="Mixed Types")

        captured = capsys.readouterr()
        assert "text" in captured.out
        assert "True" in captured.out

    def test_table_with_long_strings(self, capsys):
        """table handles long strings (truncation/wrapping)."""
        display = CLIDisplay()

        long_text = "A" * 200
        data = [{"text": long_text}]

        display.table(data, title="Long Text")

        captured = capsys.readouterr()
        # Should render without crashing
        assert captured.out

    def test_table_with_custom_headers(self, capsys):
        """table respects custom headers."""
        display = CLIDisplay()

        data = [{"a": 1, "b": 2}]

        display.table(data, headers=["Column A", "Column B"], title="Custom Headers")

        captured = capsys.readouterr()
        # Headers should be used
        assert captured.out


@pytest.mark.unit
class TestCLIDisplayErrorDetails:
    """Extended tests for error rendering with details."""

    def test_error_with_nested_details(self, capsys):
        """error displays nested error details."""
        display = CLIDisplay()

        details = {"error_code": 500, "context": {"file": "test.py", "line": 42}}

        display.error("Nested error", details=details)

        captured = capsys.readouterr()
        assert "Nested error" in captured.out

    def test_error_with_list_details(self, capsys):
        """error displays list-based details."""
        display = CLIDisplay()

        details = {"errors": ["Error 1", "Error 2", "Error 3"]}

        display.error("Multiple errors", details=details)

        captured = capsys.readouterr()
        assert "Multiple errors" in captured.out


@pytest.mark.unit
class TestCLIDisplaySpinnerExtended:
    """Extended tests for spinner functionality."""

    def test_spinner_update_description(self):
        """spinner_update changes description."""
        display = CLIDisplay()

        handle = display.spinner_start("Initial task")
        display.spinner_update(handle, "Updated task")
        display.spinner_finish(handle, "Done")

        # Should complete without error

    def test_spinner_finish_with_success_message(self):
        """spinner_finish displays success message."""
        display = CLIDisplay()

        handle = display.spinner_start("Processing")
        display.spinner_finish(handle, "✓ Complete")

        # Should complete without error


@pytest.mark.unit
class TestCLIDisplayTreeExtended:
    """Extended tests for tree rendering."""

    def test_tree_with_deep_nesting(self, capsys):
        """tree handles deeply nested structures."""
        display = CLIDisplay()

        data = {"level1": {"level2": {"level3": {"level4": "deep value"}}}}

        display.tree(data, title="Deep Tree")

        captured = capsys.readouterr()
        assert "deep value" in captured.out

    def test_tree_with_lists(self, capsys):
        """tree handles lists in structure."""
        display = CLIDisplay()

        data = {"items": ["item1", "item2", "item3"]}

        display.tree(data, title="List Tree")

        captured = capsys.readouterr()
        assert "item1" in captured.out

    def test_tree_with_mixed_content(self, capsys):
        """tree handles mixed dicts and lists."""
        display = CLIDisplay()

        data = {"config": {"enabled": True, "options": ["opt1", "opt2"]}}

        display.tree(data, title="Mixed Tree")

        captured = capsys.readouterr()
        assert "config" in captured.out


@pytest.mark.unit
class TestCLIDisplayJSON:
    """Tests for JSON output."""

    def test_json_output_dict(self, capsys):
        """json_output renders dict as JSON."""
        display = CLIDisplay()

        data = {"key": "value", "number": 42}

        display.json_output(data)

        captured = capsys.readouterr()
        assert '"key"' in captured.out
        assert '"value"' in captured.out

    def test_json_output_list(self, capsys):
        """json_output renders list as JSON."""
        display = CLIDisplay()

        data = [1, 2, 3]

        display.json_output(data)

        captured = capsys.readouterr()
        assert "[" in captured.out

    def test_json_output_nested(self, capsys):
        """json_output handles nested structures."""
        display = CLIDisplay()

        data = {"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}

        display.json_output(data)

        captured = capsys.readouterr()
        assert "Alice" in captured.out
        assert "Bob" in captured.out


@pytest.mark.unit
class TestCLIDisplayPanel:
    """Tests for panel rendering."""

    def test_panel_simple(self, capsys):
        """panel renders simple content."""
        display = CLIDisplay()

        display.panel("Simple content", title="Test Panel")

        captured = capsys.readouterr()
        assert "Simple content" in captured.out

    def test_panel_multiline(self, capsys):
        """panel handles multiline content."""
        display = CLIDisplay()

        content = "Line 1\nLine 2\nLine 3"
        display.panel(content, title="Multiline")

        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 3" in captured.out
