"""CLI tests for db commands (monitor, vault, transform)."""

import io
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.db


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


@patch("wks.api.db.cmd_query.db_query")
def test_cli_db_query_monitor(mock_db_query):
    """wksc db query monitor should query wks.monitor database directly."""
    mock_db_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "query", "monitor"])

    assert rc == 0, f"Expected exit code 0, got {rc}. stdout: {out}, stderr: {err}"
    # projection parameter has default None, so it's not passed (defaults to {"_id": 0} inside function)
    mock_db_query.assert_called_once_with("wks.monitor", None, 50)
    # Output is displayed via display layer; we just ensure something was printed
    assert out.strip() != "" or err.strip() != ""


@patch("wks.api.db.cmd_query.db_query")
def test_cli_db_query_vault(mock_db_query):
    """wksc db query vault should query wks.vault database directly."""
    mock_db_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "query", "vault"])

    assert rc == 0
    mock_db_query.assert_called_once_with("wks.vault", None, 50)
    assert out.strip() != "" or err.strip() != ""


@patch("wks.api.db.cmd_query.db_query")
def test_cli_db_query_transform(mock_db_query):
    """wksc db query transform should query wks.transform database directly."""
    mock_db_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "query", "transform"])

    assert rc == 0
    mock_db_query.assert_called_once_with("wks.transform", None, 50)
    assert out.strip() != "" or err.strip() != ""


@patch("wks.api.db.cmd_query.db_query")
def test_cli_db_query_with_wks_prefix(mock_db_query):
    """wksc db query with wks. prefix should work (no double prefix)."""
    mock_db_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "query", "wks.custom"])

    assert rc == 0
    mock_db_query.assert_called_once_with("wks.custom", None, 50)
    assert out.strip() != "" or err.strip() != ""
