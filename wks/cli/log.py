"""Log Typer app factory."""

import typer

from wks.api.log.cmd_prune import cmd_prune
from wks.api.log.cmd_status import cmd_status
from wks.cli._handle_stage_result import handle_stage_result


def log() -> typer.Typer:
    """Create and configure the log Typer app."""
    app = typer.Typer(
        name="log",
        help="Log management",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Log operations - shows available commands."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="prune")
    def prune_cmd(
        debug: bool = typer.Option(True, "--debug/--no-debug", help="Prune DEBUG entries"),
        info: bool = typer.Option(True, "--info/--no-info", help="Prune INFO entries"),
        warnings: bool = typer.Option(False, "--warnings/--no-warnings", help="Prune WARN entries"),
        errors: bool = typer.Option(False, "--errors/--no-errors", help="Prune ERROR entries"),
    ) -> None:
        """Prune log entries by level."""
        handle_stage_result(cmd_prune)(
            prune_debug=debug,
            prune_info=info,
            prune_warnings=warnings,
            prune_errors=errors,
        )

    @app.command(name="status")
    def status_cmd() -> None:
        """Show log file status (auto-prunes expired entries)."""
        handle_stage_result(cmd_status)()

    return app
