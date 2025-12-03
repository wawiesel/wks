"""CLI tests for db commands (monitor, vault, transform)."""

import io
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


def run_cli(args):
    """Execute CLI command and capture stdout/stderr."""
    from wks.cli import main

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            rc = main(args)
        except SystemExit as exc:  # CLI exits on errors/--version flows
            rc = exc.code if isinstance(exc.code, int) else 0
    return rc, out_buf.getvalue(), err_buf.getvalue()


@patch("wks.cli._call")
def test_cli_db_monitor(mock_call):
    """wksc db monitor should call wksm_db_monitor via MCP."""
    mock_call.return_value = {"success": True, "data": {"results": []}, "messages": []}

    rc, out, err = run_cli(["db", "monitor"])

    assert rc == 0
    mock_call.assert_called_once_with("wksm_db_monitor", {})
    # Output is JSON via display layer; we just ensure something was printed
    assert out.strip() != "" or err.strip() != ""


@patch("wks.cli._call")
def test_cli_db_vault(mock_call):
    """wksc db vault should call wksm_db_vault via MCP."""
    mock_call.return_value = {"success": True, "data": {"results": []}, "messages": []}

    rc, out, err = run_cli(["db", "vault"])

    assert rc == 0
    mock_call.assert_called_once_with("wksm_db_vault", {})
    assert out.strip() != "" or err.strip() != ""


@patch("wks.cli._call")
def test_cli_db_transform(mock_call):
    """wksc db transform should call wksm_db_transform via MCP."""
    mock_call.return_value = {"success": True, "data": {"results": []}, "messages": []}

    rc, out, err = run_cli(["db", "transform"])

    assert rc == 0
    mock_call.assert_called_once_with("wksm_db_transform", {})
    assert out.strip() != "" or err.strip() != ""
