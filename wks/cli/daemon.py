"""Daemon Typer app that registers all daemon commands."""

import typer

from wks.cli.handle_stage_result import handle_stage_result
from wks.api.daemon.cmd_install import cmd_install
from wks.api.daemon.cmd_reinstall import cmd_reinstall
from wks.api.daemon.cmd_restart import cmd_restart
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop
from wks.api.daemon.cmd_uninstall import cmd_uninstall

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
daemon_app.command(name="restart")(handle_stage_result(cmd_restart))
daemon_app.command(name="install")(handle_stage_result(cmd_install))
daemon_app.command(name="uninstall")(handle_stage_result(cmd_uninstall))
daemon_app.command(name="reinstall")(handle_stage_result(cmd_reinstall))

