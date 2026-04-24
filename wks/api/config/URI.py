from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class URI:
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
    def from_path(cls, path: str | Path) -> URI:
        import socket

        from wks.api.config.normalize_path import normalize_path

        normalized = normalize_path(path)
        hostname = socket.gethostname()
        return cls(f"file://{hostname}{normalized}")

    @classmethod
    def from_any(cls, path_or_uri: str | Path | URI, vault_path: Path | None = None) -> URI:
        from wks.api.config.normalize_path import normalize_path

        if isinstance(path_or_uri, URI):
            return path_or_uri

        if isinstance(path_or_uri, str) and "://" in path_or_uri:
            return cls(path_or_uri)

        path = normalize_path(path_or_uri)

        if vault_path is not None:
            vault_path = normalize_path(vault_path)
            try:
                rel_path = path.relative_to(vault_path)
                return cls(f"vault:///{rel_path}")
            except ValueError:
                pass

        return cls.from_path(path)

    @property
    def is_file(self) -> bool:
        return self.value.startswith("file://")

    @property
    def is_vault(self) -> bool:
        return self.value.startswith("vault:///")

    def to_path(self, vault_path: Path | None = None) -> Path:
        from wks.api.config.normalize_path import normalize_path

        if self.is_file:
            return self.path

        if self.is_vault:
            if vault_path is None:
                raise ValueError(f"Cannot resolve vault URI without vault_path: {self.value}")
            rel_path = self.value[9:]
            return normalize_path(vault_path / rel_path)

        raise ValueError(f"Cannot resolve local path from URI: {self.value}")

    @property
    def path(self) -> Path:
        from urllib.parse import unquote

        from wks.api.config.normalize_path import normalize_path

        if not self.is_file:
            raise ValueError(f"Cannot extract local path from non-file URI: {self.value}")

        path_part = self.value[7:]

        first_slash = path_part.find("/")
        path_part = "/" if first_slash == -1 else path_part[first_slash:]

        return normalize_path(unquote(path_part))
