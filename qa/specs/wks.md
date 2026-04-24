# WKS

WKS monitors files, transforms content, tracks vault edges, indexes material, and exposes the same behavior through Python, CLI, MCP, and read-only REST.

## Non-Negotiable Surfaces

- `wks/services/`
- `wksc`
- `wksm`
- `wksr`
- Shared behavior lives below transports.
- `cmd_*` wrappers own command contracts and `StageResult`.
- Config loads from `WKS_HOME/config.json`, validates early, and fails hard.
- Database names follow `<prefix>.<collection>`.
- URI creation is centralized.
