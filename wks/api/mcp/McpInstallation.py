"""Union of all installation types (UNO: single type)."""

from typing import Annotated

from pydantic import Field

from .McpServersJsonInstall import McpServersJsonInstall

# Union of all installation types - add new types here as they're implemented
McpInstallation = Annotated[
    McpServersJsonInstall,  # Add more types with: Type1 | Type2 | Type3
    Field(discriminator="type"),
]
