# Monitor Layer Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).


## Overview

**Purpose**: Track filesystem state and calculate priorities for files and directories.

The monitor layer provides filesystem tracking with configurable filtering, priority calculation, and automatic synchronization. It maintains a database of tracked files with their metadata and calculated priorities.

## Configuration

Monitor configuration is specified in the WKS config file under the `monitor` section:

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
    "database": "monitor",
    "sync": {
      "max_documents": 1000000,
      "min_priority": 0.0,
      "prune_interval_secs": 300.0
    }
  }
}
```

**Required Fields**:
- `filter`: Object containing include/exclude rules for paths, directory names, and glob patterns
- `priority`: Object containing managed directories and priority calculation weights
- `database`: String specifying the collection name (prefix from `database.prefix` is automatically prepended)
- `sync`: Object containing synchronization and pruning configuration

**Configuration Requirements**:
- All configuration values must be present in the config file - no defaults are permitted in code
- If a required field is missing, validation must fail immediately with a clear error message
- Priority values are floats
- Collection names are automatically prefixed with `database.prefix` from the database configuration

## Filter Logic

The monitor uses a two-phase filtering system to determine which files and directories are tracked:

**Phase 1: Root Path Matching**
- Paths are resolved to canonical (fully-resolved) form
- The system walks up the directory tree from the file to find the nearest ancestor in either `include_paths` or `exclude_paths`
- If the nearest ancestor is in `exclude_paths`, or no ancestor is found, the path is excluded immediately
- If the nearest ancestor is in `include_paths`, the path proceeds to Phase 2
- A path must appear in exactly one list; identical entries across both lists are a validation error

**Phase 2: Directory Name and Glob Matching**
- **Exclusion phase**: Evaluate `exclude_dirnames` (matches immediate parent directory name) and `exclude_globs` (matches full path or basename). If either matches, the path is tentatively excluded
- **Inclusion overrides**: Evaluate `include_dirnames` and `include_globs`. If a path was tentatively excluded but matches an include rule, the exclusion is reversed and the path is monitored
- If neither include rule matches, the exclusion stands
- Duplicate entries within the same list or across opposite lists are validation errors

## Priority Calculation

Priority is calculated as a float value based on path structure and configured weights:

1. **Base Priority**: Match the file to the deepest managed directory entry in `priority.dirs`. The base priority is the value associated with that directory (e.g., `~/Documents` → 100.0). If the file is moved, ancestry is recalculated.

2. **Depth Multiplier**: For each path component after the managed base directory, multiply by `priority.weights.depth_multiplier` (example: 0.9).

3. **Underscore Multiplier**: For each leading underscore in a path component, multiply by `priority.weights.underscore_multiplier` per underscore (example: 0.5 each).

4. **Only Underscore Multiplier**: If a path component is exactly `_`, multiply by `priority.weights.only_underscore_multiplier` (example: 0.1).

5. **Extension Weight**: Multiply by the weight from `priority.weights.extension_weights` for the file's extension. If the extension is not in the map, use 1.0.

6. **Final Priority**: The result remains a float; rounding/formatting only occurs at presentation time.

Files with calculated priority below `sync.min_priority` are not added to the database. During sync/prune operations, existing entries with priority below `min_priority` are removed.

## Synchronization

The monitor synchronizes filesystem state with the database:

- **Manual Sync**: The `wksc monitor sync` command forces an update of specified files or directories, allowing monitor to work without the daemon running
- **Automatic Sync**: When the daemon is running, significant file operations (move/delete) automatically trigger synchronization for affected paths
- **File Processing**: For files, updates the entry in the database (checksum, priority, etc.). For directories, processes files that match monitor rules (recursive with `--recursive` flag)
- **Timestamp Preservation**: Updates timestamp when content changes; unchanged files retain their original timestamp
- **Priority Threshold**: Only adds/updates entries if calculated priority >= `min_priority`. Removes existing entries if recalculated priority < `min_priority`

## Pruning

Pruning maintains the database size and removes low-priority or invalid entries:

- **Triggers**: Runs on schedule (`prune_interval_secs`) or before inserts when the collection exceeds `max_documents`
- **Removal Order**: Removes lowest-priority documents first (ties broken arbitrarily)
- **Invalid Entries**: Drops entries whose files no longer exist on the filesystem
- **Priority Threshold**: Removes entries with priority below `min_priority` (recalculated on each prune/sync operation)
- **Independence**: Pruning works independently of the service - `wksc monitor sync` can add data, and pruning enforces the cap even without the daemon running

## Database Schema

The monitor database stores tracked files with the following schema:

- `path` — absolute URI (e.g., `file:///Users/ww5/Documents/report.pdf`)
- `timestamp` — ISO 8601 UTC string for last modification (unchanged by sync if the file is unchanged)
- `checksum` — SHA256 hash of file contents
- `bytes` — file size in bytes
- `priority` — float based on path structure and weights (see Priority Calculation)

The database name is specified in `monitor.database` and is automatically prefixed with `database.prefix` from the database configuration.

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

- `wksc monitor status` — Show monitoring statistics including validation (exits with error code if configuration issues found)
- `wksc monitor check <path>` — Check if path would be monitored and report priority
- `wksc monitor sync <path> [--recursive]` — Force update of file or directory into monitor database (works without service)
- `wksc monitor filter show [<list_name>]` — Show available lists or contents of a specific list
- `wksc monitor filter add <list_name> <value>` — Add to include/exclude lists
- `wksc monitor filter remove <list_name> <value>` — Remove from include/exclude lists
- `wksc monitor priority show` — List managed directories with priorities (float values)
- `wksc monitor priority add <path> <priority>` — Set or update priority for a managed directory
- `wksc monitor priority remove <path>` — Remove a managed directory
- `wksc database monitor` — Query filesystem database

**Progress Indicators**: Commands that process multiple files (e.g., `sync`) must follow the 4-step pattern:
1. Announce: Initial status message
2. Progress: Progress indicator showing files processed
3. Result: Summary message with counts
4. Output: Structured data with details
