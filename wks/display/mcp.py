"""MCP display implementation - JSON output only."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import Display


def _now_iso() -> str:
    """Return an ISO8601 timestamp in UTC with trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MCPDisplay(Display):
    """JSON-based display for MCP integration."""

    def __init__(self):
        self._output_buffer = []  # Collect all outputs
        self._progress_states = {}  # Track progress state by handle

    def _output(self, data: Dict[str, Any]) -> None:
        """Output JSON to stdout."""
        print(json.dumps(data), flush=True)

    def status(self, message: str, **kwargs) -> None:
        """Output status as JSON."""
        self._output({"type": "status", "message": message, "timestamp": _now_iso()})

    def success(self, message: str, **kwargs) -> None:
        """Output success as JSON."""
        output = {"type": "success", "message": message, "timestamp": _now_iso()}
        if "data" in kwargs:
            output["data"] = kwargs["data"]
        self._output(output)

    def error(self, message: str, **kwargs) -> None:
        """Output error as JSON."""
        output = {"type": "error", "message": message, "timestamp": _now_iso()}
        if "details" in kwargs:
            output["details"] = kwargs["details"]
        self._output(output)

    def warning(self, message: str, **kwargs) -> None:
        """Output warning as JSON."""
        self._output({"type": "warning", "message": message, "timestamp": _now_iso()})

    def info(self, message: str, **kwargs) -> None:
        """Output info as JSON."""
        self._output({"type": "info", "message": message, "timestamp": _now_iso()})

    def table(self, data: List[Dict[str, Any]], headers: Optional[List[str]] = None, **kwargs) -> None:
        """Output table data as JSON array."""
        output = {"type": "table", "data": data, "timestamp": _now_iso()}
        if headers:
            output["headers"] = headers
        if "title" in kwargs:
            output["title"] = kwargs["title"]
        self._output(output)

    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:
        """Record progress start (MCP doesn't show live progress)."""
        handle = id(self)  # Simple handle
        self._progress_states[handle] = {"total": total, "current": 0, "description": description}
        return handle

    def progress_update(self, handle: Any, advance: int = 1, **kwargs) -> None:
        """Update progress state (not output, just tracking)."""
        if handle in self._progress_states:
            self._progress_states[handle]["current"] += advance
            if "description" in kwargs:
                self._progress_states[handle]["description"] = kwargs["description"]

    def progress_finish(self, handle: Any, **kwargs) -> None:
        """Output final progress state."""
        if handle in self._progress_states:
            state = self._progress_states[handle]
            self._output(
                {
                    "type": "progress_complete",
                    "total": state["total"],
                    "completed": state["current"],
                    "description": state["description"],
                    "timestamp": _now_iso(),
                }
            )
            del self._progress_states[handle]

    def spinner_start(self, description: str = "", **kwargs) -> Any:
        """Record spinner start (MCP doesn't show spinners)."""
        handle = id(self) + 1000  # Different from progress handles
        return handle

    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:
        """No-op for MCP (spinners not shown)."""
        pass

    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:
        """Output completion message if provided."""
        if message:
            self.status(message)

    def tree(self, data: Dict[str, Any], title: str = "", **kwargs) -> None:
        """Output tree data as nested JSON."""
        output = {"type": "tree", "data": data, "timestamp": _now_iso()}
        if title:
            output["title"] = title
        self._output(output)

    def json_output(self, data: Any, **kwargs) -> None:
        """Output structured data (primary method for MCP)."""
        self._output({"type": "data", "data": data, "timestamp": _now_iso()})

    def panel(self, content: str, title: str = "", **kwargs) -> None:
        """Output panel content as simple JSON."""
        output = {"type": "panel", "content": content, "timestamp": _now_iso()}
        if title:
            output["title"] = title
        self._output(output)
