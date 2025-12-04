"""Transform Typer app that registers all transform commands."""

import typer

transform_app = typer.Typer(
    name="transform",
    help="Transform operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
