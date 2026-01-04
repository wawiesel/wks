## Monitor API

This directory implements the monitor API following a strict one-file-per-function pattern. Each command function serves as the single source of truth for both CLI commands (via Typer) and MCP tools (via schema introspection).

### Core Principles

**One file = one thing**: Every exported function or class lives in its own file, and the filename exactly matches the exported symbol name. This eliminates ambiguity and enforces single responsibility.

**Single source of truth**: Command functions are defined once and reused by both CLI (Typer) and MCP (schema introspection). Typer command signatures are the authoritative schema—no duplicate definitions.

**Pure API layer**: This directory contains zero CLI or MCP-specific code (no printing, no protocol handling). Functions only build and return structured data. Display/rendering happens in the `wks/display/` layer.

**StageResult pattern**: All commands return `StageResult` with four stages: announce → progress → result → output. This provides consistent structure for CLI and MCP layers while separating work execution from display.

**Pydantic for input, schemas for output**: Pydantic models validate configuration input. Command outputs use registered output schemas from normative JSON schemas in `qa/specs/monitor_output.schema.json`. Schemas are auto-registered via `schema_loader.register_from_schema("monitor")` in `__init__.py`. Commands instantiate schema classes (e.g., `MonitorStatusOutput`) and call `.model_dump(mode="python")` to convert to dicts. The JSON schema is the single source of truth - Pydantic models are dynamically generated from it.

**Inline when used once**: Helper functions are kept separate only if used multiple times or substantial enough to warrant separation. Functions used once are inlined into their callers to reduce unnecessary abstraction.

**Unit test public functions**: All public functions (those without a leading `_`) must have unit tests. Private helpers (`_*`) are tested indirectly through their callers.

**Help on missing arguments**: Commands that require positional arguments should use `str | None = typer.Argument(None, ...)` for those arguments. The `handle_stage_result()` wrapper automatically detects `None` values and shows help (CLI only), so no manual checks are needed. MCP validates parameters separately using `_require_params` decorator, so this behavior only applies to CLI. Example:

```python
def cmd_sync(
    path: str | None = typer.Argument(None, help="File or directory path to sync"),
) -> StageResult:
    # No need to check for None - handle_stage_result does it automatically for CLI
    # MCP validates parameters separately before calling this function
    # ... rest of function
```

### Naming Conventions

- **Public commands**: `cmd_<name>.py` → `cmd_<name>()`
- **Private helpers**: `_<name>.py` → `_<name>()` or `_<Name>`
- **Public helpers**: `<name>.py` → `<name>()` (no leading underscore)
- **Config models**: `*Config.py` → `*Config` or `_*Config`
- **Constants**: Use class methods (e.g., `MonitorConfig.get_filter_list_names()`)

### Patterns

**Config loading**: Commands load config via `WKSConfig.load()` inside the function body. This keeps signatures simple and makes testing easy via mocking.

**Command structure**: Commands are plain Python functions with Typer annotations. They return `StageResult` containing structured data. The `handle_stage_result()` wrapper in `app.py` executes progress callbacks if present.

**Schema generation**: MCP schemas are generated via introspection of Typer signatures using `get_typer_command_schema()`. No separate schema definitions needed.

### Examples

**Command Function**:
```python
# cmd_status.py
def cmd_status() -> StageResult:
    """Get filesystem monitoring status and configuration."""
    from ...config import WKSConfig
    config = WKSConfig.load()
    monitor_cfg = config.monitor
    # ... build result dict
    return StageResult(
        announce="Checking monitor status...",
        result="Monitor status retrieved",
        output={"tracked_files": 42, "success": True},
    )
```

**Helper Function**:
```python
# explain_path.py
def explain_path(cfg: MonitorConfig, path: Path) -> tuple[bool, list[str]]:
    """Explain why a path is allowed or excluded."""
    # ... logic
    return allowed, trace
```

**Registration**:
```python
# app.py
monitor_app.command(name="status")(handle_stage_result(cmd_status))
```
