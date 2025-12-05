"""Config Typer app that registers all config commands."""

import typer

config_app = typer.Typer(
    name="config",
    help="Configuration operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
