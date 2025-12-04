"""DB Typer app that registers all database commands."""

import typer

db_app = typer.Typer(
    name="db",
    help="Database operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
