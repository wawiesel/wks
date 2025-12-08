"""Daemon Typer app that registers all daemon commands."""

import typer

from ..handle_stage_result import handle_stage_result
from .cmd_install import cmd_install
from .cmd_reinstall import cmd_reinstall
from .cmd_restart import cmd_restart
from .cmd_start import cmd_start
from .cmd_status import cmd_status
from .cmd_stop import cmd_stop
from .cmd_uninstall import cmd_uninstall

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
def status_command(ctx: typer.Context) -> None:
    """Show daemon status and metrics."""
    wrapped = handle_stage_result(cmd_status)
    wrapped()


def start_command(ctx: typer.Context) -> None:
    """Start daemon."""
    wrapped = handle_stage_result(cmd_start)
    wrapped()


def stop_command(ctx: typer.Context) -> None:
    """Stop daemon."""
    wrapped = handle_stage_result(cmd_stop)
    wrapped()


def restart_command(ctx: typer.Context) -> None:
    """Restart daemon."""
    wrapped = handle_stage_result(cmd_restart)
    wrapped()


def install_command(ctx: typer.Context) -> None:
    """Install daemon as system service."""
    wrapped = handle_stage_result(cmd_install)
    wrapped()


def uninstall_command(ctx: typer.Context) -> None:
    """Uninstall daemon system service."""
    wrapped = handle_stage_result(cmd_uninstall)
    wrapped()


def reinstall_command(ctx: typer.Context) -> None:
    """Reinstall daemon service - uninstalls if exists, then installs."""
    wrapped = handle_stage_result(cmd_reinstall)
    wrapped()


daemon_app.command(name="status")(status_command)
daemon_app.command(name="start")(start_command)
daemon_app.command(name="stop")(stop_command)
daemon_app.command(name="restart")(restart_command)
daemon_app.command(name="install")(install_command)
daemon_app.command(name="uninstall")(uninstall_command)
daemon_app.command(name="reinstall")(reinstall_command)
