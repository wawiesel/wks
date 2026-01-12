# WKS CLI Walkthrough

WKS tracks your file activity and connections through two core concepts:
- **Nodes** — Files you're working with, tracked by the monitor
- **Edges** — Links between files, extracted from vault wikilinks

This walkthrough introduces the main commands, starting with monitoring.

## Setup

Create `~/.wks/config.json` with your paths:

```json
{
  "monitor": {
    "filter": {
      "include_paths": ["~"],
      "exclude_paths": ["~/Library"],
      "include_dirnames": [],
      "exclude_dirnames": ["node_modules", "__pycache__"],
      "include_globs": [],
      "exclude_globs": [".*"]
    },
    "priority": {
      "dirs": { "~/Desktop": 160.0, "~": 100.0 },
      "weights": { "depth_multiplier": 0.9, "underscore_multiplier": 0.5, "only_underscore_multiplier": 0.1, "extension_weights": {} }
    },
    "remote": { "mappings": [] },
    "max_documents": 1000000,
    "min_priority": 0.01
  },
  "database": {
    "type": "mongo",
    "prefix": "wks",
    "data": { "uri": "mongodb://localhost:27017/", "local": true }
  },
  "service": {
    "type": "darwin",
    "data": {
      "label": "com.wks.daemon",
      "keep_alive": true,
      "run_at_load": false
    }
  },
  "daemon": {
    "sync_interval_secs": 5.0
  },
  "vault": {
    "type": "obsidian",
    "base_dir": "~/_vault"
  },
  "log": {
    "level": "INFO",
    "debug_retention_days": 0.5,
    "info_retention_days": 1.0,
    "warning_retention_days": 2.0,
    "error_retention_days": 7.0
  }
}
```

Reset for a clean start:

```bash
wksc database reset all
```

---

## 1. Monitor — Track Your Files

The monitor determines which files WKS knows about based on priority rules.

### Check if a path would be monitored

```bash
wksc monitor check ~/Desktop
```

```yaml
path: /Users/ww5/Desktop
is_monitored: true
priority: 160.0
decisions:
- symbol: ✓
  message: 'Path exists: /Users/ww5/Desktop'
- symbol: ✓
  message: Included by root /Users/ww5
- symbol: ✓
  message: 'Priority calculated: 160.0'
```

The decision trace shows exactly *why* a path is or isn't monitored—useful when debugging filter rules.

### View your priority directories

```bash
wksc monitor priority show
```

```yaml
priority_directories:
  ~/Desktop: 160.0
  '~': 100.0
count: 2
```

Higher priority files are kept when the database limit is reached.

### Check tracking status

```bash
wksc monitor status
```

```yaml
database: nodes
tracked_files: 0
time_based_counts:
  Last hour: 0
  1-4 hours: 0
  # ... (time ranges)
last_sync: null
success: true
```

Shows how many files are tracked and when they were last modified. Currently zero since we just reset.

### Sync a file to the database

Create a test file and sync it:

```bash
echo "# Test Note" > ~/Desktop/test_note.md
wksc monitor sync ~/Desktop/test_note.md
```

```yaml
files_synced: 1
files_skipped: 0
success: true
```

### See what's stored in the database

```bash
wksc database show nodes --limit 1
```

```yaml
results:
- local_uri: file://lap139160/Users/ww5/Desktop/test_note.md
  bytes: 12
  checksum: 8c265a4f5bd37e9eb94a8e3ba5ac6cd90bb5a1b09cd9f89eb0bd8b5d54a60b04
  priority: 160.0
  remote_uri: null
  timestamp: '2025-12-20T11:50:42.525138'
```

Each node stores the file's URI, content checksum, size, priority, and last-seen timestamp.

### Modify and resync

If you change the file, you need to resync it:

```bash
echo "Added more content" >> ~/Desktop/test_note.md
wksc monitor sync ~/Desktop/test_note.md
```

The checksum and timestamp update. Without resync, the database is stale.

```yaml
results:
- local_uri: file://lap139160/Users/ww5/Desktop/test_note.md
  bytes: 31
  checksum: 8c4f0ea28531db518b211f23cb83ef07eaafec9cd3dd7c5fa48d1dcb47068108
  priority: 160.0
  remote_uri: null
  timestamp: '2025-12-20T11:51:30.806177'
```
---

## 2. Daemon — Automatic File Tracking

The daemon watches for filesystem changes and syncs automatically. Use `--restrict` to limit monitoring to a single directory for testing.

### Create a test directory

```bash
mkdir -p ~/Desktop/wks_test
echo "# File 1" > ~/Desktop/wks_test/note1.md
```

### Start the daemon with --restrict

```bash
wksc daemon start --restrict ~/Desktop/wks_test
```
You can check the daemon status with and should see something like below.

```bash
wksc daemon status

11:54:59 i Checking daemon status...
11:54:59 Progress: Checking daemon status... (10.0%)
11:54:59 Progress: Complete (100.0%)
11:54:59 ✓ Daemon status retrieved
errors: []
warnings: []
running: true
pid: 5008
restrict_dir: /Users/ww5/Desktop/wks_test
log_path: /Users/ww5/.wks/logfile
last_sync: '2025-12-20T16:54:59.646057+00:00'
lock_path: /Users/ww5/.wks/daemon.lock
```

The daemon will automatically sync any new/modified files in the restricted directory.

```bash
touch  ~/Desktop/wks_test/note1.md
```

Another `wksc database show nodes` and you should see:

```yaml
results:
- local_uri: file://lap139160/Users/ww5/Desktop/test_note.md
  bytes: 31
  checksum: 8c4f0ea28531db518b211f23cb83ef07eaafec9cd3dd7c5fa48d1dcb47068108
  priority: 160.0
  remote_uri: null
  timestamp: '2025-12-20T11:51:30.806177'
- local_uri: file://lap139160/Users/ww5/Desktop/wks_test/note1.md
  bytes: 9
  checksum: 4833fb273ef2fff53739f6d82173986120977b3244d8c50ba464dc0ac2fe82a3
  priority: 144.0
  remote_uri: null
  timestamp: '2025-12-20T12:00:27.771300'
```

If you modify the file, the daemon will automatically sync the changes.
```bash
echo "# Line 2" >> ~/Desktop/wks_test/note1.md
```

If you move the file, the daemon will automatically sync the changes.
```bash
mv ~/Desktop/wks_test/note1.md ~/Desktop/wks_test/note2.md
```

If you delete the file, the daemon will automatically sync the changes.
```bash
rm ~/Desktop/wks_test/note2.md
```
Note that deletes sometimes take a few seconds to be updated because we want to be sure the file is really deleted and it wasn't just a temporary rename.

### Stop the daemon

The standard command line mode for the daemon let's you run the daemon and do file system commands for testing in the same terminal instance. For true daemon behavior, such as when you install with a service, you should use `wksc daemon start --blocking`.

Let's stop our daemon.
```bash
wksc daemon stop
```

Check the status
```bash
wksc daemon status
12:11:04 i Checking daemon status...
12:11:04 Progress: Checking daemon status... (10.0%)
12:11:04 Progress: Complete (100.0%)
12:11:04 ✓ Daemon status retrieved
errors: []
warnings: []
running: false
pid: null
restrict_dir: ''
log_path: /Users/ww5/.wks/logfile
last_sync: '2025-12-20T17:07:09.279114+00:00'
lock_path: /Users/ww5/.wks/daemon.lock
```

---

## 3. Vault — Sync Your Links

Parse `[[wikilinks]]` from your vault and store them as edges.

### Sync vault links

```bash
wksc vault sync --recursive ~/_vault
```

```yaml
notes_scanned: 38
links_written: 146
success: true
```

### Find broken links

```bash
wksc vault check
```

```yaml
issues:
- from_uri: vault:///Topics/Workflows.md
  to_uri: vault:///Missing_Note.md
  status: missing_target
is_valid: false
```

### Query links for a file

```bash
wksc vault links ~/_vault/Topics/ORIGEN.md
```

```yaml
edges:
- from_uri: vault:///Topics/Index.md
  to_uri: vault:///Topics/ORIGEN.md
- from_uri: vault:///Topics/ORIGEN.md
  to_uri: vault:///Organizations/SCALE.md
count: 5
```

Use `--direction from` or `--direction to` to filter.

---

## 4. Transform — Convert Documents

Transform files between formats using configured engines.

### Check available engines

```bash
wksc transform list
```

```yaml
engines:
- name: dx
  description: Docling-based document transformer
  supported_formats: [pdf, docx, pptx, html, md, csv, xlsx]
```

### Transform a document

Transform a PDF to markdown:

```bash
wksc transform dx ~/Documents/paper.pdf -o ~/Documents/paper.md
```

```yaml
source_uri: file://hostname/Users/ww5/Documents/paper.pdf
destination_uri: file://hostname/Users/ww5/Documents/paper.md
engine: dx
status: success
checksum: 8c265a4f5bd37e9eb94a8e3ba5ac6cd90bb5a1b09cd9f89eb0bd8b5d54a60b04
processing_time_ms: 1250
cached: false
```

Transformed content is cached—subsequent requests return instantly.

---

## 5. Diff — Compare Files

Compare files using different diff algorithms.

### Text diff (Myers algorithm)

```bash
echo "Hello World" > /tmp/file_a.txt
echo "Hello WKS" > /tmp/file_b.txt
wksc diff -e myers /tmp/file_a.txt /tmp/file_b.txt
```

```yaml
status: success
metadata:
  engine_used: myers
  is_identical: false
  file_type_a: .txt
  file_type_b: .txt
diff_output:
  unified_diff: |
    --- /tmp/file_a.txt
    +++ /tmp/file_b.txt
    @@ -1 +1 @@
    -Hello World
    +Hello WKS
  patch_format: unified
message: Text diff generated.
```

### AST-aware diff (S-expression)

For code files, use the `sexp` engine for structural diffs:

```bash
wksc diff -e sexp --language python file_v1.py file_v2.py
```

This compares the abstract syntax tree rather than raw text, ignoring formatting changes.

### Binary diff (bsdiff3)

For binary files:

```bash
wksc diff -e bsdiff3 old.bin new.bin
```

---

## 6. Link — Query the Edge Database

Low-level commands for querying links by URI.

### Link stats

```bash
wksc link status
```

```yaml
total_links: 146
total_files: 38
```

### Query by URI

```bash
wksc link show vault:///Topics/ORIGEN.md
```

```yaml
links:
- from_local_uri: vault:///Topics/ORIGEN.md
  to_local_uri: vault:///Organizations/SCALE.md
  line_number: 4
```

> [!NOTE]
> `vault links` takes filesystem paths. `link show` takes URIs.

---

## 7. Database — Inspect Raw Data

Query the underlying collections when debugging.

```bash
wksc database show edges --limit 3
```

```yaml
results:
- from_local_uri: vault:///Topics/ORIGEN.md
  to_local_uri: vault:///Organizations/SCALE.md
  line_number: 4
```

---

## 8. Config — Inspect Configuration

View your current configuration settings.

```bash
wksc config show monitor
```

```yaml
section: monitor
content:
  filter:
    include_paths: ['~']
    exclude_paths: ['~/Library']
    # ...
  priority:
    dirs:
      ~/Desktop: 160.0
      '~': 100.0
config_path: /Users/ww5/.wks/config.json
```

Use `wksc config show` to see available sections or see the full config.

---

## 9. Log — Monitor System Health

Check the status of the unified system log.

### Check log status

```bash
wksc log status
```

```yaml
log_path: /Users/ww5/.wks/logfile
size_bytes: 3078
entry_counts:
  debug: 8
  info: 33
  warn: 0
  error: 0
oldest_entry: '2025-12-20T19:36:01.573197+00:00'
newest_entry: '2025-12-20T21:16:29.305802+00:00'
```

### Prune log entries

You can manually prune logs by level (although WKS auto-prunes on access based on retention settings).

```bash
wksc log prune
```

```yaml
pruned_debug: 8
pruned_info: 33
pruned_warnings: 0
pruned_errors: 0
message: Pruned 41 log entries
```


## Command Reference

| Command | Purpose |
|---------|---------|
| `wksc monitor check <path>` | Test if path would be monitored |
| `wksc monitor sync <path>` | Add file to nodes database |
| `wksc monitor status` | Show tracked file count |
| `wksc daemon start --restrict <dir>` | Start watching a directory |
| `wksc daemon stop` | Stop the daemon |
| `wksc vault sync [path]` | Parse and store vault links |
| `wksc vault check` | Find broken links |
| `wksc vault links <file>` | Query edges for a file |
| `wksc link status` | Link collection stats |
| `wksc transform <engine> <path>` | Transform document format |
| `wksc diff -e <engine> <a> <b>` | Compare two files |
| `wksc database show <db>` | Query raw data |
| `wksc database reset all` | Clear all data |
| `wksc config show [section]` | View configuration |
| `wksc log status` | Check log file health |
| `wksc log prune` | Manually prune logs |
