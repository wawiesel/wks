"""Diff Typer app that registers all diff commands."""

import typer

diff_app = typer.Typer(
    name="diff",
    help="Diff operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
