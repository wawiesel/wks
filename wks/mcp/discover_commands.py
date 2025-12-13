"""Discover Typer command callbacks and their underlying API functions."""

import importlib
from collections.abc import Callable
from pathlib import Path

from .extract_api_function_from_command import extract_api_function_from_command


def discover_commands() -> dict[tuple[str, str], Callable]:
    """Auto-discover all cmd_* functions by scanning CLI Typer apps."""
    commands: dict[tuple[str, str], Callable] = {}
    cli_path = Path(__file__).parent.parent / "cli"

    for cli_file in cli_path.glob("*.py"):
        if cli_file.name.startswith("_") or cli_file.name == "__init__.py":
            continue

        domain = cli_file.stem
        if domain == "display":
            continue

        try:
            cli_module = importlib.import_module(f"wks.cli.{domain}")

            app = None
            patterns = [f"{domain}_app", "db_app" if domain == "database" else None, f"{domain}app", "app"]
            for pattern in patterns:
                if pattern is None:
                    continue
                app = getattr(cli_module, pattern, None)
                if app is not None:
                    break

            if app is None:
                continue

            for cmd in app.registered_commands:
                if cmd.name is None:
                    continue
                api_func = extract_api_function_from_command(cmd.callback, cli_module)
                if api_func:
                    commands[(domain, cmd.name)] = api_func

            if hasattr(app, "registered_groups"):
                for group in app.registered_groups:
                    if not hasattr(group, "typer_instance"):
                        continue
                    sub_app = group.typer_instance
                    prefix = f"{group.name}_"

                    for cmd in sub_app.registered_commands:
                        api_func = extract_api_function_from_command(cmd.callback, cli_module)
                        if api_func:
                            full_cmd_name = f"{prefix}{cmd.name}"
                            commands[(domain, full_cmd_name)] = api_func

        except Exception:
            continue

    return commands
