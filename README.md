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

## Documentation

See [SPEC.md](SPEC.md) for complete system documentation.
