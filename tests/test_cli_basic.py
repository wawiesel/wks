"""Basic CLI tests - tests for wks/cli/__init__.py."""

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore


def run_cli(args):
    """Execute CLI command and capture stdout/stderr."""
    from wks.cli import main

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            rc = main(args)
        except SystemExit as exc:  # CLI exits on errors/--json flows
            rc = exc.code if isinstance(exc.code, int) else 0
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_cli_version_flag():
    """Test --version flag."""
    rc, out, _ = run_cli(["--version"])
    assert rc == 0
    expected = importlib_metadata.version("wks")
    assert f"wksc {expected}" in out


def test_cli_help_flag():
    """Test --help flag."""
    rc, out, _ = run_cli(["--help"])
    assert rc == 0
    assert "usage:" in out.lower() or "wksc" in out.lower()


def test_cli_no_command():
    """Test CLI with no command shows help and returns 2."""
    rc, out, _ = run_cli([])
    assert rc == 2
    assert "usage:" in out.lower() or "wksc" in out.lower()


@patch("wks.cli._call")
def test_cli_config(mock_call):
    """Test wksc config command."""
    mock_call.return_value = {
        "success": True,
        "data": {"mongo": {"uri": "mongodb://localhost"}},
        "messages": [],
    }
    rc, _out, _err = run_cli(["config"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_config")


@patch("wks.cli._call")
def test_cli_transform_file_not_found(mock_call, tmp_path):
    """Test wksc transform with non-existent file returns 2."""
    nonexistent = tmp_path / "nonexistent.pdf"
    rc, _out, err = run_cli(["transform", "docling", str(nonexistent)])
    assert rc == 2
    assert "File not found" in err
    mock_call.assert_not_called()


@patch("wks.cli._call")
def test_cli_transform_success(mock_call, tmp_path):
    """Test wksc transform success."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    mock_call.return_value = {"success": True, "data": {"checksum": "abc123"}, "messages": []}

    rc, out, _err = run_cli(["transform", "docling", str(test_file)])
    assert rc == 0
    assert "abc123" in out
    mock_call.assert_called_once()


@patch("wks.cli._call")
def test_cli_transform_error(mock_call, tmp_path):
    """Test wksc transform with error."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    mock_call.return_value = {
        "success": False,
        "messages": [{"type": "error", "text": "Transform failed"}],
    }

    rc, _out, err = run_cli(["transform", "docling", str(test_file)])
    assert rc == 1
    assert "error:" in err.lower() or "Transform failed" in err


@patch("wks.cli._call")
def test_cli_cat_success(mock_call):
    """Test wksc cat success."""
    mock_call.return_value = {"success": True, "data": {"content": "file content"}, "messages": []}
    rc, out, _err = run_cli(["cat", "checksum123"])
    assert rc == 0
    assert "file content" in out
    mock_call.assert_called_once_with("wksm_cat", {"target": "checksum123"})


@patch("wks.cli._call")
def test_cli_cat_with_output(mock_call, tmp_path):
    """Test wksc cat with --output flag."""
    output_file = tmp_path / "output.md"
    mock_call.return_value = {"success": True, "data": {"content": "file content"}, "messages": []}
    rc, _out, err = run_cli(["cat", "checksum123", "--output", str(output_file)])
    assert rc == 0
    assert "Saved to" in err
    assert output_file.read_text() == "file content"


@patch("wks.cli._call")
def test_cli_cat_error(mock_call):
    """Test wksc cat with error."""
    mock_call.return_value = {
        "success": False,
        "messages": [{"type": "error", "text": "Not found"}],
    }
    rc, _out, err = run_cli(["cat", "bad_checksum"])
    assert rc == 1
    assert "error:" in err.lower() or "Not found" in err


@patch("wks.cli._call")
def test_cli_diff_success(mock_call):
    """Test wksc diff success."""
    mock_call.return_value = {"success": True, "data": {"diff": "diff output"}, "messages": []}
    rc, out, _err = run_cli(["diff", "unified", "file1", "file2"])
    assert rc == 0
    assert "diff output" in out
    mock_call.assert_called_once_with("wksm_diff", {"engine": "unified", "target_a": "file1", "target_b": "file2"})


@patch("wks.cli._call")
def test_cli_diff_error(mock_call):
    """Test wksc diff with error."""
    mock_call.return_value = {
        "success": False,
        "messages": [{"type": "error", "text": "Diff failed"}],
    }
    rc, _out, err = run_cli(["diff", "unified", "file1", "file2"])
    assert rc == 1
    assert "error:" in err.lower() or "Diff failed" in err


@patch("wks.cli._call")
def test_cli_monitor_status(mock_call):
    """Test wksc monitor status."""
    mock_call.return_value = {"success": True, "data": {"status": "ok"}, "messages": []}
    rc, _out, _err = run_cli(["monitor", "status"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_status")


@patch("wks.cli._call")
def test_cli_monitor_check(mock_call):
    """Test wksc monitor check."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["monitor", "check", "/some/path"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_check", {"path": "/some/path"})


@patch("wks.cli._call")
def test_cli_monitor_validate_with_issues(mock_call):
    """Test wksc monitor validate with issues returns 1."""
    mock_call.return_value = {"success": True, "issues": ["issue1"], "messages": []}
    rc, _out, _err = run_cli(["monitor", "validate"])
    assert rc == 1
    mock_call.assert_called_once_with("wksm_monitor_validate")


@patch("wks.cli._call")
def test_cli_monitor_validate_no_issues(mock_call):
    """Test wksc monitor validate with no issues returns 0."""
    mock_call.return_value = {"success": True, "issues": [], "messages": []}
    rc, _out, _err = run_cli(["monitor", "validate"])
    assert rc == 0


@patch("wks.cli._call")
def test_cli_monitor_list_operations(mock_call):
    """Test wksc monitor list operations."""
    mock_call.return_value = {"success": True, "data": {"items": []}, "messages": []}

    for list_name in [
        "include_paths",
        "exclude_paths",
        "include_dirnames",
        "exclude_dirnames",
        "include_globs",
        "exclude_globs",
    ]:
        rc, _out, _err = run_cli(["monitor", list_name, "list"])
        assert rc == 0
        mock_call.assert_called_once_with("wksm_monitor_list", {"list_name": list_name})
        mock_call.reset_mock()


@patch("wks.cli._call")
def test_cli_monitor_add(mock_call):
    """Test wksc monitor add operations."""
    mock_call.return_value = {"success": True, "messages": []}
    rc, _out, _err = run_cli(["monitor", "include_paths", "add", "/path"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_add", {"list_name": "include_paths", "value": "/path"})


@patch("wks.cli._call")
def test_cli_monitor_remove(mock_call):
    """Test wksc monitor remove operations."""
    mock_call.return_value = {"success": True, "messages": []}
    rc, _out, _err = run_cli(["monitor", "include_paths", "remove", "/path"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_remove", {"list_name": "include_paths", "value": "/path"})


@patch("wks.cli._call")
def test_cli_monitor_managed_list(mock_call):
    """Test wksc monitor managed list."""
    mock_call.return_value = {"success": True, "data": {"items": []}, "messages": []}
    rc, _out, _err = run_cli(["monitor", "managed", "list"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_managed_list")


@patch("wks.cli._call")
def test_cli_monitor_managed_add(mock_call):
    """Test wksc monitor managed add."""
    mock_call.return_value = {"success": True, "messages": []}
    rc, _out, _err = run_cli(["monitor", "managed", "add", "/path", "5"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_managed_add", {"path": "/path", "priority": 5})


@patch("wks.cli._call")
def test_cli_monitor_managed_remove(mock_call):
    """Test wksc monitor managed remove."""
    mock_call.return_value = {"success": True, "messages": []}
    rc, _out, _err = run_cli(["monitor", "managed", "remove", "/path"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_managed_remove", {"path": "/path"})


@patch("wks.cli._call")
def test_cli_monitor_managed_set_priority(mock_call):
    """Test wksc monitor managed set-priority."""
    mock_call.return_value = {"success": True, "messages": []}
    rc, _out, _err = run_cli(["monitor", "managed", "set-priority", "/path", "10"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_monitor_managed_set_priority", {"path": "/path", "priority": 10})


@patch("wks.cli._call")
def test_cli_vault_status(mock_call):
    """Test wksc vault status."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "status"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_status")


@patch("wks.cli._call")
def test_cli_vault_sync(mock_call):
    """Test wksc vault sync."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "sync"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_sync", {"batch_size": 1000})


@patch("wks.cli._call")
def test_cli_vault_sync_with_batch_size(mock_call):
    """Test wksc vault sync with --batch-size."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "sync", "--batch-size", "500"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_sync", {"batch_size": 500})


@patch("wks.cli._call")
def test_cli_vault_validate(mock_call):
    """Test wksc vault validate."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "validate"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_validate")


@patch("wks.cli._call")
def test_cli_vault_fix_symlinks(mock_call):
    """Test wksc vault fix-symlinks."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "fix-symlinks"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_fix_symlinks")


@patch("wks.cli._call")
def test_cli_vault_links(mock_call):
    """Test wksc vault links."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "links", "/path/to/file.md"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_links", {"file_path": "/path/to/file.md", "direction": "both"})


@patch("wks.cli._call")
def test_cli_vault_links_with_direction(mock_call):
    """Test wksc vault links with --direction."""
    mock_call.return_value = {"success": True, "data": {}, "messages": []}
    rc, _out, _err = run_cli(["vault", "links", "/path/to/file.md", "--direction", "to"])
    assert rc == 0
    mock_call.assert_called_once_with("wksm_vault_links", {"file_path": "/path/to/file.md", "direction": "to"})


@patch("wks.cli._call")
def test_cli_out_with_string(mock_call):  # noqa: ARG001
    """Test _out function with non-dict (string) output."""
    import wks.cli
    from wks.cli import _out
    from wks.display.cli import CLIDisplay

    # Set the global display object
    wks.cli.display_obj_global = CLIDisplay()

    out_buf = io.StringIO()
    with redirect_stdout(out_buf):
        _out("plain string")
    assert "plain string" in out_buf.getvalue()

    # Clean up
    wks.cli.display_obj_global = None


@patch("wks.cli._call")
def test_cli_err_with_error_messages(mock_call):  # noqa: ARG001
    """Test _err function with error messages."""
    from wks.cli import _err

    err_buf = io.StringIO()
    result = {
        "success": False,
        "messages": [
            {"type": "error", "text": "Error message 1"},
            {"type": "warning", "text": "Warning message"},
        ],
    }

    with redirect_stderr(err_buf):
        rc = _err(result)

    assert rc == 1
    err_output = err_buf.getvalue()
    assert "error:" in err_output.lower()
    assert "Error message 1" in err_output


@patch("wks.cli._call")
def test_cli_keyboard_interrupt(mock_call):
    """Test CLI handles KeyboardInterrupt."""
    mock_call.side_effect = KeyboardInterrupt()

    # Use a real command that will trigger _call
    rc, _out, _err = run_cli(["config"])
    assert rc == 130


@patch("wks.cli._call")
def test_cli_exception_handling(mock_call):
    """Test CLI handles general exceptions."""
    mock_call.side_effect = ValueError("Test error")

    err_buf = io.StringIO()
    with redirect_stderr(err_buf):
        rc, _out, err = run_cli(["config"])

    assert rc == 1
    assert "Error:" in err


@patch("wks.cli.subprocess.check_output")
def test_cli_version_with_git_sha(mock_check_output):
    """Test --version flag includes git SHA when available."""
    mock_check_output.return_value = b"abc123\n"

    rc, out, _ = run_cli(["--version"])
    assert rc == 0
    # Should contain version and git SHA
    assert "wksc" in out
    assert "abc123" in out


@patch("wks.cli.subprocess.check_output")
def test_cli_version_without_git_sha(mock_check_output):
    """Test --version flag handles git exception gracefully."""
    mock_check_output.side_effect = Exception("git not available")

    rc, out, _ = run_cli(["--version"])
    assert rc == 0
    # Should still show version without git SHA
    assert "wksc" in out


@patch("wks.cli.proxy_stdio_to_socket")
@patch("wks.cli.mcp_socket_path")
def test_cli_mcp_run_with_proxy(mock_socket_path, mock_proxy, tmp_path):
    """Test wksc mcp run with proxy (not --direct)."""
    mock_socket_path.return_value = tmp_path / "socket"
    mock_proxy.return_value = True  # Proxy succeeds

    rc, _out, _err = run_cli(["mcp", "run"])
    assert rc == 0
    mock_proxy.assert_called_once()


@patch("wks.cli.proxy_stdio_to_socket")
@patch("wks.mcp_server.main")
def test_cli_mcp_run_direct(mock_mcp_main, mock_proxy):
    """Test wksc mcp run --direct bypasses proxy."""
    mock_proxy.return_value = False

    rc, _out, _err = run_cli(["mcp", "run", "--direct"])
    assert rc == 0
    mock_mcp_main.assert_called_once()
    # Proxy should not be called when --direct
    mock_proxy.assert_not_called()


@patch("wks.mcp_setup.install_mcp_configs")
def test_cli_mcp_install(mock_install):
    """Test wksc mcp install command."""
    from wks.mcp_setup import InstallResult

    mock_install.return_value = [InstallResult("cursor", Path("/path/to/cursor"), "created", "Registered MCP server")]

    rc, out, _err = run_cli(["mcp", "install", "--client", "cursor"])
    assert rc == 0
    mock_install.assert_called_once_with(clients=["cursor"], command_override=None)
    assert "[cursor]" in out or "[CURSOR]" in out.upper()


@patch("wks.mcp_setup.install_mcp_configs")
def test_cli_mcp_install_with_command_path(mock_install):
    """Test wksc mcp install with --command-path."""
    from wks.mcp_setup import InstallResult

    mock_install.return_value = [
        InstallResult("cursor", Path("/path/to/cursor"), "updated", "Updated MCP server entry")
    ]

    rc, _out, _err = run_cli(["mcp", "install", "--client", "cursor", "--command-path", "/custom/path"])
    assert rc == 0
    mock_install.assert_called_once_with(clients=["cursor"], command_override="/custom/path")


@patch("wks.mcp_setup.install_mcp_configs")
def test_cli_mcp_install_multiple_clients(mock_install):
    """Test wksc mcp install with multiple clients."""
    from wks.mcp_setup import InstallResult

    mock_install.return_value = [
        InstallResult("cursor", Path("/path/to/cursor"), "created", ""),
        InstallResult("claude", Path("/path/to/claude"), "updated", ""),
    ]

    rc, _out, _err = run_cli(["mcp", "install", "--client", "cursor", "--client", "claude"])
    assert rc == 0
    mock_install.assert_called_once_with(clients=["cursor", "claude"], command_override=None)
