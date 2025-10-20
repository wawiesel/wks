# Wieselquist Knowledge System (WKS)

AI-assisted file organization and knowledge management system.

## Structure

- `SPEC.md` - Complete system specification
- `wks/` - Python package
- `bin/` - Executable scripts
- `scripts/` - Original monitoring scripts (reference)

## Installation

```bash
cd ~/2025-WKS
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Running the Daemon

Preferred (macOS service):

```bash
~/2025-WKS/bin/wks-service install   # writes LaunchAgent, enables, starts
~/2025-WKS/bin/wks-service status    # detailed status via launchctl
~/2025-WKS/bin/wks-service log       # tail daemon log
~/2025-WKS/bin/wks-service restart   # restart the service
~/2025-WKS/bin/wks-service uninstall # stop and remove LaunchAgent
```

Manual (foreground) for quick tests:

```bash
cd ~/2025-WKS && source venv/bin/activate
python -m wks.daemon
```

Single instance: enforced via `~/.wks/daemon.lock`.

## What the Daemon Does

- Monitors home directory for file changes
- Tracks moves, renames, creates, modifications, and deletions
- Updates `~/obsidian/WKS/FileOperations.md` with a reverse chronological log
- Updates `~/obsidian/WKS/ActiveFiles.md` with a concise activity snapshot
- Auto-creates project notes for new `YYYY-ProjectName` directories
- Adds a summary line in `FileOperations.md` showing how many unique files are being tracked (based on the monitor state)

## Archive Structure

WKS follows a hierarchical archiving pattern where old content is moved to `_old/YYYY/` subdirectories:

### Home Directory Archives

Inactive or completed projects from a given year are archived in `~/_old/YYYY/`:

```
~/_old/
├── 2024/
│   └── 2024-OldProjectName/
└── 2025/
    └── 2025-CompletedProject/
```

**Key principles:**
- **No loose files:** Everything must be in a directory, even in `_old/`
- **Year retention:** Archived directories keep their `YYYY-` prefix (e.g., `_old/2025/2025-ProjectName/`)
- **Test/demo code:** Experimental or test directories go to `_old/YYYY/` when no longer needed
- **Delete when appropriate:** Not everything needs to be archived. If content has no future value, delete it rather than cluttering `_old/`

### Project-Level Archives

Active projects can have their own `_old/` subdirectories for versioned content:

```
~/2025-ActiveProject/
├── [current work]
└── _old/
    ├── 2024/          # Content from 2024
    └── 2023/          # Content from 2023
```

This keeps the project workspace focused on current work while preserving historical context.

## Configuration

WKS reads settings from `~/.wks/config.json` if present. This controls which directories are monitored and what is ignored.

Example:

```
{
  "vault_path": "~/obsidian",
  "monitor": {
    "include_paths": [
      "~/2025-WKS",
      "~/deadlines",
      "~/Documents"
    ],
    "exclude_paths": [
      "~/Library",
      "~/obsidian"
    ],
    "ignore_dirnames": [
      "Applications", ".Trash", ".cache", "Cache", "Caches",
      "node_modules", "venv", ".venv", "__pycache__", "build", "_build", "dist"
    ],
    "ignore_globs": [
      ".*", "*.swp", "*.tmp"
    ],
    "state_file": "~/.wks/monitor_state.json",
    "state_rollover": "weekly"  
  },
  "activity": {
    "state_file": "~/.wks/activity_state.json",
    "state_rollover": "weekly"
  },
  "obsidian": {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 40,
    "destination_max_chars": 40
  }
  ,
  "similarity": {
    "enabled": true,
    "mongo_uri": "mongodb://localhost:27027/",
    "database": "wks_similarity",
    "collection": "file_embeddings",
    "model": "all-MiniLM-L6-v2",
    "include_extensions": [],
    "min_chars": 10,
    "max_chars": 5000
  }
}
```

Notes (explicit config):
- All keys shown above are required — the daemon and CLI fail fast if any are missing or empty. No defaults are applied internally.
- Inclusion-first: only paths under `monitor.include_paths` are monitored.
- Exclusions: everything under `monitor.exclude_paths` is ignored.
- Name-based ignores (`monitor.ignore_dirnames`) apply anywhere in the tree.
- Glob ignores (`monitor.ignore_globs`) use shell-style globs. Dotfiles are ignored globally except `.wks`.
- `ignore_patterns` is deprecated — use `ignore_dirnames` and `ignore_globs` only.
- Weekly rollover:
  - Monitor and activity state files are suffixed with the ISO week label (e.g., `monitor_state-2025-W42.json`) when `state_rollover` is `weekly`.
  - You can alternatively embed `{week}` in the path (e.g., `"~/.wks/monitor-{week}.json"`).
  - Obsidian logs are always single-file under `~/obsidian/WKS/`.
- Table width control: `obsidian.logs.source_max` and `destination_max` set the max characters shown for Source/Destination (middle-ellipsized). Defaults aim to fit near 120 columns overall.
 - Vault subdirectory: set `obsidian.base_dir` (e.g., `"WKS"`) to store all WKS-managed notes, links, and logs under a subfolder within the Obsidian vault (e.g., `~/obsidian/WKS/...`). Internal links (like project links to `links/`) are automatically prefixed.
 - FileOperations.md includes a line like `Tracking: N files (as of YYYY-MM-DD HH:MM:SS)` near the top. This count comes from the monitor's state and updates as events are processed.

### Similarity (optional)
- Controlled by the `similarity` section. Enabled by default.
- When enabled, the daemon indexes text content of created/modified files into MongoDB and updates paths on moves. Deleted files are removed from the index.
- Requirements: running MongoDB and first-time model download for `sentence-transformers`.
- `include_extensions`: leave empty (default) to index any file with readable text; set a list (e.g., [".md", ".txt"]) to restrict. `min_chars` skips tiny files. `max_chars` caps the amount of text read per file for a single embedding.
- Extractors: WKS includes lightweight extractors for `.docx`, `.pptx`, and `.pdf`.
  - `.docx`: parses the OOXML document to extract text.
  - `.pptx`: extracts text from all slides.
  - `.pdf`: uses `pdftotext` if available (recommended, via Poppler); otherwise falls back to `strings` for best-effort ASCII.
  - Other files are read as UTF‑8 text with errors ignored.

### Local MongoDB under ~/.wks (optional)
- A helper script is provided to run a local MongoDB for WKS using a dbpath in `~/.wks/mongodb` and port `27027`.

Start/stop/status:

```
~/2025-WKS/bin/wks-mongo start
~/2025-WKS/bin/wks-mongo status
~/2025-WKS/bin/wks-mongo log
~/2025-WKS/bin/wks-mongo stop
```

Notes:
- Requires `mongod` in PATH (install MongoDB Community, e.g., via Homebrew on macOS).
- The default `similarity.mongo_uri` is `mongodb://localhost:27027/` to match the script.

<!-- Removed organizer agent docs to keep scope focused and simple. -->

## Documentation

See [SPEC.md](SPEC.md) for complete system documentation.

## CLI

Install as editable: `pip install -e .` then use `wks`.

- `wks daemon start|stop|status` — manage the background daemon
- `wks config print` — print effective configuration
- `wks mongo start|stop|status|log` — local MongoDB at `~/.wks/mongodb` (port 27027)
- `wks sim index <paths...>` — index files/directories (recursive) for similarity
- `wks sim query --path <file> [--top N --min M --mode file|chunk --json]` — find nearest files to a file
- `wks sim query --text "..." [--top N --min M --mode file|chunk --json]` — find nearest files to text
- `wks sim stats` — show similarity DB stats
- `wks sim route --path <file> [--top N --min M --mode file|chunk --max-targets K --evidence E --json]` — suggest target folders based on the top similar files; aggregates by project root (~/YYYY-Name), Documents subfolder, or deadlines subfolder. Does not move files.
- `wks sim backfill [roots...] [--limit N --json]` — index existing files under the configured include paths (or specified roots), honoring exclude/ignore rules from the config. Useful to build the initial index.

Similarity reads settings from `~/.wks/config.json` under the `similarity` key. All similarity keys are required when `similarity.enabled` is true. No implicit defaults are used.

### Reset logs if corrupted

To reset Obsidian logs (FileOperations.md and ActiveFiles.md) to a clean state:

```
wks obs reset-logs
```

This recreates headers under `~/obsidian/WKS/` and writes an initialization entry. It does not touch any root-level files.
