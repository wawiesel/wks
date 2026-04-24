from typing import Annotated

from pydantic import Field

from .McpServersJsonInstall import McpServersJsonInstall

McpInstallation = Annotated[
    McpServersJsonInstall,  # Add more types with: Type1 | Type2 | Type3
    Field(discriminator="type"),
]
