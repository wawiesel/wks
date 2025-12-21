# Linux (systemd) Backend Implementation

This directory contains the Linux-specific implementation of the service API using systemd user services for service management.

## Linux-Specific Details

**Service Management**: Linux uses systemd for service management. User services are defined via unit files in `~/.config/systemd/user/` and managed via `systemctl --user` commands.

## Implementation Strategy

### Service Management

The implementation uses systemd user services (`systemctl --user`) for service management. See `_Impl.py` for the actual implementation.

**Service Installation**: The service unit file is created in `~/.config/systemd/user/` and runs `wksc daemon start` which handles the actual filesystem monitoring.

**Event Handling**: Filesystem monitoring is handled by the daemon itself (via `wksc daemon start`), not by the service implementation. The service implementation only manages the systemd service lifecycle.

### Unit File Structure

The systemd unit file includes:
- `[Unit]`: Service description and dependencies
- `[Service]`: ExecStart command, working directory, logging, restart policy
- `[Install]`: Service enablement target

**Working Directory**: Always `WKS_HOME` (from `WKSConfig.get_home_dir()`)

**Logging**: Uses unified log file at `{WKS_HOME}/logfile`

**Restart Policy**: `Restart=always` with `RestartSec=10` to automatically restart the service if it crashes

### Service Lifecycle

1. **Install**: Creates unit file, reloads systemd daemon, optionally enables service
2. **Uninstall**: Stops service, disables service, removes unit file, reloads systemd daemon
3. **Start**: Starts service via `systemctl --user start`
4. **Stop**: Stops service via `systemctl --user stop`
5. **Status**: Checks if unit file exists, if service is active, and retrieves PID if running
