## DB API

This directory implements the database API following a strict one-file-per-function pattern. Each function serves as the single source of truth for both CLI commands (via Typer) and MCP tools (via schema introspection).

### Core Principles

**One file = one thing**: Every exported function or class lives in its own file, and the filename exactly matches the exported symbol name. This eliminates ambiguity and enforces single responsibility.

**Database abstraction**: All database-specific code is isolated in `_<backend>/` subdirectories. The public API in this directory uses database-agnostic interfaces that could be swapped out for other database implementations. Each backend directory contains `_Impl.py` (implementation) and `_DbConfigData.py` (configuration data).

**Pure API layer**: This directory contains zero CLI or MCP-specific code (no printing, no protocol handling). Functions only build and return structured data. Display/rendering happens in the `wks/api/display/` layer.

**StageResult pattern**: All commands return `StageResult` with four stages: announce → progress → result → output. This provides consistent structure for CLI and MCP layers while separating work execution from display.

**Pydantic for input, schemas for output**: Pydantic models validate configuration input. Command outputs use registered output schemas (from `wks/api/_output_schemas/`) to ensure consistent structure. Commands instantiate schema classes and call `.model_dump(mode="python")` to convert to dicts.

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

**Output schemas**: All commands use registered output schemas from `wks/api/_output_schemas/database.py`. Import the schema class, instantiate it with output data, and call `.model_dump(mode="python")` to convert to dict. This ensures type safety and consistent structure.

### Database Configuration

**DatabaseConfig**: The `DatabaseConfig` class in `DatabaseConfig.py` provides unified database configuration with backend-specific data. It's a container that holds backend-specific configuration - backends handle their own connection details.

**Configuration structure**:

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

For `mongomock` (in-memory database), `data` can be empty:

```json
{
  "database": {
    "type": "mongomock",
    "prefix": "wks",
    "data": {}
  }
}
```

**Backend-specific requirements**: Each backend's `_DbConfigData` class defines what it needs:
- `mongo`: Requires `uri` field (MongoDB connection string)
- `mongomock`: Requires nothing (in-memory, no connection needed)

**Backend abstraction**: `DatabaseConfig` doesn't expose backend-specific details. Backend implementations access their config data directly (e.g., `db_config.data.uri` for mongo). This keeps the abstraction clean - `DatabaseConfig` is just a container, backends handle their own connection logic.

**Backend registry**: The `_BACKEND_REGISTRY` in `DatabaseConfig` is the **ONLY** place where backend types are enumerated. To add a new backend:

1. Add an entry to `_BACKEND_REGISTRY` mapping the type name to its config data class
2. Create the backend implementation in `_<backend_type>/` following the existing pattern:
   - `_DbConfigData.py`: Pydantic model defining backend-specific config fields (only require what's needed)
   - `_Impl.py`: Implementation of `_AbstractImpl` that handles connections using its config data
3. The rest of the code will automatically work with the new backend via dynamic imports

**Initialization**: `DatabaseConfig` uses Pydantic's `model_validator(mode="before")` to:
- Validate the `type` is supported (checks `_BACKEND_REGISTRY`)
- Automatically instantiate the correct backend config class from the `data` dict
- Let the backend config class validate itself (e.g., mongo validates URI format)

This means you can simply call `DatabaseConfig(**db_config_dict)` and all validation happens automatically.

**Connection handling**: Backend implementations (`_Impl` classes) handle their own connections:
- They receive `DatabaseConfig` in their `__init__`
- They access backend-specific config via `db_config.data` (e.g., `db_config.data.uri` for mongo)
- They manage connection lifecycle in `__enter__` and `__exit__`
- No need for `get_uri()` or other convenience methods on `DatabaseConfig` - backends are self-contained
