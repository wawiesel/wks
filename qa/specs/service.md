# Service

The service layer installs and controls the daemon through platform-specific user-service mechanisms.

## Supported Platforms

- macOS launchd
- Linux systemd user services

## Rules

- Installation writes one managed service definition per platform.
- Service startup runs `wksc daemon start --blocking`.
- Stop operations are idempotent.
- Platform-specific code stays behind the shared service abstraction.

## Outputs

- CLI and MCP service commands share one command contract.
- REST does not manage services.
