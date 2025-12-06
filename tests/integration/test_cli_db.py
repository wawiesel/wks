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


@patch("wks.api.db.DbCollection.DbCollection.query")
def test_cli_db_show_monitor(mock_query):
    """wksc db show monitor should show monitor collection."""
    mock_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "show", "monitor"])

    assert rc == 0, f"Expected exit code 0, got {rc}. stdout: {out}, stderr: {err}"
    # DbCollection.query is called with collection name without prefix
    mock_query.assert_called_once()
    assert mock_query.call_args[0][1] == "monitor"  # collection name
    # Output is displayed via display layer; we just ensure something was printed
    assert out.strip() != "" or err.strip() != ""


@patch("wks.api.db.DbCollection.DbCollection.query")
def test_cli_db_show_vault(mock_query):
    """wksc db show vault should show vault collection."""
    mock_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "show", "vault"])

    assert rc == 0
    mock_query.assert_called_once()
    assert mock_query.call_args[0][1] == "vault"  # collection name
    assert out.strip() != "" or err.strip() != ""


@patch("wks.api.db.DbCollection.DbCollection.query")
def test_cli_db_show_transform(mock_query):
    """wksc db show transform should show transform collection."""
    mock_query.return_value = {"results": [], "count": 0}

    rc, out, err = run_cli(["db", "show", "transform"])

    assert rc == 0
    mock_query.assert_called_once()
    assert mock_query.call_args[0][1] == "transform"  # collection name
    assert out.strip() != "" or err.strip() != ""
