"""Transform Typer app factory."""

from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print

from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._get_controller import _get_controller
from wks.api.transform.cmd_transform import cmd_transform
from wks.cli._handle_stage_result import handle_stage_result


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
        file_path: Annotated[Path | None, typer.Argument(help="File to transform")] = None,
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
            _show_engines()
            raise typer.Exit()

        # Engine but no file - show engine info
        if file_path is None:
            _show_engine_info(engine)
            raise typer.Exit()

        # Both engine and file - run transform
        _run_transform(engine, file_path, output, raw, ctx.args)

    return app


def _show_engines() -> None:
    """Show list of available engines from config."""
    try:
        config = WKSConfig.load()
        engines = config.transform.engines

        print("[bold]Available engines:[/bold]")
        for name, engine_config in engines.items():
            engine_type = engine_config.type
            supported = engine_config.supported_types or ["*"]
            print(f"  [cyan]{name}[/cyan] ({engine_type})")
            print(f"    Supported: {', '.join(supported)}")
        print()
        print("[dim]Usage: wksc transform <engine> <file>[/dim]")
    except Exception as e:
        print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1) from None


def _show_engine_info(engine: str) -> None:
    """Show info for a specific engine."""
    try:
        config = WKSConfig.load()
        engines = config.transform.engines

        if engine not in engines:
            print(f"[red]Engine '{engine}' not found.[/red]")
            print(f"[dim]Available: {', '.join(engines.keys())}[/dim]")
            raise typer.Exit(1) from None

        engine_config = engines[engine]
        print(f"[bold]Engine: {engine}[/bold]")
        print(f"  Type: {engine_config.type}")
        print(f"  Supported types: {', '.join(engine_config.supported_types or ['*'])}")
        print(f"  Options: {engine_config.data}")
        print()
        print(f"[dim]Usage: wksc transform {engine} <file> [options][/dim]")
    except typer.Exit:
        raise
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


def _run_transform(
    engine: str,
    file_path: Path,
    output: Path | None,
    raw: bool,
    extra_args: list[str],
) -> None:
    """Run transform with engine and file."""
    # Parse extra args as overrides
    overrides = _parse_overrides(extra_args)

    try:
        if raw:
            with _get_controller() as controller:
                gen = controller.transform(file_path, engine, overrides, output)
                try:
                    while True:
                        next(gen)
                except StopIteration as e:
                    cache_key, _ = e.value
                print(cache_key)
            return

        handle_stage_result(cmd_transform)(engine, file_path, overrides, output)

    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


def _parse_overrides(args: list[str]) -> dict:
    """Parse extra CLI args into override dict."""
    overrides = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]
            value: Any
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1]
                i += 2
            else:
                value = True
                i += 1

            # Auto-convert types
            if isinstance(value, str):
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)

            overrides[key] = value
        else:
            i += 1
    return overrides
