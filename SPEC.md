# WKS Command-Line Utility (wkso)

This spec documents the wkso CLI: a minimal, focused interface to configure, run, and index the WKS agent. It intentionally covers only three command groups: config, service, and index.

## Overview
- Purpose: Keep filesystem and Obsidian in sync, maintain embeddings + change history, and surface activity.
- Scope: Single CLI `wkso` with commands:
  - `wkso config` — inspect effective configuration
  - `wkso service` — install/start/stop the background daemon (macOS launchd support)
  - `wkso index` — add files/directories to the similarity database with progress and Docs output
  - `wkso db` — query or reset Mongo collections that back the similarity/time databases

## Installation
- Recommended: pipx
  - `pipx install .`
  - If using Docling extraction: `pipx runpip wkso install docling`
- Python: 3.10+

## Configuration
- File: `~/.wks/config.json`
- Minimal keys (examples shown):
  - Top-level: `"vault_path": "~/obsidian"`
  - `obsidian`: `{ "base_dir": "WKS", "log_max_entries": 500, "active_files_max_rows": 50, "source_max_chars": 40, "destination_max_chars": 40, "docs_keep": 99 }`
  - `monitor`: `{ "include_paths": ["~"], "exclude_paths": ["~/Library","~/obsidian","~/.wks"], "ignore_dirnames": [".git","_build"], "ignore_globs": ["*.tmp","*~","._*"], "state_file": "~/.wks/monitor_state.json" }`
  - `display`: `{ "timestamp_format": "%Y-%m-%d %H:%M:%S" }`
  - `mongo`: `{ "uri": "mongodb://localhost:27027/", "space_database": "wks_similarity", "space_collection": "file_embeddings", "time_database": "wks_similarity", "time_collection": "file_snapshots" }`
  - `similarity`: `{ "enabled": true, "model": "all-MiniLM-L6-v2", "include_extensions": [".md",".txt",".py",".ipynb",".tex",".docx",".pptx",".pdf",".html",".csv",".xlsx"], "min_chars": 10, "max_chars": 200000, "chunk_chars": 1500, "chunk_overlap": 200, "offline": true }`
  - `extract`: `{ "engine": "docling", "ocr": false, "timeout_secs": 30 }` (Docling is required)

## Commands

Global options:
- `--version` — print the installed CLI version (with current git SHA when available) and exit immediately.
- `--display {auto,rich,basic}` — select the output style for subcommands (default `rich`).

### wkso config
- `wkso config print` — print the effective JSON config to stdout.

### wkso service
- Purpose: Manage the long‑running daemon that monitors files, writes FileOperations/ActiveFiles/Health in `~/obsidian/<base_dir>`, and updates embeddings.
- macOS launchd:
  - `wkso service install` — write `~/Library/LaunchAgents/com.wieselquist.wkso.plist`, bootstrap, and start.
  - `wkso service install` ensures the configured MongoDB endpoint is reachable; when using the default `localhost:27027`, it auto-starts a local `mongod` if needed.
  - `wkso service uninstall` — unload and remove the plist (cleans up legacy labels).
- Start/stop/status (works with or without launchd):
  - `wkso service start` — verify Mongo is running (auto-start local `mongod` when configured), then start via launchd if installed, else start a background process.
  - `wkso service stop` — stop the running daemon and shut down the managed `mongod` if we launched it.
  - `wkso service status` — print daemon status.
  - `wkso service restart` — restart daemon (via launchd if present).

Database responsibilities
- The service maintains a file database keyed by path that tracks: path, checksum, embedding, date last modified, last operation, number of bytes, and angle from empty (the angle between the file’s embedding and the embedding of the empty string). Embeddings are computed per the configured strategy (Docling extraction + sentence-transformers as currently deployed).
- The database powers de‑duplication, similarity checks, and RAG‑like queries. Moves/renames are recognized via matching checksum so we avoid creating new logical entries on path changes. We do not use the checksum as the primary key; path remains the key so when a file at a path is updated, all metadata updates in place without changing the key.
- Primary views today:
  - `FileOperations.md`: a Markdown view of the top N most recent changes. It should show checksum, date last modified, last operation, human‑readable size, and angle from empty (or `-` if unavailable). Temp/autosave artifacts are hidden in this view.
- `Health.md`: a dashboard of current status and metrics.

Change Snapshots Database (planned)
- Purpose: Maintain a time-dependent history of content changes per file, respecting moves/renames and avoiding duplicate logical entries.
- Key behaviors:
  - Path remains the primary identity; moves/renames do not create new logical entries when the checksum is unchanged (records are renamed in-place).
  - On content change, create a snapshot record with: `path`, `t_prev`, `t_new`, `checksum_new`, `checksum_prev`, `bytes_delta`, `size_bytes_new`, `size_bytes_prev`, `angle_delta` (from embedding_changes), and `binary_patch_size` (size in bytes from bsdiff4 on previous vs new content). Binary diff runs for every change, regardless of embedding availability.
  - History access: must be able to list all change times in the past week per file, and always include at least the most recent modification.
- Implementation notes:
  - Collection name: `file_snapshots` (MongoDB). Indices on `(path, t_new_epoch)`.
  - Binary diff: use `bsdiff4.file_diff(old, new, patch)` to compute a temp patch, measure size, and dispose; store `binary_patch_size` only (not the patch content).
  - Angle from empty and change angle derive from the embedding DB: `angle_delta` aligns with entries in `embedding_changes`.
  - Large files: consider a configurable size cap for diffing; still record metadata when skipped.

Notes
- Single instance enforced via `~/.wks/daemon.lock`.
- Health: `~/.wks/health.json` and `~/obsidian/<base_dir>/Health.md`.
- FileOperations: rebuilt from `~/.wks/file_ops.jsonl` with temp/autosaves hidden in the page view.

### wkso index
- Purpose: Add files and directories to the similarity DB and write Docs snapshots.
- Usage:
  - `wkso index <path ...>` — each path may be a file or directory; directories are processed recursively.
- Behavior:
  - Filters files by `similarity.include_extensions`.
  - For each file: extracts text (Docling or configured engine), computes embeddings, records change angle, and writes `~/obsidian/<base_dir>/Docs/<checksum>.md` when updated.
  - Shows a progress bar with ETA and current filename; prints a final summary.

### wkso db
- Purpose: Provide lightweight access to the Mongo databases that power similarity (space) and change snapshots (time) without requiring Docling/model startup.
- Subcommands:
  - `wkso db query --space|--time [--filter JSON] [--projection JSON] [--sort field:asc|desc] [--limit N]` — run raw Mongo queries against the selected logical store.
    - `--space` targets the embeddings collection (`similarity.collection`, default `file_embeddings`).
    - `--time` targets the snapshots collection (`similarity.snapshots_collection`, default `file_snapshots`).
    - Works with minimal config: `mongo.uri`, `mongo.space_database`, and `mongo.space_collection`; all default to the canonical values if missing.
  - `wkso db info [--space|--time] [-n N]` — print counts and list the most recent files/snapshots using short Mongo timeouts for responsiveness.
    - Defaults to the space database when neither `--space` nor `--time` is supplied.
    - `-n/--latest` shows the latest N entries (default 10).
    - When using the default local URI, the command auto-starts `mongod` if it is not already running.
    - Space view columns: timestamp, path, checksum, chunk count, and on-disk size. Time/snapshot view columns: t_new, path, checksum, size, and byte delta.
  - `wkso db reset` — drop the configured database and remove the local `~/.wks/mongodb` data directory; best-effort stop of local `mongod` on port 27027.
- Error handling: all db commands report connection failures succinctly (`DB connection failed`/`DB unreachable`) and exit non‑zero when Mongo cannot be reached.

## Output Surfaces (daemon)
- `WKS/FileOperations.md` — reverse chronological operations log (auditable ledger; temp/autosaves hidden in view).
- `WKS/ActiveFiles.md` — sorted by |°/hr| from embedding_changes (1h/1d/1w windows; sign preserved).
- `WKS/Health.md` — heartbeat, metrics, links.
- `WKS/Docs/` — extracted text snapshots by checksum (latest N kept).

## Safety & Defaults
- Writes only under `~/obsidian/<base_dir>`.
- Respects ignore rules (`exclude_paths`, `ignore_dirnames`, `ignore_globs`).
- Avoids duplicate daemons; stale locks are cleaned when possible.
