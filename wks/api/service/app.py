"""Service Typer app that registers all service commands."""

import typer

service_app = typer.Typer(
    name="service",
    help="Service operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
