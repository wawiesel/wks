## Service API

This directory implements the service API for platform-specific daemon management. The service layer provides install/uninstall/start/stop operations via the OS service manager (launchd on macOS, systemd on Linux).

### Architecture

**Platform abstraction**: Platform-specific code is in `_<platform>/` subdirectories. Each contains `_Impl.py` (implementation) and `_Data.py` (platform-specific config). The public `Service` class validates backend types and instantiates platform implementations via context manager.

**Separation of concerns**:
- **Daemon** (in `wks/api/daemon/`): OS-independent filesystem watcher. Contains all event handling and sync logic.
- **Service** (this directory): OS-dependent installer/manager. Wraps the daemon in a system service.

### Configuration

`ServiceConfig` uses `type/data` pattern:

```json
{
  "service": {
    "type": "darwin",
    "data": {
      "label": "com.example.wks.service",
      "keep_alive": true,
      "run_at_load": false
    }
  }
}
```

**Backend registry**: `_BACKEND_REGISTRY` in `ServiceConfig.py` enumerates supported platforms. To add a platform:
1. Add entry to `_BACKEND_REGISTRY` mapping platform name to config data class
2. Create `_<platform>/` with `_Data.py` and `_Impl.py`
3. Implement install/uninstall/start/stop/status methods

### Commands

- `wksc service install [--restrict <dir>]`: Install daemon as system service
- `wksc service uninstall`: Remove system service
- `wksc service start`: Start the installed service
- `wksc service stop`: Stop the installed service
- `wksc service status`: Check installation and running status

### Adding a New Platform Backend

1. **Add to backend registry**: In `ServiceConfig.py`, add entry to `_BACKEND_REGISTRY`
2. **Create platform directory**: Create `_<platform>/` subdirectory
3. **Implement `_Data.py`**: Pydantic model for platform-specific config fields
4. **Implement `_Impl.py`**: Class inheriting from `_AbstractImpl` with install/uninstall/start/stop/status methods

See `_darwin/` for macOS launchd implementation and `_linux/` for systemd implementation.
