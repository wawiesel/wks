"""Extract the underlying API function from a Typer command callback (UNO: single function)."""

import importlib
from collections.abc import Callable
from typing import Any


def extract_api_function_from_command(cmd_callback: Callable, cli_module: Any) -> Callable | None:
    """Extract underlying API function from a Typer command callback.

    With factory pattern, callbacks are nested inside the factory function.
    The API functions are in wks.api.{domain}.cmd_{name} modules.
    """
    if hasattr(cmd_callback, "__wrapped__"):
        return cmd_callback.__wrapped__

    # Extract command name from callback name
    callback_name = cmd_callback.__name__.lstrip("_")

    # Handle patterns: status_cmd -> status, status_command -> status
    if callback_name.endswith("_cmd"):
        cmd_name = callback_name[:-4]
    elif callback_name.endswith("_command"):
        cmd_name = callback_name[:-8]
    else:
        cmd_name = callback_name

    # Get domain from cli_module (e.g., wks.cli.monitor -> monitor)
    if not hasattr(cli_module, "__name__"):
        return None
    domain = cli_module.__name__.split(".")[-1]

    # Look for cmd_{name} in API module: wks.api.{domain}.cmd_{cmd_name}
    try:
        api_module = importlib.import_module(f"wks.api.{domain}.cmd_{cmd_name}")
        func = getattr(api_module, f"cmd_{cmd_name}", None)
        if callable(func):
            return func
    except ImportError:
        pass

    # Fallback: look in CLI module (old pattern)
    func_name = f"cmd_{cmd_name}"
    func = getattr(cli_module, func_name, None)
    if callable(func):
        return func

    return None
