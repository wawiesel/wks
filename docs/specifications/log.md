# Log Domain

Centralized logging across all WKS domains.

## Configuration

```json
{
  "log": {
    "level": "INFO",
    "debug_retention_days": 0.5,
    "info_retention_days": 1.0,
    "warning_retention_days": 2.0,
    "error_retention_days": 7.0
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `level` | string | Yes | Logging level: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `debug_retention_days` | float | Yes | Days to retain debug entries |
| `info_retention_days` | float | Yes | Days to retain info entries |
| `warning_retention_days` | float | Yes | Days to retain warnings |
| `error_retention_days` | float | Yes | Days to retain errors |

## Log File

Single unified log file at `~/.wks/logfile`. All domains write timestamped entries with domain tags:

```
[2025-12-20T12:15:00+00:00] [daemon] INFO: Daemon child started
[2025-12-20T12:15:01+00:00] [daemon] WARN: Watch path missing /tmp/test
[2025-12-20T12:15:02+00:00] [monitor] ERROR: Sync failed for /path/to/file
[2025-12-20T12:15:03+00:00] [vault] INFO: Synced 42 links
```

Format: `[TIMESTAMP] [DOMAIN] LEVEL: message`

## Commands

### `wksc log prune`

Remove log entries by level. Default: prune DEBUG and INFO.

```bash
wksc log prune              # Delete DEBUG and INFO entries (default)
wksc log prune --warnings   # Delete WARN entries
wksc log prune --errors     # Delete ERROR entries
wksc log prune --no-debug   # Do not delete DEBUG entries
wksc log prune --no-info    # Do not delete INFO entries
```

| Flag | Description |
|------|-------------|
| `--debug / --no-debug` | Prune DEBUG entries (default: `--debug`) |
| `--info / --no-info` | Prune INFO entries (default: `--info`) |
| `--warnings / --no-warnings` | Prune WARN entries (default: `--no-warnings`) |
| `--errors / --no-errors` | Prune ERROR entries (default: `--no-errors`) |

**Output:**
```yaml
errors: []
warnings: []
pruned_debug: 5
pruned_info: 42
pruned_warnings: 0
pruned_errors: 0
message: "Pruned 47 log entries"
```

### `wksc log status`

Show log file status.

```yaml
log_path: /Users/ww5/.wks/logfile
size_bytes: 12345
entry_counts:
  debug: 0
  info: 42
  warn: 3
  error: 1
oldest_entry: "2025-12-18T10:00:00+00:00"
newest_entry: "2025-12-20T12:00:00+00:00"
```

---

## Implementation Notes

- **Prune-on-access**: Any log read auto-prunes expired entries first (part of access contract)
- `log prune` is a manual override to remove by level (DEBUG/INFO by default)
- All domains write to shared logfile via `_append_log` utility
