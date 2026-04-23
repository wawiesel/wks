"""Top-level transform command registration."""

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


def _reject_legacy_positionals(args: list[str]) -> None:
    """Reject leftover positional args from the retired transform CLI."""
    extra_positionals = [arg for arg in args if not arg.startswith("--")]
    if len(extra_positionals) == 0:
        return

    extras = " ".join(extra_positionals)
    raise typer.BadParameter(
        f"Unexpected positional argument(s): {extras}. "
        "The legacy 'wksc transform <engine> <file>' form was removed; use '--engine/-e'."
    )


def _print_engine_list(output_data: dict) -> None:
    """Render the configured transform engines."""
    engines = output_data["engines"]
    default_engine = output_data["default_engine"]
    print("[bold]Available engines:[/bold]")
    print(f"  [green]default[/green]: {default_engine}")
    for name, data in engines.items():
        print(f"  [cyan]{name}[/cyan] ({data['type']})")
        print(f"    Supported: {', '.join(data['supported_types'])}")
    print()
    print("[dim]Usage: wksc transform [-e ENGINE] <file>[/dim]")


def _print_engine_info(output_data: dict) -> None:
    """Render one configured transform engine."""
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
    print(f"[dim]Usage: wksc transform -e {engine_name} <file> [options][/dim]")


def register_transform(app: typer.Typer) -> None:
    """Register the top-level transform command directly on the root app."""

    @app.command(
        name="transform",
        help="Transform operations",
        context_settings={
            "help_option_names": ["-h", "--help"],
            "allow_interspersed_args": True,
            "allow_extra_args": True,
        },
    )
    def transform_cmd(
        ctx: typer.Context,
        path: Annotated[str | None, typer.Argument(help="File or URI to transform")] = None,
        engine: Annotated[str | None, typer.Option("--engine", "-e", help="Configured engine name")] = None,
        output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
        raw: Annotated[bool, typer.Option("--raw", help="Output raw checksum only")] = False,
    ) -> None:
        """Transform a file using a configured engine.

        Usage:
          wksc transform [--raw] [-e ENGINE] <file> [options]
          wksc transform -e <engine>        # Show engine help
          wksc transform                    # List available engines

        Note: --raw and --output must come before <file>.
        """
        if path is None and engine is None:
            _handle_stage_result(cmd_list, result_printer=_print_engine_list, suppress_output=True)()
            return

        if path is None:
            if engine is None:
                raise AssertionError("engine must be set when requesting transform engine info")
            _handle_stage_result(cmd_info, result_printer=_print_engine_info, suppress_output=True)(engine)
            return

        _reject_legacy_positionals(ctx.args)

        from wks.api.config.WKSConfig import WKSConfig

        selected_engine = engine or WKSConfig.load().transform.default_engine
        uri = _resolve_uri_arg(path)
        overrides = _parse_overrides(ctx.args)

        if raw:

            def raw_printer(output_data: dict) -> None:
                print(output_data["checksum"])

            _handle_stage_result(cmd_engine, result_printer=raw_printer, suppress_output=True)(
                selected_engine, uri, overrides, output
            )
            return

        _handle_stage_result(cmd_engine)(selected_engine, uri, overrides, output)
