"""Edge record model (UNO: single model)."""

from dataclasses import dataclass

from .._constants import DOC_TYPE_LINK
from .identity import identity


@dataclass
class EdgeRecord:
    """Single vault edge with URI-first schema."""

    # Source context
    note_path: str
    from_uri: str
    line_number: int
    column_number: int
    source_heading: str
    raw_line: str

    # Link content
    link_type: str
    raw_target: str
    alias_or_text: str

    # Target resolution (URI-first)
    to_uri: str
    status: str
    parser: str = "vault"
    source_domain: str = "vault"

    @property
    def identity(self) -> str:
        return identity(self.note_path, self.line_number, self.column_number, self.to_uri)

    def to_document(self, seen_at_iso: str) -> dict[str, object]:
        return {
            "_id": self.identity,
            "doc_type": DOC_TYPE_LINK,
            "from_uri": self.from_uri,
            "to_uri": self.to_uri,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "source_heading": self.source_heading,
            "raw_line": self.raw_line,
            "link_type": self.link_type,
            "raw_target": self.raw_target,
            "alias_or_text": self.alias_or_text,
            "status": self.status,
            "parser": self.parser,
            "source_domain": self.source_domain,
            "last_seen": seen_at_iso,
            "last_updated": seen_at_iso,
        }
