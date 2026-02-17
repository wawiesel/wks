"""CLI - main entry point."""

import sys

# Global options that accept a value argument
_GLOBAL_VALUE_OPTS = {"--display", "-d"}
# Global options that are boolean flags
_GLOBAL_FLAG_OPTS = {"--quiet"}


def _hoist_global_options(argv: list[str]) -> list[str]:
    """Move global options (-d, -q) to the front of argv.

    Allows users to write ``wksc monitor status -d json`` instead of
    requiring ``wksc -d json monitor status``.
    """
    hoisted: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in _GLOBAL_VALUE_OPTS and i + 1 < len(argv):
            hoisted.extend([arg, argv[i + 1]])
            i += 2
        elif (arg.startswith(("-d", "--display=")) and "=" in arg) or arg in _GLOBAL_FLAG_OPTS:
            hoisted.append(arg)
            i += 1
        else:
            rest.append(arg)
            i += 1
    return hoisted + rest


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    import click
    import typer

    from wks.cli._create_app import _create_app

    if argv is None:
        argv = sys.argv[1:]

    argv = _hoist_global_options(argv)

    if "--version" in argv or "-v" in argv:
        from wks.api.config.cmd_version import cmd_version

        result = cmd_version()
        list(result.progress_callback(result))
        if result.success:
            print(f"wksc {result.output['version']}")
        else:
            print("wksc: failed to retrieve version", file=sys.stderr)
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
