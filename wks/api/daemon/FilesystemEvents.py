"""Filesystem events dataclass for daemon filesystem monitoring."""

from dataclasses import dataclass, field


@dataclass
class FilesystemEvents:
    """Accumulated filesystem events from daemon monitoring.

    All paths are absolute paths as strings.
    All fields are required - pass empty lists when there are no events.
    """

    modified: list[str] = field(description="Paths of modified files")
    created: list[str] = field(description="Paths of created files")
    deleted: list[str] = field(description="Paths of deleted files")
    moved: list[tuple[str, str]] = field(description="Tuples of (old_path, new_path) for moved files")

    def is_empty(self) -> bool:
        """Check if there are any events."""
        return not (self.modified or self.created or self.deleted or self.moved)

    def total_count(self) -> int:
        """Get total number of events (moves count as 2: delete + create)."""
        return len(self.modified) + len(self.created) + len(self.deleted) + len(self.moved)
