"""Config Typer app factory."""

import typer

from wks.api.config.cmd_list import cmd_list
from wks.api.config.cmd_set import cmd_set
from wks.api.config.cmd_show import cmd_show
from wks.api.config.cmd_version import cmd_version
from wks.cli._app_factory import build_typer_app, require_subcommand
from wks.cli._handle_stage_result import _handle_stage_result


def config() -> typer.Typer:
    """Create and configure the config Typer app."""
    app = build_typer_app(name="config", help_text="Configuration operations")
    require_subcommand(app, err=False)

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

    @app.command(name="set")
    def set_cmd(
        key: str = typer.Argument(..., help="Dot-path key (e.g. monitor.max_documents)"),
        value: str = typer.Argument("", help="Value (JSON-parsed, e.g. 500000, '\"hello\"', '[1,2]')"),
        delete: bool = typer.Option(False, "--delete", help="Remove the key instead of setting it"),
    ) -> None:
        """Set, modify, or remove a config value."""
        _handle_stage_result(cmd_set)(key, value, delete=delete)

    @app.command(name="version")
    def version_cmd() -> None:
        """Show WKS version information."""
        _handle_stage_result(cmd_version)()

    return app
