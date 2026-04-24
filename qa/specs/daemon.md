# Daemon

The daemon performs blocking filesystem monitoring and sync work.

## Rules

- Service startup delegates to `wksc daemon start --blocking`.
- Daemon state is reported through typed status output.
