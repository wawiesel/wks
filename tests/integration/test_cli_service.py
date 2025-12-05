"""CLI tests for service command."""

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
def test_cli_service_status(mock_call):
    """wksc service status should call wksm_service via MCP."""
    mock_call.return_value = {
        "success": True,
        "data": {
            "service": {"running": True},
            "launch_agent": {},
            "notes": [],
        },
        "messages": [],
    }

    rc, _out, _err = run_cli(["service-status"])

    assert rc == 0
    mock_call.assert_called_once_with("wksm_service", {})
    # We don't assert on formatted output here; display layer is tested separately.
