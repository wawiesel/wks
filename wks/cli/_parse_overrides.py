"""Parse command line overrides into a dictionary."""

from typing import Any


def _parse_overrides(args: list[str]) -> dict[str, Any]:
    """Parse extra CLI args into override dict.

    Parses args like ['--key', 'value', '--flag'] into {'key': 'value', 'flag': True}.
    Auto-converts 'true'/'false' to bool and digits to int.
    """
    overrides: dict[str, Any] = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]
            value: Any
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1]
                i += 2
            else:
                value = True
                i += 1

            # Auto-convert types
            if isinstance(value, str):
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)

            overrides[key] = value
        else:
            i += 1
    return overrides
