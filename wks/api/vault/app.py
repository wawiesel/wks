"""Vault Typer app that registers all vault commands."""

import typer

vault_app = typer.Typer(
    name="vault",
    help="Vault operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Commands will be registered here when implemented
