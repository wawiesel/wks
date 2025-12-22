"""Service Typer app that registers service commands."""

from pathlib import Path

import typer

from wks.api.service.cmd_install import cmd_install
from wks.api.service.cmd_start import cmd_start
from wks.api.service.cmd_status import cmd_status
from wks.api.service.cmd_stop import cmd_stop
from wks.api.service.cmd_uninstall import cmd_uninstall
from wks.cli._handle_stage_result import handle_stage_result

service_app = typer.Typer(
    name="service",
    help="System service install/uninstall",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@service_app.callback(invoke_without_command=True)
def _service_callback(ctx: typer.Context) -> None:
    """Service operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


def _status_command() -> None:
    """Check service status."""
    handle_stage_result(cmd_status)()


def _start_command() -> None:
    """Start service."""
    handle_stage_result(cmd_start)()


def _stop_command() -> None:
    """Stop service."""
    handle_stage_result(cmd_stop)()


def _install_command(
    restrict: Path | None = typer.Option(  # noqa: B008
        None, "--restrict", help="Restrict monitoring to this directory"
    ),
) -> None:
    """Install system service."""
    handle_stage_result(cmd_install)(restrict_dir=restrict)


def _uninstall_command() -> None:
    """Uninstall system service."""
    handle_stage_result(cmd_uninstall)()


service_app.command(name="status")(_status_command)
service_app.command(name="start")(_start_command)
service_app.command(name="stop")(_stop_command)
service_app.command(name="install")(_install_command)
service_app.command(name="uninstall")(_uninstall_command)
