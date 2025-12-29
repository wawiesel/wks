"""Cat Typer app factory - print file or cached content to stdout."""

import mimetypes
import re
from pathlib import Path
from typing import Annotated

import typer

from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform._get_controller import _get_controller


def cat() -> typer.Typer:
    """Create and configure the cat Typer app."""
    app = typer.Typer(
        name="cat",
        help="Print content to stdout (file path or checksum)",
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        invoke_without_command=True,
    )

    @app.callback(invoke_without_command=True)
    def callback(
        ctx: typer.Context,
        target: Annotated[str | None, typer.Argument(help="File path or checksum")] = None,
        engine: Annotated[str | None, typer.Option("--engine", "-e", help="Engine to use")] = None,
    ) -> None:
        """Print content to stdout.

        TARGET can be:
        - A file path: transforms file and prints content
        - A checksum (64 hex chars): prints cached content directly
        """
        if target is None:
            typer.echo(ctx.get_help(), err=True)
            raise typer.Exit()

        _cat_target(target, engine)

    return app


def _is_checksum(target: str) -> bool:
    """Check if target is a 64-character hex checksum."""
    return bool(re.match(r"^[a-f0-9]{64}$", target))


def _get_mime_type(file_path: Path) -> str:
    """Get MIME type for file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def _select_engine(file_path: Path, override: str | None, config: WKSConfig) -> str:
    """Select engine based on MIME type or override."""
    if override:
        return override

    mime_type = _get_mime_type(file_path)
    cat_config = config.cat

    # Check mime_engines mapping
    if hasattr(cat_config, "mime_engines") and cat_config.mime_engines:
        # Exact match
        if mime_type in cat_config.mime_engines:
            return cat_config.mime_engines[mime_type]

        # Wildcard match (e.g., "text/*")
        base_type = mime_type.split("/")[0] + "/*"
        if base_type in cat_config.mime_engines:
            return cat_config.mime_engines[base_type]

    # Fall back to default engine
    return cat_config.default_engine or "cat"


def _cat_target(target: str, engine_override: str | None) -> None:
    """Cat content to stdout - handles both file paths and checksums."""
    try:
        with _get_controller() as controller:
            # Check if target is a checksum
            if _is_checksum(target):
                # Direct checksum lookup
                content = controller.get_content(target)
                typer.echo(content)
                return

            from wks.utils.normalize_path import normalize_path

            file_path = normalize_path(target)

            if not file_path.exists():
                typer.echo(f"Error: File not found: {file_path}", err=True)
                raise typer.Exit(1) from None

            config = WKSConfig.load()
            engine = _select_engine(file_path, engine_override, config)

            # Check if engine exists
            if engine not in config.transform.engines:
                typer.echo(f"Error: Engine '{engine}' not found.", err=True)
                typer.echo(f"Available: {', '.join(config.transform.engines.keys())}", err=True)
                raise typer.Exit(1) from None

            # Transform file (uses cache if available)
            cache_key = controller.transform(file_path, engine, {}, None)

            # Get and print content
            content = controller.get_content(cache_key)
            typer.echo(content)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
