"""Supported MCP client targets and their native commands."""

from dataclasses import dataclass


@dataclass(frozen=True)
class McpTarget:
    """A supported MCP client target."""

    name: str
    description: str
    install_command: str
    uninstall_command: str


_TARGETS: tuple[McpTarget, ...] = (
    McpTarget(
        name="codex",
        description="OpenAI Codex CLI",
        install_command="codex mcp add wks -- wksm run",
        uninstall_command="codex mcp remove wks",
    ),
    McpTarget(
        name="claude",
        description="Anthropic Claude Code (user scope)",
        install_command="claude mcp add --scope user wks -- wksm run",
        uninstall_command="claude mcp remove --scope user wks",
    ),
    McpTarget(
        name="gemini",
        description="Google Gemini CLI (user scope)",
        install_command="gemini mcp add --scope user wks wksm run",
        uninstall_command="gemini mcp remove --scope user wks",
    ),
)


def list_targets() -> tuple[McpTarget, ...]:
    """Return all supported MCP client targets."""
    return _TARGETS


def get_target(name: str) -> McpTarget | None:
    """Return the named target or None when unsupported."""
    for target in _TARGETS:
        if target.name == name:
            return target
    return None


def target_names() -> tuple[str, ...]:
    """Return the supported target names."""
    return tuple(target.name for target in _TARGETS)
