## Monitor API

Single-source monitor commands live here. Each command is a plain function, one per file, registered on the Typer app and reused by MCP.

### Layout
- `app.py` — Typer app; wires commands via the StageResult-aware wrapper.
- `cmd_*.py` — one command per file (status, check, sync, filter show/add/remove, priority show/add/remove). File name == function name.
- `_*.py` — private helpers, exactly one function or class per file. The exported name must begin with `_` and reflect the file name (e.g., `_sync_execute.py` → `_sync_execute`, `_check_build_decisions.py` → `_check_build_decisions_from_trace`).
- `MonitorConfig.py` — monitor config model.
- `_*.py` models — one Pydantic model per file, private (e.g., `_MonitorStatus`, `_ConfigValidationResult`, `_PriorityDirectoriesResult`, `_ManagedDirectoryInfo`, `_ListOperationResult`).

### Naming rules
- Public commands: `cmd_<name>.py` contains only `cmd_<name>()`.
- Private helpers: file starts with `_` and exports only symbols starting with `_` that align with the filename.
- Models: private, one per file, named with leading `_` matching the file.
- Constants: private constants start with `_` (e.g., `_LIST_NAMES`).
- No mixed exports: do not define multiple public helpers/classes in one file.

### Patterns

- **No CLI/MCP-specific code or printing** here. Functions only build/return structured data; downstream layers decide how to render/transport it.
- **Config**: load via `WKSConfig.load()` inside the function (or inject later) but keep signatures simple.
- **Schemas**: MCP schemas come from Typer command signatures (see `get_typer_command_schema` in `wks/api/base.py`).
- **StageResult + progress (mandatory)**: All command functions return a `StageResult` (announce → progress → result → output) and use `StageResult.progress_callback` (accepts `(description, progress)`) instead of yielding/printing—no direct prints; surface everything via the callback/output payload.

### Responsibilities
- Do: keep command logic thin and call underlying monitor helpers/controllers.
- Do: ensure outputs are structured dicts (no printing); CLI formatting is added by the display layer.
- Avoid: duplicating schema/arg definitions in CLI or MCP; Typer signature is the source of truth.
