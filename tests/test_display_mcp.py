"""Tests for MCP display implementation."""

import io
import json
from contextlib import redirect_stdout

import pytest
from wks.display.mcp import MCPDisplay


class TestMCPDisplay:
    """Test MCPDisplay methods."""

    def test_status(self):
        """Test status message output."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.status("Processing...")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "status"
        assert data["message"] == "Processing..."
        assert "timestamp" in data

    def test_success(self):
        """Test success message."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.success("Done!")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "success"
        assert data["message"] == "Done!"

    def test_success_with_data(self):
        """Test success message with data."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.success("Done!", data={"result": "success"})
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "success"
        assert "data" in data
        assert data["data"]["result"] == "success"

    def test_error(self):
        """Test error message."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.error("Error occurred")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "error"
        assert data["message"] == "Error occurred"

    def test_error_with_details(self):
        """Test error message with details."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.error("Error occurred", details="Detailed info")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "error"
        assert data["details"] == "Detailed info"

    def test_warning(self):
        """Test warning message."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.warning("Warning message")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "warning"
        assert data["message"] == "Warning message"

    def test_info(self):
        """Test info message."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.info("Info message")
        
        output = f.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "info"
        assert data["message"] == "Info message"

    def test_table(self):
        """Test table output."""
        display = MCPDisplay()
        
        data = [{"name": "Alice", "age": 30}]
        
        with redirect_stdout(io.StringIO()) as f:
            display.table(data)
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "table"
        assert result["data"] == data

    def test_table_with_headers(self):
        """Test table with headers."""
        display = MCPDisplay()
        
        data = [{"a": 1, "b": 2}]
        
        with redirect_stdout(io.StringIO()) as f:
            display.table(data, headers=["a", "b"])
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["headers"] == ["a", "b"]

    def test_table_with_title(self):
        """Test table with title."""
        display = MCPDisplay()
        
        data = [{"col": "val"}]
        
        with redirect_stdout(io.StringIO()) as f:
            display.table(data, title="My Table")
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["title"] == "My Table"

    def test_progress_start_update_finish(self):
        """Test progress lifecycle."""
        display = MCPDisplay()
        
        handle = display.progress_start(100, "Processing")
        assert handle is not None
        
        display.progress_update(handle, advance=50)
        
        with redirect_stdout(io.StringIO()) as f:
            display.progress_finish(handle)
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "progress_complete"
        assert result["completed"] == 50

    def test_progress_update_with_description(self):
        """Test progress update with description."""
        display = MCPDisplay()
        
        handle = display.progress_start(100, "Initial")
        display.progress_update(handle, advance=10, description="Updated")
        
        with redirect_stdout(io.StringIO()) as f:
            display.progress_finish(handle)
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["description"] == "Updated"

    def test_progress_update_invalid_handle(self):
        """Test progress update with invalid handle."""
        display = MCPDisplay()
        
        # Should not raise
        display.progress_update(999, advance=10)

    def test_progress_finish_invalid_handle(self):
        """Test progress finish with invalid handle."""
        display = MCPDisplay()
        
        # Should not output anything
        with redirect_stdout(io.StringIO()) as f:
            display.progress_finish(999)
        
        output = f.getvalue().strip()
        assert output == ""

    def test_spinner_start_update_finish(self):
        """Test spinner lifecycle."""
        display = MCPDisplay()
        
        handle = display.spinner_start("Spinning...")
        assert handle is not None
        
        display.spinner_update(handle, "Still spinning")
        
        with redirect_stdout(io.StringIO()) as f:
            display.spinner_finish(handle, "Done!")
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "status"
        assert result["message"] == "Done!"

    def test_spinner_finish_no_message(self):
        """Test spinner finish without message."""
        display = MCPDisplay()
        
        handle = display.spinner_start("Spinning...")
        
        with redirect_stdout(io.StringIO()) as f:
            display.spinner_finish(handle)
        
        output = f.getvalue().strip()
        assert output == ""

    def test_tree(self):
        """Test tree output."""
        display = MCPDisplay()
        
        data = {"a": 1, "b": {"c": 2}}
        
        with redirect_stdout(io.StringIO()) as f:
            display.tree(data)
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "tree"
        assert result["data"] == data

    def test_tree_with_title(self):
        """Test tree with title."""
        display = MCPDisplay()
        
        data = {"key": "value"}
        
        with redirect_stdout(io.StringIO()) as f:
            display.tree(data, title="My Tree")
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["title"] == "My Tree"

    def test_json_output(self):
        """Test json_output method."""
        display = MCPDisplay()
        
        data = {"key": "value"}
        
        with redirect_stdout(io.StringIO()) as f:
            display.json_output(data)
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "data"
        assert result["data"] == data

    def test_panel(self):
        """Test panel output."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.panel("Content", title="Title")
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "panel"
        assert result["content"] == "Content"
        assert result["title"] == "Title"

    def test_panel_no_title(self):
        """Test panel without title."""
        display = MCPDisplay()
        
        with redirect_stdout(io.StringIO()) as f:
            display.panel("Content")
        
        output = f.getvalue().strip()
        result = json.loads(output)
        assert result["type"] == "panel"
        assert "title" not in result

