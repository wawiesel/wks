# Monitor Layer Specification

**Purpose**: Track filesystem state and calculate priorities

**Database**: `wks.monitor` (Strict `<collection>.<database>` format required)

**Schema**:
- `path` — absolute URI (e.g., `file:///Users/ww5/Documents/report.pdf`)
- `timestamp` — ISO 8601 UTC string for last modification (unchanged by sync if the file is unchanged)
- `checksum` — SHA256 hash of file contents
- `bytes` — file size in bytes
- `priority` — float based on path structure and weights (see Priority Calculation)

## Priority Calculation
1. Match file to deepest managed directory entry (e.g., `~/Documents` → 100.0). Recompute on moves because ancestry changes.
2. For each path component after the managed base: multiply by the configured `depth_multiplier` (example: 0.9).
3. For each leading `_` in a component: multiply by the configured `underscore_multiplier` per underscore (example: 0.5 each).
4. If the component is exactly `_`: multiply by the configured `only_underscore_multiplier` (example: 0.1).
5. Multiply by extension weight from the configured `extension_weights` map (unspecified extensions use 1.0).
6. Final priority remains a float; round/format only at presentation time.

## Filter (include/exclude logic)
- `include_paths` and `exclude_paths` store canonical directories (fully-resolved on load). A path must appear in exactly one list; identical entries across both lists are a validation error. When evaluating a file/directory, resolve it and walk its ancestors until one appears in either list. The nearest match wins. If the closest ancestor is in `exclude_paths` (or no ancestor is found at all), the path is excluded immediately and no further checks run.
- Once a path survives the root check, the daemon applies directory/glob rules in two phases:
  - **Exclusion phase**: evaluate `exclude_dirnames` (the immediate parent directory) and `exclude_globs` (full path/basename). If either matches, the path becomes “tentatively excluded”.
  - **Inclusion overrides**: evaluate `include_dirnames` and `include_globs`. If a path was tentatively excluded but matches an include rule, the exclusion is reversed and the path is monitored. If neither include rule fires, the exclusion stands. Dirname/glob lists must not share entries; duplicates are validation errors, and entries that duplicate the opposite glob list are flagged as redundant.

## Priority (managed directories + scoring)
- Managed directories map canonical paths to priority **floats** for finer-grained weighting.
- Priority calculation multiplies by the managed directory weight and the configured multipliers (depth, underscore, only-underscore, extension).
- Managed directories are created/updated via priority commands; removal deletes the entry.
- `min_priority`: Files with calculated priority below this threshold are not added to the database. During sync/prune operations, existing entries with priority below `min_priority` are expunged.

## Sync (database + housekeeping)
- `database`: `wks.monitor` (`<database>.<collection>` format required).
- `max_documents`: cap on monitor collection; excess pruned from lowest priority.
- `prune_interval_secs`: how often pruning runs.
- When the daemon is running, significant file operations (move/delete) implicitly trigger a sync for the affected paths; manual `wksc monitor sync` is still available when the service is not running.

### Pruning
- Triggered on schedule (`prune_interval_secs`) or before inserts when over `max_documents`.
- Removes lowest-priority documents first (ties broken arbitrarily) and drops entries whose files no longer exist.
- Removes entries with priority below `min_priority` (recalculated on each prune/sync operation).
- Keeps the collection bounded so sync/queries remain fast.
- Independent of the service: `wksc monitor sync` can add data; pruning enforces the cap even without the daemon running.

## Monitor config (shape)

Only the `monitor` section is shown here; other config sections are omitted. Priority values are floats.

```json
{
  "monitor": {
    "filter": {
      "include_paths": [],
      "exclude_paths": [],
      "include_dirnames": [],
      "exclude_dirnames": [],
      "include_globs": [],
      "exclude_globs": []
    },
    "priority": {
      "dirs": {
        "/Users/you/Projects": 100.0
      },
      "weights": {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {}
      }
    },
    "sync": {
      "database": "wks.monitor",
      "max_documents": 1000000,
      "min_priority": 0.0,
      "prune_interval_secs": 300.0
    }
  }
}
```

## MCP Interface (Primary)

Complete control over monitoring configuration and status.

- `wksm_monitor_status` — Get monitoring status and configuration (includes validation; exits with error code if issues found)
- `wksm_monitor_check(path)` — Check if path would be monitored
- `wksm_monitor_sync(path, recursive: bool = False)` — Force update of file or directory into monitor database
- `wksm_monitor_filter_show(list_name?)` — Show contents of a configuration list or, with no list_name, show available lists
- `wksm_monitor_filter_add(list_name, value)` — Add value to include/exclude paths/dirnames/globs
- `wksm_monitor_filter_remove(list_name, value)` — Remove value from include/exclude paths/dirnames/globs
- `wksm_monitor_priority_show` — List managed directories with priorities (float values)
- `wksm_monitor_priority_add(path, priority: float)` — Set or update priority for a managed directory (creates if missing)
- `wksm_monitor_priority_remove(path)` — Remove a managed directory
- `wksm_db_monitor()` — Query filesystem database

## CLI Interface (Secondary)

Human-friendly wrappers for the MCP tools.

- `wksc monitor status` — show monitoring statistics including validation (exits with error code if configuration issues found)
- `wksc monitor check <path>` — check if path would be monitored and report priority
- `wksc monitor sync <path> [--recursive]` — force update of file or directory into monitor database (works without service)
- `wksc monitor filter show [<list_name>]` — show available lists or contents of a specific list
- `wksc monitor filter add <list_name> <value>` — add to include/exclude lists
- `wksc monitor filter remove <list_name> <value>` — remove from include/exclude lists
- `wksc monitor priority show` — list managed directories with priorities (float values)
- `wksc monitor priority add <path> <priority>` — set or update priority for a managed directory
- `wksc monitor priority remove <path>` — remove a managed directory
- `wksc db monitor` — query filesystem database

### Monitor Sync Command

The `wksc monitor sync <path>` command forces an update of a file or directory into the monitor database, allowing monitor to work without the service running. This is useful for:
- Initial population of the monitor database
- Manual synchronization after bulk file operations
- Testing monitor configuration without starting the service

**Behavior:**
- For files: Updates the file's entry in the monitor database (checksum, priority, etc.)
- For directories (default, non-recursive): Processes only files directly in the directory that match monitor rules
- For directories (with `--recursive` flag): Recursively processes all files in the directory and subdirectories that match monitor rules
- Respects all monitor include/exclude rules (same logic as service)
- Calculates priority based on managed directories and configured weights
- Only adds/updates entries if calculated priority >= `min_priority`
- Removes existing entries if recalculated priority < `min_priority`
- Updates existing entries or creates new ones (upsert) for files above threshold
- Updates timestamp when content changes; unchanged files retain their timestamp


- **Progress indicator required**: This command must follow the 4-step pattern from CONTRIBUTING.md (works for both CLI and MCP):
  1. Announce (CLI: STDERR, MCP: status message): "Syncing files..."
  2. Progress indicator (CLI: progress bar on STDERR, MCP: progress notifications): Shows progress as files are processed with time estimate (total = number of files to process)
  3. Result (CLI: STDERR, MCP: result notification messages): "Synced X files, skipped Y files" or error message
  4. Output (CLI: STDOUT, MCP: result notification data): Summary data (counts, paths, etc.)
