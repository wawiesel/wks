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

### Manual Start (Foreground)

Start the daemon to monitor file changes and update Obsidian:

```bash
cd ~/2025-WKS
source venv/bin/activate
python -m wks.daemon
```

Press `Ctrl+C` to stop.

Single instance: The daemon enforces a single running instance via a lock at `~/.wks/daemon.lock`. If another process is running, a new start will exit immediately.

### Background Process

Run the daemon in the background:

```bash
cd ~/2025-WKS
source venv/bin/activate
nohup python -m wks.daemon > ~/.wks/daemon.log 2>&1 &
echo $! > ~/.wks/daemon.pid
```

To stop the background daemon:

```bash
kill $(cat ~/.wks/daemon.pid)
rm ~/.wks/daemon.pid
```

### System Service (macOS with launchd)

Create a LaunchAgent to run WKS automatically on login:

1. Create the plist file at `~/Library/LaunchAgents/com.wieselquist.wks.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wieselquist.wks</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ww5/2025-WKS/venv/bin/python</string>
        <string>-m</string>
        <string>wks.daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/ww5/2025-WKS</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/ww5/.wks/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ww5/.wks/daemon.error.log</string>
</dict>
</plist>
```

2. Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.wieselquist.wks.plist
```

3. Manage the service:

```bash
# Start
launchctl start com.wieselquist.wks

# Stop
launchctl stop com.wieselquist.wks

# Unload (disable)
launchctl unload ~/Library/LaunchAgents/com.wieselquist.wks.plist

# Check status
launchctl list | grep wks
```

## What the Daemon Does

- Monitors home directory for file changes
- Tracks moves, renames, creates, modifications, and deletions
- Updates `~/obsidian/FileOperations.md` with reverse chronological log
- Updates `~/obsidian/ActiveFiles.md` with activity metrics
- Auto-creates project notes for new `YYYY-ProjectName` directories
- Adds a summary line in `FileOperations.md` showing how many unique files are being tracked (based on the monitor state)

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
      "node_modules", "venv", ".venv", "__pycache__", "build", "dist"
    ],
    "ignore_patterns": [
      ".git", "__pycache__", ".DS_Store", "venv", ".venv", "node_modules"
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
    "logs": {
      "weekly": false,
      "dir": "Logs",            
      "max_entries": 500,
      "source_max": 40,
      "destination_max": 40
    },
    "active": {
      "max_rows": 50
    }
  }
  ,
  "similarity": {
    "enabled": true,
    "mongo_uri": "mongodb://localhost:27027/",
    "database": "wks_similarity",
    "collection": "file_embeddings",
    "model": "all-MiniLM-L6-v2",
    "include_extensions": [".md", ".txt", ".py", ".ipynb", ".tex"],
    "min_chars": 10
  }
}
```

Notes:
- Inclusion-first: only paths under `include_paths` are monitored. If omitted, defaults to your home directory.
- Exclusions: anything under `exclude_paths` is ignored. By default, `~/Library` and `~/obsidian` are excluded.
- Name-based ignores (`ignore_dirnames`) apply to any matching directory name anywhere under monitored roots.
- Pattern ignores (`ignore_patterns`) skip files/paths containing these tokens (simple contains match, not full globbing).
- Glob ignores (`ignore_globs`) use shell-style globs applied to both the full path and the basename (e.g., `.*` to ignore dotfiles). The `.wks` directory is always allowed.
- Weekly rollover:
  - Monitor and activity state files are suffixed with the ISO week label (e.g., `monitor_state-2025-W42.json`) when `state_rollover` is `weekly`.
  - You can alternatively embed `{week}` in the path (e.g., `"~/.wks/monitor-{week}.json"`).
  - Obsidian file operations default to a single `FileOperations.md` file. If you prefer weekly files, set `obsidian.logs.weekly` to true; otherwise a cap of `max_entries` keeps the table short.
  - ActiveFiles.md is a single snapshot. Use `obsidian.active.max_rows` to limit rows shown.
- Table width control: `obsidian.logs.source_max` and `destination_max` set the max characters shown for Source/Destination (middle-ellipsized). Defaults aim to fit near 120 columns overall.
 - Vault subdirectory: set `obsidian.base_dir` (e.g., `"WKS"`) to store all WKS-managed notes, links, and logs under a subfolder within the Obsidian vault (e.g., `~/obsidian/WKS/...`). Internal links (like project links to `links/`) are automatically prefixed.
 - FileOperations.md includes a line like `Tracking: N files (as of YYYY-MM-DD HH:MM:SS)` near the top. This count comes from the monitor's state and updates as events are processed.

### Similarity (optional)
- Controlled by the `similarity` section. Enabled by default.
- When enabled, the daemon indexes text content of created/modified files (by extension) into MongoDB and updates paths on moves. Deleted files are removed from the index.
- Requirements: running MongoDB and first-time model download for `sentence-transformers`.
- Configure `include_extensions` and `min_chars` to scope indexing and avoid tiny/non-text files.

### Local MongoDB under ~/.wks
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

## Documentation

See [SPEC.md](SPEC.md) for complete system documentation.
