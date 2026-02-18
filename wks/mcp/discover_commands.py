"""Discover API functions by scanning wks/api/ directories."""

import importlib
from collections.abc import Callable
from pathlib import Path


def discover_commands() -> dict[tuple[str, str], Callable]:
    """Auto-discover all API functions by scanning wks/api/.

    Scans for:
      - wks/api/{domain}/cmd_{name}.py  ->  cmd_{name}()  ->  ("domain", "name")
      - wks/api/{domain}/cmd.py         ->  cmd()          ->  ("domain", "domain")
      - wks/api/cmd_{name}.py           ->  cmd_{name}()   ->  ("_root", "name")
    """
    commands: dict[tuple[str, str], Callable] = {}
    api_path = Path(__file__).parent.parent / "api"

    # Domain directories (e.g. wks/api/link/, wks/api/cat/)
    for domain_dir in api_path.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
            continue

        domain = domain_dir.name

        # cmd_{name}.py files -> ("domain", "name")
        for cmd_file in domain_dir.glob("cmd_*.py"):
            cmd_name = cmd_file.stem[4:]  # strip "cmd_"
            func = _import_func(f"wks.api.{domain}.{cmd_file.stem}", f"cmd_{cmd_name}")
            if func:
                commands[(domain, cmd_name)] = func

        # cmd.py (callback-style) -> ("domain", "domain")
        if (domain_dir / "cmd.py").exists():
            func = _import_func(f"wks.api.{domain}.cmd", "cmd")
            if func:
                commands[(domain, domain)] = func

    # Root-level cmd_{name}.py -> ("_root", "name")
    for cmd_file in api_path.glob("cmd_*.py"):
        cmd_name = cmd_file.stem[4:]  # strip "cmd_"
        func = _import_func(f"wks.api.{cmd_file.stem}", f"cmd_{cmd_name}")
        if func:
            commands[("_root", cmd_name)] = func

    return commands


def _import_func(module_path: str, func_name: str) -> Callable | None:
    """Import a function from a module, returning None on failure."""
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        return func if callable(func) else None
    except Exception:
        return None
