"""Config Typer app factory."""

import typer

from wks.api.config.cmd_list import cmd_list
from wks.api.config.cmd_show import cmd_show
from wks.api.config.cmd_version import cmd_version
from wks.cli._handle_stage_result import _handle_stage_result


def config() -> typer.Typer:
    """Create and configure the config Typer app."""
    app = typer.Typer(
        name="config",
        help="Configuration operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Show help when no subcommand is provided."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=False)
            raise typer.Exit()

    @app.command(name="list")
    def list_cmd() -> None:
        """List configuration."""
        _handle_stage_result(cmd_list)()

    @app.command(name="show")
    def show_cmd(
        section: str = typer.Argument(..., help="Configuration section name"),
    ) -> None:
        """Show configuration for a specific section."""
        _handle_stage_result(cmd_show)(section)

    @app.command(name="version")
    def version_cmd() -> None:
        """Show WKS version information."""
        _handle_stage_result(cmd_version)()

    return app
