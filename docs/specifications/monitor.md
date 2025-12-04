# Monitor Layer Specification

**Purpose**: Track filesystem state and calculate priorities

**Database**: `wks.monitor` (Strict `<collection>.<database>` format required)

**Schema**:
- `path` — absolute URI (e.g., `file:///Users/ww5/Documents/report.pdf`)
- `timestamp` — ISO 8601 UTC string for last modification
- `checksum` — SHA256 hash of file contents
- `bytes` — file size in bytes
- `priority` — calculated integer score (1-∞) based on path structure

## Priority Calculation
1. Match file to deepest `managed_directories` entry (e.g., `~/Documents` → 100)
2. For each path component after base: multiply by `depth_multiplier` (0.9)
3. For each leading `_` in component name: divide by `underscore_divisor` (2)
4. If component is single `_`: divide by `single_underscore_divisor` (64)
5. Multiply by extension weight from `extension_weights`
6. Round to integer (minimum 1)

## Monitor include/exclude logic
- `include_paths` and `exclude_paths` store canonical directories (fully-resolved on load). A path must appear in exactly one list; identical entries across both lists are a validation error. When evaluating a file/directory, resolve it and walk its ancestors until one appears in either list. The nearest match wins. If the closest ancestor is in `exclude_paths` (or no ancestor is found at all), the path is excluded immediately and no further checks run.
- Once a path survives the root check, the daemon applies directory/glob rules in two phases:
  - **Exclusion phase**: evaluate `exclude_dirnames` (the immediate parent directory) and `exclude_globs` (full path/basename). If either matches, the path becomes “tentatively excluded”.
  - **Inclusion overrides**: evaluate `include_dirnames` and `include_globs`. If a path was tentatively excluded but matches an include rule, the exclusion is reversed and the path is monitored. If neither include rule fires, the exclusion stands. Dirname/glob lists must not share entries; duplicates are validation errors, and entries that duplicate the opposite glob list are flagged as redundant.

## MCP Interface (Primary)

Complete control over monitoring configuration and status.

- `wksm_monitor_status` — Get monitoring status and configuration
- `wksm_monitor_validate` — Validate configuration for conflicts
- `wksm_monitor_check(path)` — Check if path would be monitored
- `wksm_monitor_list(list_name)` — Get contents of configuration list
- `wksm_monitor_add(list_name, value)` — Add value to list
- `wksm_monitor_remove(list_name, value)` — Remove value from list
- `wksm_monitor_managed_list` — List managed directories
- `wksm_monitor_managed_add(path, priority)` — Add managed directory
- `wksm_monitor_managed_remove(path)` — Remove managed directory
- `wksm_monitor_managed_set_priority(path, priority)` — Update directory priority
- `wksm_db_monitor()` — Query filesystem database

## CLI Interface (Secondary)

Human-friendly wrappers for the MCP tools.

- `wksc monitor status` — show monitoring statistics (supports `--live`)
- `wksc monitor include_paths {add,remove} <path>` — manage explicit inclusions
- `wksc monitor exclude_paths {add,remove} <path>` — manage explicit exclusions
- `wksc monitor include_dirnames {add,remove} <name>` — manage directory name inclusions
- `wksc monitor exclude_dirnames {add,remove} <name>` — manage directory name exclusions
- `wksc monitor include_globs {add,remove} <pattern>` — manage glob pattern inclusions
- `wksc monitor exclude_globs {add,remove} <pattern>` — manage glob pattern exclusions
- `wksc monitor managed {add,remove,set-priority}` — manage directory priorities
- `wksc db monitor` — query filesystem database
