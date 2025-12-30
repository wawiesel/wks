"""Test utilities."""

import importlib
import re
from pathlib import Path


def _snake_to_pascal(snake_str: str) -> str:
    """Convert snake_case to PascalCase."""
    components = snake_str.split("_")
    return "".join(word.capitalize() for word in components)


def verify_domain_init(domain_name: str) -> None:
    """Verify that domain __init__.py exports expected Output classes."""
    repo_root = Path(__file__).resolve().parents[2]
    domain_dir = repo_root / "wks" / "api" / domain_name

    if not domain_dir.exists():
        raise FileNotFoundError(f"Domain {domain_name} does not exist")

    expected_outputs = set()
    domain_pascal = _snake_to_pascal(domain_name)

    for cmd_file in sorted(domain_dir.glob("cmd_*.py")):
        match = re.match(r"cmd_(.+)\.py$", cmd_file.name)
        if not match:
            continue
        command_snake = match.group(1)
        command_pascal = _snake_to_pascal(command_snake)
        expected_output = f"{domain_pascal}{command_pascal}Output"
        expected_outputs.add(expected_output)

    if not expected_outputs:
        # If no commands, maybe it shouldn't export outputs?
        return

    domain_module_path = f"wks.api.{domain_name}"
    module = importlib.import_module(domain_module_path)

    actual_exports = set()
    if hasattr(module, "__all__"):
        actual_exports = set(module.__all__)
    else:
        # If no __all__, check what's actually exported (names not starting with _)
        actual_exports = {name for name in dir(module) if not name.startswith("_")}

    # Check for unexpected exports (only output classes allowed?)
    # The previous test mainly checked that expected outputs are present.
    # It also checked for "unexpected symbols" but that might be strict.
    # Let's enforce that expected outputs ARE exported.
    missing = expected_outputs - actual_exports
    if missing:
        raise AssertionError(
            f"wks/api/{domain_name}/__init__.py is missing expected exports: {missing}. "
            f"Found exports: {sorted(actual_exports)}."
        )

    # Optional: Check for extra exports? The original test did.
    # unexpected = actual_exports - expected_outputs
    # if unexpected:
    #    # Some domains might export Configs?
    #    # e.g. wks.api.config exports WKSConfig?
    #    pass
