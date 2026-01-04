from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class URI:
    """Strongly typed URI value object.

    Ensures that any instance holds a valid URI string (containing '://').
    """

    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise TypeError("URI value must be a string")
        if "://" not in self.value:
            raise ValueError(f"Invalid URI format (missing scheme): {self.value}")

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"URI('{self.value}')"

    @classmethod
    def from_path(cls, path: str | Path) -> "URI":
        """Create a URI from a file path."""
        import socket

        from wks.utils.normalize_path import normalize_path

        normalized = normalize_path(path)
        hostname = socket.gethostname()
        return cls(f"file://{hostname}{normalized}")
