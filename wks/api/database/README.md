## DB API

This directory implements the database API following a strict one-file-per-function pattern. Each function serves as the single source of truth for both CLI commands (via Typer) and MCP tools (via schema introspection).

### Core Principles

**One file = one thing**: Every exported function or class lives in its own file, and the filename exactly matches the exported symbol name. This eliminates ambiguity and enforces single responsibility.

**Database abstraction**: All database-specific code is isolated in `_<backend>/` subdirectories. The public API in this directory uses database-agnostic interfaces that could be swapped out for other database implementations. Each backend directory contains `_Impl.py` (implementation) and `_DbConfigData.py` (configuration data).

**Pure API layer**: This directory contains zero CLI or MCP-specific code (no printing, no protocol handling). Functions only build and return structured data. Display/rendering happens in the `wks/api/display/` layer.

**StageResult pattern**: All commands return `StageResult` with four stages: announce → progress → result → output. This provides consistent structure for CLI and MCP layers while separating work execution from display.

**Pydantic for input, dicts for output**: Pydantic models validate configuration input. Command outputs are plain `dict[str, Any]` for flexibility. No Pydantic models for command results.

**Inline when used once**: Helper functions are kept separate only if used multiple times or substantial enough to warrant separation. Functions used once are inlined into their callers to reduce unnecessary abstraction.

**Unit test public functions**: All public functions (those without a leading `_`) must have unit tests. Private helpers (`_*`) are tested indirectly through their callers.

### Naming Conventions

- **Public commands**: `cmd_<name>.py` → `cmd_<name>()`
- **Private helpers**: `_<name>.py` → `_<name>()` or `_<Name>`
- **Public helpers**: `<name>.py` → `<name>()` (no leading underscore)
- **Database implementations**: `_<backend>/<name>.py` → `<name>()` or `<Name>`

### Patterns

**Command structure**: Commands are plain Python functions with Typer annotations. They return `StageResult` containing structured data. The `handle_stage_result()` wrapper in `app.py` executes progress callbacks if present.

**Database access**: Use `Database` context manager from `Database.py` for database operations, or `Database.query()` classmethod for simple pass-through queries. 

### Database Configuration

**DbConfig**: The `DbConfig` class in `DbConfig.py` provides unified database configuration with backend-specific data. The configuration structure is:

```json
{
  "database": {
    "type": "mongo",
    "prefix": "wks",
    "data": {
      "uri": "mongodb://localhost:27017/"
    }
  }
}
```

The `prefix` field is required and specifies the database name prefix. For example, with `prefix: "wks"`, a database named `"monitor"` in config is accessed as `"wks.monitor"` in the backend. Users should specify just the database name (e.g., `"monitor"`) when using `Database` - the prefix is handled automatically.

**Backend registry**: The `_BACKEND_REGISTRY` in `DbConfig` is the **ONLY** place where backend types are enumerated. To add a new backend:

1. Add an entry to `_BACKEND_REGISTRY` mapping the type name to its config data class
2. Create the backend implementation in `_<backend_type>/` following the existing pattern
3. The rest of the code will automatically work with the new backend via dynamic imports

**Initialization**: `DbConfig` uses Pydantic's `model_validator(mode="before")` to:
- Validate the `type` is supported
- Automatically instantiate the correct backend config class from the `data` dict
- Let the backend config class validate itself

This means you can simply call `DbConfig(**db_config_dict)` and all validation happens automatically.
