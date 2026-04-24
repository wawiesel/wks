# WKS Package Layout

`wks/` contains the shared runtime layers:

- `services/`: typed shared business logic and `WKSService`
- `api/`: command wrappers returning `StageResult`
- `cli/`: thin Typer transport over command wrappers
- `mcp/`: thin MCP transport over command wrappers
- `rest/`: thin read-only FastAPI transport over shared services

Execution shape:

```text
Python -> services/core
CLI    -> cmd_* -> services/core
MCP    -> cmd_* -> services/core
REST   -> services/core
```

The rule is simple: shared behavior does not live in transports.
