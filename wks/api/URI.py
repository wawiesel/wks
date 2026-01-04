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

    @classmethod
    def from_any(cls, path_or_uri: str | Path, vault_path: Path | None = None) -> "URI":
        """Convert any path or URI string to a URI object.

        Handles:
        - Already-formatted URIs (vault:///, file:///)
        - File paths (normalized and hostname-prefixed)
        - Vault path awareness (converts to vault:/// if within vault_path)
        """
        from wks.utils.normalize_path import normalize_path

        # Already a URI string?
        if isinstance(path_or_uri, str) and "://" in path_or_uri:
            return cls(path_or_uri)

        # Convert to Path and normalize
        path = normalize_path(path_or_uri)

        # If vault_path provided, check if path is within vault
        if vault_path is not None:
            vault_path = normalize_path(vault_path)
            try:
                rel_path = path.relative_to(vault_path)
                return cls(f"vault:///{rel_path}")
            except ValueError:
                pass

        # Default to file URI
        return cls.from_path(path)

    @property
    def is_file(self) -> bool:
        """Return True if this is a local filesystem URI (file://)."""
        return self.value.startswith("file://")

    @property
    def is_vault(self) -> bool:
        """Return True if this is a vault-internal URI (vault:///)."""
        return self.value.startswith("vault:///")

    def to_path(self, vault_path: Path | None = None) -> Path:
        """Resolve this URI to a local filesystem Path.

        Args:
            vault_path: Optional root directory for resolving vault:/// URIs.

        Returns:
            Path object.

        Raises:
            ValueError: If URI is not a supported type or vault_path is missing for vault URIs.
        """
        from wks.utils.normalize_path import normalize_path

        if self.is_file:
            return self.path

        if self.is_vault:
            if vault_path is None:
                raise ValueError(f"Cannot resolve vault URI without vault_path: {self.value}")
            # vault:///path/to/note.md -> path/to/note.md
            rel_path = self.value[9:]
            return normalize_path(vault_path / rel_path)

        raise ValueError(f"Cannot resolve local path from URI: {self.value}")

    @property
    def path(self) -> Path:
        """Get the local filesystem path from a file:// URI.

        For vault:// URIs, use .to_path(vault_path).

        Raises:
            ValueError: If URI is not a file URI.
        """
        from urllib.parse import unquote

        from wks.utils.normalize_path import normalize_path

        if not self.is_file:
            raise ValueError(f"Cannot extract local path from non-file URI: {self.value}")

        # Strip scheme
        path_part = self.value[7:]

        # Find start of path after hostname
        first_slash = path_part.find("/")
        path_part = "/" if first_slash == -1 else path_part[first_slash:]

        return normalize_path(unquote(path_part))
