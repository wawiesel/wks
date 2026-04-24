from dataclasses import dataclass


@dataclass
class LinkRef:
    line_number: int
    column_number: int
    raw_target: str
    link_type: str  # "wikilink", "url", "image", "reference", etc.
    alias: str = ""
    is_embed: bool = False
