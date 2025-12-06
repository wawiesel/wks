"""Utilities for formatting data for display."""

from typing import Any


def data_to_tables(data: Any) -> list[dict[str, Any]]:
    """Convert any data structure into a list of table structures.

    This function automatically transforms common data structures into
    table format suitable for CLI display. It handles:
    - List of dicts → single table
    - Single dict → key-value table
    - Dict with nested lists/dicts → multiple tables
    - Lists of simple values → single-column table

    Args:
        data: Any data structure to convert

    Returns:
        List of table structures, each with:
        - "data": list[dict[str, Any]] - table rows
        - "headers": list[str] - column headers
        - "title": str - optional table title
    """
    tables: list[dict[str, Any]] = []

    if data is None:
        return tables

    # If it's already a list of table structures, return as-is
    if isinstance(data, list) and data and isinstance(data[0], dict) and "data" in data[0] and "headers" in data[0]:
        return data

    # List of dicts → single table
    if isinstance(data, list) and data and isinstance(data[0], dict) and all(isinstance(item, dict) for item in data):
        # Check if it's already table data (has consistent keys)
        headers = list(data[0].keys())
        tables.append(
            {
                "data": data,
                "headers": headers,
            }
        )
        return tables

    # List of simple values → single-column table
    if isinstance(data, list) and data and not isinstance(data[0], dict):
        tables.append(
            {
                "data": [{"Value": str(item)} for item in data],
                "headers": ["Value"],
            }
        )
        return tables

    # Single dict → key-value table
    if isinstance(data, dict):
        # Check if dict values are lists (nested structures)
        has_nested_lists = any(isinstance(v, list) for v in data.values() if v is not None)
        has_nested_dicts = any(isinstance(v, dict) for v in data.values() if v is not None)

        if has_nested_lists or has_nested_dicts:
            # Create separate tables for nested structures
            simple_data = []
            for key, value in data.items():
                if isinstance(value, list) and value:
                    # Create a table for this list
                    if isinstance(value[0], dict):
                        # List of dicts
                        headers = list(value[0].keys())
                        tables.append(
                            {
                                "data": value,
                                "headers": headers,
                                "title": _format_title(key),
                            }
                        )
                    else:
                        # List of simple values
                        tables.append(
                            {
                                "data": [{"Value": str(item)} for item in value],
                                "headers": ["Value"],
                                "title": _format_title(key),
                            }
                        )
                elif isinstance(value, dict):
                    # Nested dict - create key-value table
                    nested_rows = [{"Key": k, "Value": _format_value(v)} for k, v in value.items()]
                    tables.append(
                        {
                            "data": nested_rows,
                            "headers": ["Key", "Value"],
                            "title": _format_title(key),
                        }
                    )
                else:
                    # Simple key-value pair
                    simple_data.append({"Key": key, "Value": _format_value(value)})

            # Add simple key-value pairs as a table if any
            if simple_data:
                tables.append(
                    {
                        "data": simple_data,
                        "headers": ["Key", "Value"],
                    }
                )
        else:
            # Simple key-value dict → single table
            rows = [{"Key": k, "Value": _format_value(v)} for k, v in data.items()]
            tables.append(
                {
                    "data": rows,
                    "headers": ["Key", "Value"],
                }
            )

    return tables


def _format_title(key: str) -> str:
    """Format a key into a readable table title."""
    # Convert snake_case or kebab-case to Title Case
    import re

    # Replace underscores and hyphens with spaces
    title = re.sub(r"[_-]", " ", key)
    # Title case
    return title.title()


def _format_value(value: Any) -> str:
    """Format a value for display in a table cell."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, (dict, list)):
        # For complex types, show a summary
        if isinstance(value, dict):
            return f"{{ {len(value)} items }}"
        if isinstance(value, list):
            return f"[ {len(value)} items ]"
    return str(value)
