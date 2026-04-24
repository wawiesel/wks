from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodeDiffOutput:
    structured_changes: list[dict[str, Any]]
