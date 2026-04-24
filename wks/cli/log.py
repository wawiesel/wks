"""Log Typer app factory."""

import typer

from wks.api.log.cmd_prune import cmd_prune
from wks.api.log.cmd_status import cmd_status
from wks.cli._app_factory import build_typer_app, require_subcommand
from wks.cli._handle_stage_result import _handle_stage_result


def log() -> typer.Typer:
    """Create and configure the log Typer app."""
    app = build_typer_app(name="log", help_text="Log management")
    require_subcommand(app)

    @app.command(name="prune")
    def prune_cmd(
        debug: bool = typer.Option(False, "--debug/--no-debug", help="Prune DEBUG entries"),
        info: bool = typer.Option(False, "--info/--no-info", help="Prune INFO entries"),
        warnings: bool = typer.Option(False, "--warnings/--no-warnings", help="Prune WARN entries"),
        errors: bool = typer.Option(False, "--errors/--no-errors", help="Prune ERROR entries"),
    ) -> None:
        """Prune log entries by level.

        At least one level flag must be specified (e.g. --info, --debug).
        """
        if not any([debug, info, warnings, errors]):
            typer.echo("Error: specify at least one level to prune (--debug, --info, --warnings, --errors)", err=True)
            raise typer.Exit(2)
        _handle_stage_result(cmd_prune)(
            prune_debug=debug,
            prune_info=info,
            prune_warnings=warnings,
            prune_errors=errors,
        )

    @app.command(name="status")
    def status_cmd() -> None:
        """Show log file status (auto-prunes expired entries)."""
        _handle_stage_result(cmd_status)()

    return app
