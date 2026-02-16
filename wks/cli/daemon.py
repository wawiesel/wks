"""Daemon Typer app factory."""

from pathlib import Path

import typer

from wks.api.daemon.cmd_clear import cmd_clear
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop
from wks.cli._handle_stage_result import _handle_stage_result


def daemon() -> typer.Typer:
    """Create and configure the daemon Typer app."""
    app = typer.Typer(
        name="daemon",
        help="Daemon runtime management",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Daemon operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit(2)

    @app.command(name="status")
    def status_cmd() -> None:
        """Check daemon status."""
        _handle_stage_result(cmd_status)()

    @app.command(name="start")
    def start_cmd(
        restrict: Path | None = typer.Option(  # noqa: B008
            None, "--restrict", help="Restrict monitoring to this directory"
        ),
        blocking: bool = typer.Option(False, "--blocking", help="Run in foreground (blocking mode)"),
    ) -> None:
        """Start daemon runtime."""
        _handle_stage_result(cmd_start)(restrict_dir=restrict, blocking=blocking)

    @app.command(name="stop")
    def stop_cmd() -> None:
        """Stop daemon runtime."""
        _handle_stage_result(cmd_stop)()

    @app.command(name="clear")
    def clear_cmd(
        errors_only: bool = typer.Option(False, "--errors-only", help="Only remove ERROR entries from the logfile"),
    ) -> None:
        """Clear daemon logs and state. Use --errors-only while running."""
        _handle_stage_result(cmd_clear)(errors_only=errors_only)

    return app
