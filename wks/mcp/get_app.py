"""Locate the Typer app for a domain."""

import importlib
from typing import Any


def get_app(domain: str) -> Any:
    """Auto-discover Typer app for a domain by calling its factory function.

    Each CLI domain module exports a factory function matching its name.
    For example: wks.cli.monitor exports monitor() -> typer.Typer
    """
    try:
        module = importlib.import_module(f"wks.cli.{domain}")
        # Factory function matches domain name
        factory = getattr(module, domain, None)
        if factory is not None and callable(factory):
            return factory()
    except Exception:
        pass
    return None
