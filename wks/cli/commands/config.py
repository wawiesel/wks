"""Config command implementation."""

import argparse
import json
from typing import Any, Dict, List

from ...config import get_config_path
from ...display.context import get_display


def _format_config_value(value: Any) -> str:
    """Format a config value for display."""
    if isinstance(value, list):
        if value and isinstance(value[0], str):
            return ", ".join(value)
        return str(value)
    elif isinstance(value, dict):
        return str(value)
    elif isinstance(value, bool):
        return "true" if value else "false"
    else:
        return str(value)


def _add_config_section_items(table_data: List[Dict[str, str]], section_data: Dict[str, Any]) -> None:
    """Add items from a config section to table data."""
    for key, value in sorted(section_data.items()):
        if isinstance(value, dict):
            # Nested dict - add as subsection
            table_data.append({"Key": f"  {key}", "Value": ""})
            for subkey, subvalue in sorted(value.items()):
                if isinstance(subvalue, dict):
                    # Deeply nested - show as string
                    table_data.append({"Key": f"    {subkey}", "Value": _format_config_value(subvalue)})
                else:
                    table_data.append({"Key": f"    {subkey}", "Value": _format_config_value(subvalue)})
        else:
            table_data.append({"Key": f"  {key}", "Value": _format_config_value(value)})


def _build_config_table_data(config_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build table data from config with sections."""
    table_data = []

    # Define section order and names (matching SPEC.md architecture)
    sections = [
        ("Monitor", "monitor"),
        ("Vault", "vault"),
        ("DB", "db"),
        ("Extract", "extract"),
        ("Diff", "diff"),
        ("Related", "related"),
        ("Index", "index"),
        ("Search", "search"),
        ("Display", "display"),
    ]

    for section_name, section_key in sections:
        if section_key in config_data:
            # Add section header
            table_data.append({"Key": section_name, "Value": ""})
            _add_config_section_items(table_data, config_data[section_key])

    # Add any remaining top-level keys not in our section list
    known_keys = {key for _, key in sections}
    remaining = {k: v for k, v in config_data.items() if k not in known_keys}
    if remaining:
        table_data.append({"Key": "Other", "Value": ""})
        for key, value in sorted(remaining.items()):
            table_data.append({"Key": f"  {key}", "Value": _format_config_value(value)})

    return table_data


def _style_config_table_data(table_data: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Apply styling to config table data."""
    formatted_data = []
    for row in table_data:
        key = row["Key"]
        value = row["Value"]
        # Style section headers (empty value and not indented)
        if value == "" and not key.startswith("  "):
            formatted_data.append({"Key": f"[bold yellow]{key}[/bold yellow]", "Value": value})
        else:
            formatted_data.append({"Key": key, "Value": value})
    return formatted_data


def show_config(args: argparse.Namespace) -> int:
    """Show config file - table in CLI mode, JSON in MCP mode."""
    # Import from wks.cli to allow monkeypatching in tests
    from ...cli import load_config
    
    config_path = get_config_path()
    display = getattr(args, "display_obj", None) or get_display(getattr(args, "display", None))
    display_mode = getattr(args, "display", None)

    # Load config (allows monkeypatching in tests)
    try:
        config_data = load_config()
    except Exception as e:
        display.error(f"Failed to load config file: {config_path}", details=str(e))
        return 2

    # MCP mode: output raw JSON (not wrapped in MCP format)
    if display_mode == "mcp":
        # Output raw JSON for MCP mode (tests expect this)
        print(json.dumps(config_data, indent=2))
        return 0

    # CLI mode: show as table with sections
    table_data = _build_config_table_data(config_data)
    formatted_data = _style_config_table_data(table_data)

    display.table(
        formatted_data,
        title=f"WKS Configuration ({config_path})",
        column_justify={"Key": "left", "Value": "left"},
        show_header=False
    )

    return 0


def setup_config_parser(subparsers) -> None:
    """Setup config command parser."""
    cfg = subparsers.add_parser("config", help="Show configuration file")
    cfg.set_defaults(func=show_config)

