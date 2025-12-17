"""Vault public API."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ._AbstractImpl import _AbstractImpl
from .VaultConfig import VaultConfig


class Vault(_AbstractImpl):
    """Facade for vault operations.

    Delegates to a concrete implementation based on configuration.
    Acts as a Context Manager to ensure proper resource handling.
    """

    def __init__(self, vault_config: VaultConfig):
        self.vault_config = vault_config
        self.type = vault_config.type
        # In Vault, the "name" concept isn't as central as Database,
        # but _Impl takes config and optional machine name.
        # We'll just pass config to _Impl for now.
        self._impl: _AbstractImpl | None = None

    def __enter__(self) -> "Vault":
        backend_type = self.vault_config.type

        # Validate backend type using VaultConfig registry (single source of truth)
        from .VaultConfig import _BACKEND_REGISTRY

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import backend implementation class directly from backend _Impl module
        # Pattern: wks.api.vault._obsidian._Impl
        module = __import__(f"wks.api.vault._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl

        # _Impl expects (vault_path: Path, *, machine_name: str | None = None)
        # But we want to construct it from ValidConfig.
        # This implies _Impl signature or construction might need a wrapper or
        # we adapt here.
        # Existing _Impl: __init__(self, vault_path: Path, *, machine_name: str | None = None)
        # We can adapt here:
        from ...utils import expand_path

        vault_path = expand_path(self.vault_config.base_dir)
        self._impl = impl_class(vault_path)

        # Vault implementations don't strictly need __enter__/__exit__ unless they hold resources.
        # But we support the protocol for consistency.
        if hasattr(self._impl, "__enter__"):
            self._impl.__enter__()  # type: ignore
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._impl and hasattr(self._impl, "__exit__"):
            self._impl.__exit__(exc_type, exc_val, exc_tb)  # type: ignore
        self._impl = None

    @property
    def vault_path(self) -> Path:
        """Root directory of the vault."""
        if not self._impl:
            raise RuntimeError("Vault not initialized (use 'with Vault(...)')")
        return self._impl.vault_path

    @property
    def links_dir(self) -> Path:
        return self._impl.links_dir  # type: ignore

    def iter_markdown_files(self) -> Iterator[Path]:
        return self._impl.iter_markdown_files()  # type: ignore

    # Expose find_broken_links if available (duck typing)
    def find_broken_links(self) -> list[Path]:
        if hasattr(self._impl, "find_broken_links"):
            return self._impl.find_broken_links()  # type: ignore
        return []
