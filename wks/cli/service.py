"""Service Typer app factory."""

from pathlib import Path

import typer

from wks.api.service.cmd_install import cmd_install
from wks.api.service.cmd_start import cmd_start
from wks.api.service.cmd_status import cmd_status
from wks.api.service.cmd_stop import cmd_stop
from wks.api.service.cmd_uninstall import cmd_uninstall
from wks.cli._handle_stage_result import _handle_stage_result


def service() -> typer.Typer:
    """Create and configure the service Typer app."""
    app = typer.Typer(
        name="service",
        help="System service install/uninstall",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Service operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="status")
    def status_cmd() -> None:
        """Check service status."""
        _handle_stage_result(cmd_status)()

    @app.command(name="start")
    def start_cmd() -> None:
        """Start service."""
        _handle_stage_result(cmd_start)()

    @app.command(name="stop")
    def stop_cmd() -> None:
        """Stop service."""
        _handle_stage_result(cmd_stop)()

    @app.command(name="install")
    def install_cmd(
        restrict: Path | None = typer.Option(  # noqa: B008
            None, "--restrict", help="Restrict monitoring to this directory"
        ),
    ) -> None:
        """Install system service."""
        _handle_stage_result(cmd_install)(restrict_dir=restrict)

    @app.command(name="uninstall")
    def uninstall_cmd() -> None:
        """Uninstall system service."""
        _handle_stage_result(cmd_uninstall)()

    return app
