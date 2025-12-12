"""Extract the underlying API function from a Typer command callback."""

from collections.abc import Callable
from typing import Any


def extract_api_function_from_command(cmd_callback: Callable, cli_module: Any) -> Callable | None:
    """Extract underlying API function from a Typer command callback."""
    if hasattr(cmd_callback, "__wrapped__"):
        return cmd_callback.__wrapped__

    if hasattr(cli_module, "__dict__"):
        callback_name = cmd_callback.__name__
        if callback_name.endswith("_command"):
            cmd_name = callback_name[:-8]
            func_name = f"cmd_{cmd_name}"
            if hasattr(cli_module, func_name):
                func = getattr(cli_module, func_name)
                if callable(func):
                    return func

    return None
