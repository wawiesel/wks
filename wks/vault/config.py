"""Vault configuration management."""

from __future__ import annotations

__all__ = ["VaultConfig", "VaultConfigError"]

from dataclasses import dataclass


class VaultConfigError(Exception):
    """Raised when vault configuration is invalid."""

    def __init__(self, errors: list[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Vault configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class VaultConfig:
    """Vault configuration loaded from config dict with validation."""

    vault_type: str
    base_dir: str
    wks_dir: str
    update_frequency_seconds: float
    database: str

    def _validate_required_fields(self) -> list[str]:
        """Validate that required fields are present and correct types."""
        errors = []

        if not isinstance(self.vault_type, str) or not self.vault_type:
            errors.append(
                f"vault.type must be a non-empty string "
                f"(found: {type(self.vault_type).__name__} = {self.vault_type!r}, expected: 'obsidian')"
            )

        if not isinstance(self.base_dir, str) or not self.base_dir:
            errors.append(
                f"vault.base_dir must be a non-empty string "
                f"(found: {type(self.base_dir).__name__} = {self.base_dir!r}, expected: path string like '~/_vault')"
            )

        if not isinstance(self.wks_dir, str) or not self.wks_dir:
            errors.append(
                f"vault.wks_dir must be a non-empty string "
                f"(found: {type(self.wks_dir).__name__} = {self.wks_dir!r}, expected: string like 'WKS')"
            )

        if not isinstance(self.update_frequency_seconds, (int, float)) or self.update_frequency_seconds <= 0:
            errors.append(
                f"vault.update_frequency_seconds must be a positive number "
                f"(found: {type(self.update_frequency_seconds).__name__} = {self.update_frequency_seconds!r}, "
                "expected: float > 0)"
            )

        return errors

    def _validate_database_format(self) -> list[str]:
        """Validate database string is in 'database.collection' format."""
        errors = []

        if not isinstance(self.database, str) or "." not in self.database:
            errors.append(
                f"vault.database must be in format 'database.collection' "
                f"(found: {self.database!r}, expected: format like 'wks.vault')"
            )
        elif isinstance(self.database, str):
            parts = self.database.split(".", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append(
                    f"vault.database must be in format 'database.collection' "
                    f"(found: {self.database!r}, expected: format like 'wks.vault' with both parts non-empty)"
                )

        return errors

    def _validate_vault_type(self) -> list[str]:
        """Validate vault type is supported."""
        errors = []

        if self.vault_type != "obsidian":
            errors.append(f"vault.type must be 'obsidian' (found: {self.vault_type!r}, expected: 'obsidian')")

        return errors

    def __post_init__(self):
        """Validate vault configuration after initialization.

        Collects all validation errors and raises a single VaultConfigError
        with all errors, so the user can see everything that needs fixing.
        """
        errors = []
        errors.extend(self._validate_required_fields())
        errors.extend(self._validate_database_format())
        errors.extend(self._validate_vault_type())

        if errors:
            raise VaultConfigError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> VaultConfig:
        """Load vault config from config dict.

        Raises:
            VaultConfigError: If vault section is missing or field values are invalid
        """
        vault_config = config.get("vault")
        if not vault_config:
            raise VaultConfigError(
                [
                    "vault section is required in config "
                    "(found: missing, expected: vault section with base_dir, database, etc.)"
                ]
            )

        # Extract fields with defaults
        vault_type = vault_config.get("type", "obsidian")
        base_dir = vault_config.get("base_dir", "")
        wks_dir = vault_config.get("wks_dir", "WKS")
        update_frequency_seconds = vault_config.get("update_frequency_seconds", 10.0)
        database = vault_config.get("database", "")

        return cls(
            vault_type=vault_type,
            base_dir=base_dir,
            wks_dir=wks_dir,
            update_frequency_seconds=float(update_frequency_seconds),
            database=database,
        )
