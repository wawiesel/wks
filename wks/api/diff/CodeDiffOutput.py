"""Code diff output dataclass."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodeDiffOutput:
    """Structured code diff output."""

    structured_changes: list[dict[str, Any]]
