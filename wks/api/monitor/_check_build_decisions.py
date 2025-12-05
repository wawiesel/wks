"""Build decision trace entries for monitor check."""

from pathlib import Path
from typing import List, Dict


def _check_build_decisions(trace: list[str], path_exists: bool, test_path: Path) -> list[dict[str, str]]:
    """Build decision list from trace messages and path existence."""
    decisions: List[Dict[str, str]] = []
    decisions.append(
        {
            "symbol": "✓" if path_exists else "⚠",
            "message": f"Path exists: {test_path}" if path_exists else f"Path does not exist (checking as if it did): {test_path}",
        }
    )
    for message in trace:
        lower = message.lower()
        if lower.startswith("excluded"):
            symbol = "✗"
        elif "override" in lower or lower.startswith("included"):
            symbol = "✓"
        else:
            symbol = "•"
        decisions.append({"symbol": symbol, "message": message})
    return decisions
