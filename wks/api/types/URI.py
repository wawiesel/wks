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

    @property
    def path(self) -> Path:
        """Get the local filesystem path from the URI.

        Raises:
            ValueError: If URI is not a file URI.
        """
        from urllib.parse import unquote

        from wks.utils.normalize_path import normalize_path

        if not self.value.startswith("file://"):
            raise ValueError(f"Cannot extract local path from non-file URI: {self.value}")

        # Strip scheme
        path_part = self.value[7:]

        # Find start of path after hostname
        # file://hostname/path -> hostname/path -> find('/')
        # file:///path -> /path -> find('/')
        first_slash = path_part.find("/")
        path_part = "/" if first_slash == -1 else path_part[first_slash:]

        return normalize_path(unquote(path_part))
