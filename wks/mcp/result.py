"""Structured result format for MCP tools.

MCP tools return structured results that include data, errors, warnings, and messages.
CLI consumes these and formats/displays them appropriately.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(Enum):
    """Type of message in MCP result."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    STATUS = "status"
    SUCCESS = "success"


@dataclass
class Message:
    """A single message (error, warning, info, etc.) from an MCP tool."""

    type: MessageType
    text: str
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"type": self.type.value, "text": self.text}
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class MCPResult:
    """
    Structured result from an MCP tool.

    MCP is the source of truth for all errors, warnings, and messages.
    CLI consumes this structure and formats/displays appropriately.

    Attributes:
        success: Whether the operation succeeded
        data: The actual result data (dict)
        messages: List of messages (errors, warnings, info, status)
        log: Optional log entries for debugging (CLI may suppress these)
    """

    success: bool
    data: dict[str, Any]
    messages: list[Message] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def add_error(self, text: str, details: str | None = None) -> None:
        """Add an error message."""
        self.success = False
        self.messages.append(Message(MessageType.ERROR, text, details))

    def add_warning(self, text: str, details: str | None = None) -> None:
        """Add a warning message."""
        self.messages.append(Message(MessageType.WARNING, text, details))

    def add_info(self, text: str, details: str | None = None) -> None:
        """Add an info message."""
        self.messages.append(Message(MessageType.INFO, text, details))

    def add_status(self, text: str, details: str | None = None) -> None:
        """Add a status message."""
        self.messages.append(Message(MessageType.STATUS, text, details))

    def add_success(self, text: str, details: str | None = None) -> None:
        """Add a success message."""
        self.messages.append(Message(MessageType.SUCCESS, text, details))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "data": self.data,
            "messages": [msg.to_dict() for msg in self.messages],
        }
        if self.log:
            result["log"] = self.log
        return result

    @classmethod
    def success_result(cls, data: dict[str, Any], message: str | None = None) -> "MCPResult":
        """Create a successful result."""
        result = cls(success=True, data=data)
        if message:
            result.add_success(message)
        return result

    @classmethod
    def error_result(
        cls, error_text: str, details: str | None = None, data: dict[str, Any] | None = None
    ) -> "MCPResult":
        """Create an error result."""
        result = cls(success=False, data=data or {})
        result.add_error(error_text, details)
        return result
