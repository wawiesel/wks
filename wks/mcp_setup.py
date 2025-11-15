"""Utilities for registering the WKS MCP server with common MCP clients."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


MCP_CONFIG_TARGETS: Dict[str, Path] = {
    "cursor": Path.home() / ".cursor" / "mcp.json",
    "claude": Path.home() / "Library" / "Application Support" / "Claude" / "mcp.json",
    "gemini": Path.home() / ".config" / "gemini" / "mcp.json",
}


@dataclass
class InstallResult:
    """Status for a single MCP client registration attempt."""

    client: str
    path: Path
    status: str
    message: str = ""


def _resolve_command(command_override: Optional[str]) -> tuple[str, List[str]]:
    """Determine the command and args that should launch the MCP server."""
    if command_override:
        cmd_path = Path(command_override).expanduser()
        return str(cmd_path), ["mcp", "run"]

    resolved = shutil.which("wks0")
    if resolved:
        return resolved, ["mcp", "run"]

    # Fall back to the current interpreter + module path.
    return sys.executable, ["-m", "wks.cli", "mcp", "run"]


def _load_config(path: Path) -> tuple[dict, bool, Optional[str]]:
    """Load an MCP config file, backing up invalid JSON if needed."""
    if not path.exists():
        return {}, False, None

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object")
        return data, True, None
    except Exception:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy(path, backup)
        return {}, True, str(backup)


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _register_server(target: Path, command: str, args: List[str]) -> InstallResult:
    data, existed, backup_path = _load_config(target)
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers

    desired = {"command": command, "args": args}
    current = servers.get("wks")

    if current == desired and existed:
        return InstallResult("unknown", target, "unchanged", "already configured")

    servers["wks"] = desired
    _write_config(target, data)
    status = "created" if not existed else "updated"
    message = ""
    if backup_path:
        message = f"Previous config invalid; backed up to {backup_path}"
    return InstallResult("unknown", target, status, message.strip())


def install_mcp_configs(
    *,
    clients: Optional[Iterable[str]] = None,
    command_override: Optional[str] = None,
    targets: Optional[Dict[str, Path]] = None,
) -> List[InstallResult]:
    """Ensure the WKS MCP server is registered for each requested client."""
    available = targets or MCP_CONFIG_TARGETS
    selected = list(clients) if clients else list(available.keys())
    missing = sorted(set(selected) - set(available.keys()))
    if missing:
        raise ValueError(f"Unknown MCP client(s): {', '.join(missing)}")

    command, args = _resolve_command(command_override)
    results: List[InstallResult] = []

    for client in selected:
        path = available[client]
        try:
            result = _register_server(path, command, args)
            result.client = client
        except Exception as exc:  # pragma: no cover
            results.append(
                InstallResult(client, path, "error", f"Failed to update: {exc}")
            )
            continue
        if not result.message:
            if result.status == "created":
                result.message = f"Registered MCP server at {path}"
            elif result.status == "updated":
                result.message = f"Updated MCP server entry at {path}"
            else:
                result.message = "Already up to date"
        results.append(result)

    return results


__all__ = ["install_mcp_configs", "InstallResult", "MCP_CONFIG_TARGETS"]


