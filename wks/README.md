# WKS Package Layout

- `services/`: typed shared business logic and `WKSService`
- `api/`: command wrappers returning `StageResult`
- `cli/`: thin Typer transport over command wrappers
- `mcp/`: thin MCP transport over command wrappers
- `rest/`: thin read-only FastAPI transport over shared services

```text
Python -> services/core
CLI    -> cmd_* -> services/core
MCP    -> cmd_* -> services/core
REST   -> services/core
```
