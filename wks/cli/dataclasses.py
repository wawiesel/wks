"""Data classes for CLI command results."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FileTimings:
    """Timing information for file processing stages."""
    hash: Optional[float] = None
    extract: Optional[float] = None
    embed: Optional[float] = None
    db: Optional[float] = None
    chunks: Optional[float] = None
    obsidian: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class FileSummary:
    """Summary of file processing result."""
    path: Path
    status: str
    timings: FileTimings = field(default_factory=FileTimings)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "path": str(self.path),
            "status": self.status,
            "timings": self.timings.to_dict(),
        }


@dataclass
class DatabaseSummary:
    """Database summary information."""
    database: str
    collection: str
    total_files: int
    total_bytes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        result = {
            "database": self.database,
            "collection": self.collection,
            "total_files": self.total_files,
        }
        if self.total_bytes is not None:
            result["total_bytes"] = self.total_bytes
        return result


@dataclass
class IndexResult:
    """Result of an index operation."""
    mode: str
    requested: List[str]
    added: int
    skipped: int
    errors: int
    files: List[FileSummary]
    database: Optional[DatabaseSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        result = {
            "mode": self.mode,
            "requested": self.requested,
            "added": self.added,
            "skipped": self.skipped,
            "errors": self.errors,
            "files": [f.to_dict() for f in self.files],
        }
        if self.database:
            result["database"] = self.database.to_dict()
        return result

