"""Vault public API."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ._AbstractBackend import _AbstractBackend
from .VaultConfig import VaultConfig


class Vault(_AbstractBackend):
    """Facade for Vault operations.

    Delegates to a concrete implementation based on configuration.
    Acts as a Context Manager to ensure proper resource handling.
    """

    def __init__(self, vault_config: VaultConfig | None = None):
        """Initialize Vault facade.

        Args:
            vault_config: Optional VaultConfig object. If None, it will be loaded from WKSConfig.
        """
        if vault_config:
            self.vault_config = vault_config
        else:
            from wks.api.config.WKSConfig import WKSConfig

            # Load full config to get vault section
            full_config = WKSConfig.load()
            self.vault_config = full_config.vault

        self._backend: _AbstractBackend | None = None

    def __enter__(self) -> "Vault":
        backend_type = self.vault_config.type

        # Validate backend type using VaultConfig registry
        from .VaultConfig import _BACKEND_REGISTRY

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import backend implementation class directly from backend _Backend module
        # Pattern: wks.api.vault._obsidian._Backend
        module = __import__(f"wks.api.vault._{backend_type}._Backend", fromlist=[""])
        backend_class = module._Backend

        # Instantiate backend
        self._backend = backend_class(self.vault_config)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._backend = None

    @property
    def vault_path(self) -> Path:
        """Root directory of the vault."""
        if not self._backend:
            raise RuntimeError("Vault not initialized (use 'with Vault(...)')")
        return self._backend.vault_path

    @property
    def links_dir(self) -> Path:
        if not self._backend:
            raise RuntimeError("Vault not initialized (use 'with Vault(...)')")
        return self._backend.links_dir

    def iter_markdown_files(self) -> Iterator[Path]:
        if not self._backend:
            raise RuntimeError("Vault not initialized (use 'with Vault(...)')")
        return self._backend.iter_markdown_files()

    # Expose find_broken_links if available (duck typing)
    def find_broken_links(self) -> list[Path]:
        if hasattr(self._backend, "find_broken_links"):
            return self._backend.find_broken_links()  # type: ignore
        return []

    def resolve_link(self, target: str) -> Any:
        # Use Any return type to avoid circular import of LinkMetadata if it's not strictly needed here,
        # or import it if we want strict typing. Let's rely on backend return.
        if not self._backend:
            raise RuntimeError("Vault not initialized (use 'with Vault(...)')")
        return self._backend.resolve_link(target)

    def update_link_for_move(self, old_path: Path, new_path: Path) -> tuple[str, str] | None:
        if not self._backend or not hasattr(self._backend, "update_link_for_move"):
            return None
        return self._backend.update_link_for_move(old_path, new_path)  # type: ignore

    def rewrite_wiki_links(self, old_target: str, new_target: str) -> int:
        if not self._backend or not hasattr(self._backend, "rewrite_wiki_links"):
            return 0
        return self._backend.rewrite_wiki_links(old_target, new_target)  # type: ignore

    def update_edges_for_move(
        self,
        old_path: Path,
        new_path: Path,
        old_vault_rel: str,
        new_vault_rel: str,
    ) -> int:
        if not self._backend or not hasattr(self._backend, "update_edges_for_move"):
            return 0
        return self._backend.update_edges_for_move(old_path, new_path, old_vault_rel, new_vault_rel)  # type: ignore
