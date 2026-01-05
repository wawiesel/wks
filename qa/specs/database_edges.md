# Database Schema: Edges

Name: `edges`

Each document represents a directional relationship (link) between nodes.

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Deterministic ID: `sha256(from_local_uri|line|col|to_local_uri|to_remote_uri)` |
| `from_local_uri` | string | Source URI (`file://...` or `vault:///...`). Corresponds to `nodes.local_uri`. |
| `from_remote_uri` | string (optional) | Source Remote URI if the source is synced (e.g., `https://sharepoint...`). Corresponds to `nodes.remote_uri`. |
| `name` | string | Display name/alias of the link (may be empty). |
| `to_local_uri` | string (optional) | Target Local URI (`file://...`, `vault:///...`). |
| `to_remote_uri` | string (optional) | Target Remote URI (`https://...` or cloud URL of synced file). |
| `line_number` | int | 1-based line number in source file. |
| `column_number` | int | 1-based column number in source file. |
| `parser` | string | Parser used to extract the link. |
| `doc_type` | string | Always `link`. |
| `last_seen` | string | ISO8601 timestamp. |
| `last_updated` | string | ISO8601 timestamp. |
