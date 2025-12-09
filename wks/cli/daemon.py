"""Daemon Typer app that registers all daemon commands."""

from pathlib import Path

import typer

from wks.api.daemon.cmd_install import cmd_install
from wks.api.daemon.cmd_run import cmd_run
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop
from wks.api.daemon.cmd_uninstall import cmd_uninstall
from wks.cli.handle_stage_result import handle_stage_result

daemon_app = typer.Typer(
    name="daemon",
    help="Daemon service management",
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


# Register commands with StageResult handler
# All daemon commands have no required arguments, so use direct registration
daemon_app.command(name="status")(handle_stage_result(cmd_status))
daemon_app.command(name="start")(handle_stage_result(cmd_start))
daemon_app.command(name="stop")(handle_stage_result(cmd_stop))
@daemon_app.command(name="install")
def daemon_install(restrict: Path | None = typer.Option(None, "--restrict", help="Restrict monitoring to this directory (stored in service config)")) -> None:
    """Install daemon as system service."""
    handle_stage_result(cmd_install)(restrict_dir=restrict)
daemon_app.command(name="uninstall")(handle_stage_result(cmd_uninstall))


@daemon_app.command(name="run")
def daemon_run(restrict: Path | None = typer.Option(None, "--restrict", help="Restrict monitoring to this directory (useful for testing)")) -> None:
    """Run the daemon in the foreground, monitoring filesystem changes.
    
    The daemon runs until interrupted (Ctrl+C). Only one daemon instance can run
    per configuration at a time.
    """
    cmd_run(restrict_dir=restrict)

