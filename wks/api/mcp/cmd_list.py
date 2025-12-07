"""List MCP installations command."""

import json
from pathlib import Path

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.get_config_path import get_config_path


def cmd_list() -> StageResult:
    """List MCP installations.

    Returns:
        StageResult with list of installations and their status
    """
    config_path = get_config_path()
    if not config_path.exists():
        return StageResult(
            announce="Listing MCP installations...",
            result="Configuration file not found",
            output={"installations": [], "count": 0},
            success=False,
        )

    try:
        with config_path.open() as fh:
            config_dict = json.load(fh)
    except Exception as e:
        return StageResult(
            announce="Listing MCP installations...",
            result=f"Error reading config: {e}",
            output={"installations": [], "count": 0, "error": str(e)},
            success=False,
        )

    mcp_config = config_dict.get("mcp", {})
    installs = mcp_config.get("installs", {})

    installations = []
    for name, install_data in installs.items():
        installations.append(
            {
                "name": name,
                "type": install_data.get("type", "unknown"),
                "active": install_data.get("active", False),
                "path": install_data.get("data", {}).get("settings_path", "unknown"),
            }
        )

    return StageResult(
        announce="Listing MCP installations...",
        result=f"Found {len(installations)} installation(s)",
        output={"installations": installations, "count": len(installations)},
        success=True,
    )

