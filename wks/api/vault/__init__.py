"""Vault API module."""

from wks.api.config.output_models import output_model

VaultStatusOutput = output_model("VaultStatusOutput", "database", "total_links", "last_sync", "success")
VaultSyncOutput = output_model(
    "VaultSyncOutput", "notes_scanned", "links_written", "links_deleted", "sync_duration_ms", "success"
)
VaultLinksOutput = output_model("VaultLinksOutput", "path", "direction", "edges", "count", "success")
VaultCheckOutput = output_model(
    "VaultCheckOutput", "path", "notes_checked", "links_checked", "broken_count", "issues", "is_valid", "success"
)
VaultRepairOutput = output_model(
    "VaultRepairOutput", "fixed", "unresolved", "fixed_count", "unresolved_count", "success"
)

__all__ = [
    "VaultCheckOutput",
    "VaultLinksOutput",
    "VaultRepairOutput",
    "VaultStatusOutput",
    "VaultSyncOutput",
]
