"""Transform Typer app factory."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print

from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.cmd_info import cmd_info
from wks.api.transform.cmd_list import cmd_list
from wks.cli._handle_stage_result import _handle_stage_result
from wks.cli._parse_overrides import _parse_overrides
from wks.cli._resolve_uri_arg import _resolve_uri_arg


def transform() -> typer.Typer:
    """Create and configure the transform Typer app."""
    app = typer.Typer(
        name="transform",
        help="Transform operations",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        engine: Annotated[str | None, typer.Argument(help="Engine name")] = None,
        path: Annotated[str | None, typer.Argument(help="File or URI to transform")] = None,
        output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
        raw: Annotated[bool, typer.Option("--raw", help="Output raw checksum only")] = False,
    ) -> None:
        """Transform a file using specified engine.

        Usage:
          wksc transform <engine> <file> [options]
          wksc transform <engine>           # Show engine help
          wksc transform                    # List available engines
        """
        # No args - show available engines
        if engine is None:

            def list_printer(output_data: dict) -> None:
                engines = output_data["engines"]
                print("[bold]Available engines:[/bold]")
                for name, data in engines.items():
                    print(f"  [cyan]{name}[/cyan] ({data['type']})")
                    print(f"    Supported: {', '.join(data['supported_types'])}")
                print()
                print("[dim]Usage: wksc transform <engine> <file>[/dim]")

            _handle_stage_result(cmd_list, result_printer=list_printer, suppress_output=True)()
            return

        # Engine but no file - show engine info
        if path is None:

            def info_printer(output_data: dict) -> None:
                # Handle error case
                if output_data.get("errors"):
                    for err in output_data["errors"]:
                        print(f"[red]Error: {err}[/red]")
                    return

                engine_name = output_data["engine"]
                config = output_data["config"]
                print(f"[bold]Engine: {engine_name}[/bold]")
                print(f"  Type: {config['type']}")
                print(f"  Supported types: {', '.join(config['supported_types'])}")
                print(f"  Options: {config['options']}")
                print()
                print(f"[dim]Usage: wksc transform {engine_name} <file> [options][/dim]")

            _handle_stage_result(cmd_info, result_printer=info_printer, suppress_output=True)(engine)
            return

        # Both engine and file - run transform
        uri = _resolve_uri_arg(path)
        overrides = _parse_overrides(ctx.args)

        if raw:

            def raw_printer(output_data: dict) -> None:
                print(output_data["checksum"])

            _handle_stage_result(cmd_engine, result_printer=raw_printer, suppress_output=True)(
                engine, uri, overrides, output
            )
        else:
            _handle_stage_result(cmd_engine)(engine, uri, overrides, output)

    return app
