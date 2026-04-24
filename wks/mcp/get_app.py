import importlib
from typing import Any


def get_app(domain: str) -> Any:
    try:
        module = importlib.import_module(f"wks.cli.{domain}")
        factory = getattr(module, domain, None)
        if factory is not None and callable(factory):
            return factory()
    except Exception:
        pass
    return None
