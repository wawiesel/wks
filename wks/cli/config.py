"""Config Typer app that registers all config commands."""

import typer

from wks.api.config.cmd_list import cmd_list
from wks.api.config.cmd_show import cmd_show
from wks.api.config.cmd_version import cmd_version
from wks.cli._handle_stage_result import handle_stage_result

config_app = typer.Typer(
    name="config",
    help="Configuration operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context) -> None:
    """Show help when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=False)
        raise typer.Exit()


# Register commands with StageResult handler
def list_command() -> None:
    """List configuration."""
    handle_stage_result(cmd_list)()


config_app.command(name="list")(list_command)


def show_command(
    section: str = typer.Argument(..., help="Configuration section name"),
) -> None:
    """Show configuration for a specific section."""
    handle_stage_result(cmd_show)(section)


def version_command() -> None:
    """Show WKS version information."""
    handle_stage_result(cmd_version)()


config_app.command(name="show")(show_command)
config_app.command(name="version")(version_command)
