# Daemon API (UNO)

This directory implements the daemon runtime (filesystem watcher). It follows the **UNO pattern**: one file, one definitional unit.

## Files
- `Daemon.py` — public daemon API (start/stop/status, get_filesystem_events, clear_events)
- `DaemonConfig.py` — daemon configuration model (all fields required)
- `FilesystemEvents.py` — dataclass for accumulated events
- `cmd_start.py` — API command to start the daemon (StageResult + schema output)
- `cmd_stop.py` — API command to stop the daemon
- `cmd_status.py` — API command to report daemon status
- `__init__.py` — schema registration and public exports

## Behavior
- Daemon loads `WKSConfig` from `WKS_HOME`, uses `daemon` config.
- Filesystem watching via `watchdog` observer; events accumulated and retrievable via `get_filesystem_events()`.
- `restrict_dir` is required in config; empty string means fall back to monitor include paths.
- All outputs must match `docs/specifications/daemon_output.schema.json`.

## Testing
- See `tests/unit/test_wks_api_daemon_Daemon.py` for TDD scaffold exercising the public API with real filesystem events.

