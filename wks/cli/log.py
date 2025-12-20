"""Log Typer app that registers log commands."""

import typer

from wks.api.log.cmd_prune import cmd_prune
from wks.api.log.cmd_status import cmd_status
from wks.cli._handle_stage_result import handle_stage_result

log_app = typer.Typer(
    name="log",
    help="Log management",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@log_app.callback(invoke_without_command=True)
def log_callback(ctx: typer.Context) -> None:
    """Log operations - shows available commands."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()


def prune_command(
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


def status_command() -> None:
    """Show log file status (auto-prunes expired entries)."""
    handle_stage_result(cmd_status)()


log_app.command(name="prune")(prune_command)
log_app.command(name="status")(status_command)
