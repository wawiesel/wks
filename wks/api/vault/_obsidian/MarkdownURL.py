"""MarkdownURL model (UNO: single model)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownURL:
    """A parsed markdown URL from markdown."""

    line_number: int
    column_number: int
    url: str
    text: str
