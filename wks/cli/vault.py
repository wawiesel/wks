"""Vault Typer app factory."""

import typer

from wks.api.vault.cmd_check import cmd_check
from wks.api.vault.cmd_links import cmd_links
from wks.api.vault.cmd_status import cmd_status
from wks.api.vault.cmd_sync import cmd_sync
from wks.cli._handle_stage_result import handle_stage_result


def vault() -> typer.Typer:
    """Create and configure the vault Typer app."""
    app = typer.Typer(
        name="vault",
        help="Vault operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

    @app.command(name="status")
    def status_cmd() -> None:
        """Get vault link health status."""
        handle_stage_result(cmd_status)()

    @app.command(name="sync")
    def sync_cmd(
        path: str | None = typer.Argument(None, help="Path to sync (default: entire vault)"),
        recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively sync directory"),
    ) -> None:
        """Sync vault links to database."""
        handle_stage_result(cmd_sync)(path, recursive=recursive)

    @app.command(name="check")
    def check_cmd(
        path: str | None = typer.Argument(None, help="Path to check (default: entire vault)"),
    ) -> None:
        """Check vault link health."""
        handle_stage_result(cmd_check)(path)

    @app.command(name="links")
    def links_cmd(
        path: str = typer.Argument(..., help="File path to query links for"),
        direction: str = typer.Option("both", "--direction", "-d", help="Direction: to, from, or both"),
    ) -> None:
        """Show edges to/from a specific file."""
        if direction not in ("to", "from", "both"):
            typer.echo(f"Invalid direction: {direction}. Must be 'to', 'from', or 'both'", err=True)
            raise typer.Exit(code=1)
        handle_stage_result(cmd_links)(path, direction)  # type: ignore[arg-type]

    return app
