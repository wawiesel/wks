"""Config Typer app that registers all config commands."""

import typer

from ..base import handle_stage_result
from .cmd_show import cmd_show

config_app = typer.Typer(
    name="config",
    help="Configuration operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@config_app.callback(invoke_without_command=True)
def config_callback(
    ctx: typer.Context,
    section: str | None = typer.Argument(None, help="Configuration section name (e.g., 'monitor', 'db', 'vault')"),
) -> None:
    """Show configuration sections or a specific section.
    
    Usage:
        wksc config              # List all section names
        wksc config <section>   # Show config for a specific section
    """
    if ctx.invoked_subcommand is None:
        # Handle the command directly
        wrapped = handle_stage_result(cmd_show)
        wrapped(section)

