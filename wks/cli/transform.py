"""CLI commands for transform operations."""

from pathlib import Path
from typing import Optional

import typer
from rich import print


from ..api.transform.cmd_show import cmd_show
from ..api.transform.cmd_transform import cmd_transform
from ..api.transform._get_controller import _get_controller
from ._create_app import create_app
from ._handle_stage_result import handle_stage_result
from .display import display_output

app = create_app()


@app.command("transform", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def transform(
    ctx: typer.Context,
    engine: str = typer.Argument(..., help="Engine name defined in config"),
    file_path: Path = typer.Argument(..., help="File to transform"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    display: str = typer.Option("yaml", "--display", help="Output format: yaml or json"),
    raw: bool = typer.Option(False, "--raw", help="Output raw checksum only (for scripting)"),
):
    """Transform a file. Extra flags override engine config."""
    
    # 0. Parse Extra Args
    overrides = {}
    i = 0
    args = ctx.args
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(args) and not args[i+1].startswith("--"):
                value = args[i+1]
                i += 2
            else:
                value = True # Flag usage
                i += 1
            
            # Auto-convert types
            if isinstance(value, str):
                if value.lower() == "true": value = True
                elif value.lower() == "false": value = False
                elif value.isdigit(): value = int(value)
            
            overrides[key] = value
        else:
            i += 1

    try:
        # Scripting Mode: Raw
        if raw:
            # Bypass StageResult/Spinner machinery for pure stdout checksum
            # We use `get_controller` directly here, mirroring `cmd_cat` pattern
            # Note: We duplicate the logic from `cmd_transform`'s inner work 
            # because `cmd_transform` is wrapped in StageResult generator.
            # This is acceptable for the specific bypassing case.
            with _get_controller() as controller:
                cache_key = controller.transform(file_path, engine, overrides, output)
                print(cache_key)
            return

        # Interactive Mode: StageResult
        handle_stage_result(cmd_transform)(engine, file_path, overrides, output)

    except Exception as e:
        # For raw mode, we might want to print to stderr only?
        # But handle_stage_result handles exception display for interactive.
        # Here we just catch simple top-level.
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("show")
def show(
    checksum: str = typer.Argument(..., help="Transform checksum"),
    content: bool = typer.Option(False, "--content", help="Show full content"),
    display: str = typer.Option("yaml", "--display", help="Output format: yaml or json"),
):
    """Show details or content of a transform."""
    handle_stage_result(cmd_show)(checksum, content)


@app.command("cat")
def cat(
    checksum: str = typer.Argument(..., help="Transform checksum"),
):
    """Print the content of a transform to stdout."""
    try:
        with _get_controller() as controller:
            content = controller.get_content(checksum)
        print(content)
    except Exception as e:
        print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
