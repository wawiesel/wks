"""Test that wks/api/*/__init__.py only export Output classes matching cmd_*.py files."""

import importlib
import re
from pathlib import Path

import pytest


def _snake_to_pascal(snake_str: str) -> str:
    """Convert snake_case to PascalCase."""
    components = snake_str.split("_")
    return "".join(word.capitalize() for word in components)


def _get_expected_outputs(domain_dir: Path) -> set[str]:
    """Get expected Output class names from cmd_*.py files in domain directory."""
    expected = set()
    domain_name = domain_dir.name
    domain_pascal = domain_name.capitalize()

    for cmd_file in sorted(domain_dir.glob("cmd_*.py")):
        # Extract command name: cmd_filter_add.py -> filter_add
        match = re.match(r"cmd_(.+)\.py$", cmd_file.name)
        if not match:
            continue
        command_snake = match.group(1)
        command_pascal = _snake_to_pascal(command_snake)
        expected_output = f"{domain_pascal}{command_pascal}Output"
        expected.add(expected_output)

    return expected


def _get_actual_exports(domain_module_path: str) -> set[str]:
    """Get actual exports from domain __init__.py module."""
    try:
        module = importlib.import_module(domain_module_path)
        if hasattr(module, "__all__"):
            return set(module.__all__)
        # If no __all__, check what's actually exported (names not starting with _)
        return {name for name in dir(module) if not name.startswith("_")}
    except ImportError:
        return set()


@pytest.mark.parametrize(
    "domain_name",
    [
        "config",
        "database",
        "daemon",
        "mcp",
        "monitor",
        "service",
        # Add other domains as needed
    ],
)
def test_domain_init_only_exports_matching_output_classes(domain_name: str) -> None:
    """Each wks/api/<domain>/__init__.py SHALL only export <Domain><Command>Output classes matching cmd_*.py files."""
    repo_root = Path(__file__).resolve().parents[2]
    domain_dir = repo_root / "wks" / "api" / domain_name

    if not domain_dir.exists():
        pytest.skip(f"Domain {domain_name} does not exist")

    expected_outputs = _get_expected_outputs(domain_dir)
    if not expected_outputs:
        pytest.skip(f"Domain {domain_name} has no cmd_*.py files")

    domain_module_path = f"wks.api.{domain_name}"
    actual_exports = _get_actual_exports(domain_module_path)

    # Check that all exports are expected Output classes
    unexpected = actual_exports - expected_outputs
    if unexpected:
        pytest.fail(
            f"wks/api/{domain_name}/__init__.py exports unexpected symbols: {unexpected}. "
            f"Only {sorted(expected_outputs)} are allowed (matching cmd_*.py files)."
        )

    # Check that all expected Output classes are exported
    missing = expected_outputs - actual_exports
    if missing:
        pytest.fail(
            f"wks/api/{domain_name}/__init__.py is missing expected exports: {missing}. "
            f"Found exports: {sorted(actual_exports)}."
        )

