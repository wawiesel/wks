"""Status Typer app factory - top-level system status."""

import typer
from rich import print

from wks.api.cmd_status import cmd_status
from wks.cli._handle_stage_result import _handle_stage_result


def status() -> typer.Typer:
    """Create and configure the status Typer app."""
    app = typer.Typer(
        name="status",
        help="Show system status summary",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        """Show aggregated system status."""
        if ctx.invoked_subcommand is not None:
            return

        def status_printer(output: dict) -> None:
            svc = output.get("service", {})
            log = output.get("log", {})
            mon = output.get("monitor", {})
            lnk = output.get("link", {})
            vlt = output.get("vault", {})

            # Service line
            if "error" in svc:
                print(f"[bold]Service:[/bold]  [red]{svc['error']}[/red]")
            elif svc.get("running"):
                details = []
                if svc.get("pid"):
                    details.append(f"PID {svc['pid']}")
                if svc.get("installed"):
                    details.append("installed via launchd")
                detail_str = f" ({', '.join(details)})" if details else ""
                print(f"[bold]Service:[/bold]  [green]running[/green]{detail_str}")
            elif svc.get("installed"):
                print("[bold]Service:[/bold]  [yellow]installed but not running[/yellow]")
            else:
                print("[bold]Service:[/bold]  [dim]not installed[/dim]")

            # Log line
            if "error" in log:
                print(f"[bold]Logfile:[/bold]  [red]{log['error']}[/red]")
            else:
                counts = log.get("entry_counts", {})
                total = sum(counts.values())
                errors = counts.get("error", 0)
                warnings = counts.get("warn", 0)
                parts = [f"{total} entries"]
                if errors:
                    parts.append(f"[red]{errors} errors[/red]")
                else:
                    parts.append("0 errors")
                if warnings:
                    parts.append(f"[yellow]{warnings} warnings[/yellow]")
                else:
                    parts.append("0 warnings")
                print(f"[bold]Logfile:[/bold]  {', '.join(parts)}")

            # Monitor line
            if "error" in mon:
                print(f"[bold]Monitor:[/bold]  [red]{mon['error']}[/red]")
            else:
                tracked = mon.get("tracked_files", 0)
                last_sync = mon.get("last_sync")
                sync_str = f", last sync {last_sync}" if last_sync else ""
                print(f"[bold]Monitor:[/bold]  {tracked} tracked files{sync_str}")

            # Links line
            if "error" in lnk:
                print(f"[bold]Links:[/bold]    [red]{lnk['error']}[/red]")
            else:
                total_links = lnk.get("total_links", 0)
                total_files = lnk.get("total_files", 0)
                print(f"[bold]Links:[/bold]    {total_links} links across {total_files} files")

            # Vault line
            if "error" in vlt:
                print(f"[bold]Vault:[/bold]    [red]{vlt['error']}[/red]")
            else:
                total_links = vlt.get("total_links", 0)
                print(f"[bold]Vault:[/bold]    {total_links} edges indexed")

        _handle_stage_result(cmd_status, result_printer=status_printer, suppress_output=True)()

    return app
