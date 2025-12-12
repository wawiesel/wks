"""Daemon Typer app that registers daemon commands."""

from pathlib import Path

import typer

from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop
from wks.cli.handle_stage_result import handle_stage_result

daemon_app = typer.Typer(
    name="daemon",
    help="Daemon runtime management",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@daemon_app.callback(invoke_without_command=True)
def daemon_callback(ctx: typer.Context) -> None:
    """Daemon operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


def status_command() -> None:
    """Check daemon status."""
    handle_stage_result(cmd_status)()


def start_command(
    restrict: Path | None = typer.Option(None, "--restrict", help="Restrict monitoring to this directory"),
) -> None:
    """Start daemon runtime."""
    handle_stage_result(cmd_start)(restrict_dir=restrict)


def stop_command() -> None:
    """Stop daemon runtime."""
    handle_stage_result(cmd_stop)()


daemon_app.command(name="status")(status_command)
daemon_app.command(name="start")(start_command)
daemon_app.command(name="stop")(stop_command)

