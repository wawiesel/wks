# Darwin Service Backend

macOS service installation is implemented with user `launchd` jobs.

## Rules

- Install writes one managed plist.
- Start/stop/status remain behind the shared service abstraction.
