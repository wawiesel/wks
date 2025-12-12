"""Locate the Typer app for a domain."""

import importlib
from typing import Any


def get_app(domain: str) -> Any:
    """Auto-discover Typer app for a domain by trying common naming patterns."""
    patterns = [f"{domain}_app", "db_app" if domain == "database" else None, f"{domain}app", "app"]
    for pattern in patterns:
        if pattern is None:
            continue
        try:
            module = importlib.import_module(f"wks.cli.{domain}")
            app = getattr(module, pattern, None)
            if app is not None:
                return app
        except Exception:
            continue
    return None
