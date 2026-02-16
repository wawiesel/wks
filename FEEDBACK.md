# WKS CLI Stress Test Feedback

Tested every `wksc` command and subcommand as a first-time user.
Date: 2026-02-16, version 0.8.0.

---

## Bugs

### B1. `vault links` rejects valid vault paths

```
$ wksc vault links /Users/ww5/_vault/note.md
✗ Target is not in the vault: file://mac139160/Users/ww5/_vault/note.md
```

The file is inside the vault (`base_dir: /Users/ww5/_vault`). Other commands
handle the same path fine:

```
$ wksc vault check /Users/ww5/_vault/note.md
✓ Health Check Passed: 1 notes, 1 links, 0 broken

$ wksc link check /Users/ww5/_vault/note.md
✓ Monitored: Found 1 links in note.md
```

**Root cause**: `cmd_links.py` uses `URI.from_any()` directly (line 67) while
`cmd_check.py` uses `_ensure_arg_uri()` (line 69) which handles the
file-to-vault path conversion correctly. `cmd_links` should use the same
resolution path.

**File**: `wks/api/vault/cmd_links.py:67-69`

---

### B2. `link show` leaks Python internals in YAML output

```yaml
direction: !!python/object/apply:wks.api.link.Direction.Direction
- from
```

JSON mode is fine (`"direction": "from"`). The Direction enum needs a YAML
serializer or should be converted to a string before output.

**File**: `wks/api/link/cmd_show.py` (output construction)

---

### B3. `vault check` shows checkmark on failure

```
✓ Health Check Failed: 341 notes, 3147 links, 452 broken
```

Check mark (success=True) with "Failed" in the message. The issue:
`result_obj.success = len(all_errors) == 0` doesn't consider broken links,
only scanner errors. But the result message reflects `is_valid` which does
consider broken links.

**Fix**: `result_obj.success` should be set to `is_valid`, not just
`len(all_errors) == 0`.

**File**: `wks/api/vault/cmd_check.py:110`

---

### B4. `service status` reports wrong `log_path`

```yaml
log_path: /Users/ww5/.wks/daemon.json    # service status
log_path: /Users/ww5/.wks/logfile         # daemon status (correct)
```

`service/cmd_status.py` line 117 sets `log_path` to `daemon_file` (the JSON
status file) instead of the actual logfile.

**File**: `wks/api/service/cmd_status.py:117`

---

### B5. `diff` silently fails without `--engine`

```
$ wksc diff README.md pyproject.toml
(just prints help page, exits 1, no error message)
```

Nothing tells the user that `--engine` is required. The help page shows it
as an optional flag (`--engine -e TEXT`). Should either:
- Make it a required argument, or
- Default to `auto`, or
- Print a clear error: "Error: --engine is required (options: bsdiff3, myers, sexp, auto)"

**File**: `wks/cli/diff.py:42-44`

---

### B6. `transform` options fail after positional args

```
$ wksc transform dx file.toml --raw
Error: No such command '--raw'.

$ wksc transform --raw dx file.toml     # works
```

This is a Typer limitation with `invoke_without_command=True` + positional
args + options. User expectation is that `--raw` works in any position.

**File**: `wks/cli/transform.py:28-34`

---

## UX Improvements

### U1. No top-level `wksc status`

A new user has to know the difference between `service status`, `daemon status`,
and `log status`. A single `wksc status` that shows the combined picture
would be the natural first command:

```
$ wksc status
Service:  running (PID 3794, installed via launchd)
Logfile:  37 entries, 0 errors, 0 warnings
Monitor:  480 tracked files, last sync 5s ago
Links:    84 links across 76 files
Vault:    343 notes, 2695 edges
```

---

### U2. `daemon clear` should work while running

Currently:
```
$ wksc daemon clear
✗ Cannot clear while daemon is running
```

The user must stop → clear → start to clear errors. The daemon should be able
to clear its own error/warning log on demand. At minimum, add a
`--errors-only` flag that truncates the logfile's ERROR entries without
requiring a stop.

---

### U3. `vault check` output is overwhelming

With 452 broken links, the output is 67KB of individual YAML entries. Should
summarize by default and offer `--verbose` for the full list:

```
$ wksc vault check
✗ Health Check Failed: 341 notes, 3147 links, 452 broken
  Top sources of broken links:
    Index.md: 47 broken
    _Past/: 38 broken
    ...
  Run with --verbose for full list.
```

---

### U4. No `--quiet` / `-q` flag for scripting

Every command prints progress lines to stderr, even sub-second operations:

```
10:41:16 i Getting version information...
10:41:16 Progress: Getting package version... (30.0%)
10:41:16 Progress: Complete (100.0%)
10:41:16 ✓ WKS version: 0.8.0
```

For scripting, `wksc -q config version` should just output the data.

---

### U5. `service start` is silent about already-running state

```
$ wksc service start       # already running
✓ Service started successfully (label: com.wieselquist.wks)
```

No indication that it was already running. Ideally:
`✓ Service already running (PID: 3794)` or a warning.

---

### U6. `database show` succeeds for nonexistent databases

```
$ wksc database show nonexistent
✓ Found 0 document(s) in nonexistent
```

Should warn that the database doesn't exist. `database list` shows available
databases; `show` on a name not in that list should say so.

---

### U7. `database list` shows stale/test databases

```
databases:
- TRANSFORM
- XXtransformXX
- edges
- nodes
- transform
- wks
```

`TRANSFORM`, `XXtransformXX`, `wks` look like leftover test databases. No
way to distinguish active from stale. Consider flagging known databases or
adding a `database drop` command for cleanup.

---

## Summary

| ID  | Type | Severity | Command              | Issue                                   |
|-----|------|----------|----------------------|-----------------------------------------|
| B1  | Bug  | High     | `vault links`        | Rejects valid vault paths               |
| B2  | Bug  | Medium   | `link show`          | Python internals in YAML output         |
| B3  | Bug  | Medium   | `vault check`        | Checkmark on failure                    |
| B4  | Bug  | Low      | `service status`     | Wrong `log_path` value                  |
| B5  | Bug  | Medium   | `diff`               | Silent failure without `--engine`       |
| B6  | Bug  | Low      | `transform`          | Options after positional args fail      |
| U1  | UX   | High     | (new)                | No top-level `wksc status`              |
| U2  | UX   | Medium   | `daemon clear`       | Requires stopping daemon                |
| U3  | UX   | Medium   | `vault check`        | Overwhelming output for broken links    |
| U4  | UX   | Medium   | (global)             | No `--quiet` flag                       |
| U5  | UX   | Low      | `service start`      | Silent about already-running            |
| U6  | UX   | Low      | `database show`      | Succeeds for nonexistent databases      |
| U7  | UX   | Low      | `database list`      | Shows stale/test databases              |
