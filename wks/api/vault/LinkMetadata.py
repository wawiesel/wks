"""Link metadata model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkMetadata:
    """Metadata about a resolved link target.

    URI-first design: target_uri is the canonical identifier.
    Filesystem paths and target_kind can be derived from target_uri and other fields.
    """

    target_uri: str
    status: str

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for backward compatibility."""
        return {
            "target_uri": self.target_uri,
            "status": self.status,
        }
