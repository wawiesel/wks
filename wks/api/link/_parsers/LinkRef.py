"""Link reference dataclass (UNO: single model)."""

from dataclasses import dataclass


@dataclass
class LinkRef:
    """A reference to a link found in a file."""

    line_number: int
    column_number: int
    raw_target: str
    link_type: str  # "wikilink", "url", "image", "reference", etc.
    alias: str = ""
    is_embed: bool = False
