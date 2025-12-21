# Database Schema: Nodes

Name: `nodes`

Each document represents a monitored node (file) in the filesystem.

| Field | Type | Description |
|-------|------|-------------|
| `local_uri` | string | URI of the file (`file://...`). Primary key used for lookups. |
| `remote_uri` | string (optional) | Remote URI if the file is synced to cloud (e.g., `https://sharepoint...`). |
| `checksum` | string | File checksum (e.g., md5/sha256). |
| `bytes` | int | File size in bytes. |
| `priority` | float | Calculated priority score. |
| `timestamp` | string | ISO8601 timestamp of last modification. |

**Meta Document**:
- `_id`: `__meta__`
- `doc_type`: `meta`
- `last_sync`: ISO8601 timestamp of the last sync operation.
