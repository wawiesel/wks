"""CLI - main entry point."""

import sys


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    import click
    import typer

    from wks.cli._create_app import _create_app

    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        from wks.api.config.cmd_version import cmd_version

        result = cmd_version()
        list(result.progress_callback(result))
        if result.success:
            full_version = result.output.get("full_version", result.output.get("version", "unknown"))
            print(f"wksc {full_version}")
        else:
            print(f"wksc {result.output.get('version', 'unknown')}")
        return 0 if result.success else 1

    app = _create_app()
    try:
        app(argv)
        return 0
    except typer.Exit as e:
        return e.exit_code
    except click.exceptions.UsageError as e:
        typer.echo(f"Usage error: {e}", err=True)
        return 1
    except Exception as e:
        typer.echo(f"Unhandled error: {e}", err=True)
        return 1
