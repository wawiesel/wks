# Contributing to WKS

Follow `.cursor/rules/*` and [AGENTS.md](AGENTS.md) first.

## Core Rules

- Use the shared internal Python service/core API plus thin CLI, MCP, and read-only REST surfaces.
- REST support is mandatory.
- Keep one command contract per `cmd_*` file.
- Do not duplicate business logic across transports.
- Use dataclasses and strict validation at the boundary.
- Remove fallback behavior and dead code.
- Keep CLI stdout content-only. Status, progress, warnings, and failures go to stderr.

## Setup

```bash
python3 -m venv venv
venv/bin/pip install -e .
```

Install any extra local tooling into `venv`.

## Daily Workflow

1. Check which `.cursor/rules/*` apply.
2. Read existing wrappers, handlers, and facades before adding new logic.
3. Make the change.
4. Run the required checks from `venv`.
5. Commit with a Conventional Commit message.

## Required Checks

Run these before pushing:

```bash
venv/bin/python scripts/check_format.py --fix
venv/bin/python scripts/check_types.py
venv/bin/python scripts/check_complexity.py
venv/bin/pytest
```

Focused suites are still available:

```bash
venv/bin/python scripts/test_smoke.py
venv/bin/python scripts/test_unit.py
venv/bin/python scripts/test_integration.py
```

## Commits

Use Conventional Commits:

- `feat: ...`
- `fix: ...`
- `refactor: ...`
- `test: ...`
- `docs: ...`
- `chore: ...`

## Architecture

### Service Layer

- Lives in `wks/services/`
- Contains shared typed logic
- No `StageResult`
- No CLI, MCP, or REST protocol code

### Command Layer

- Lives in `wks/api/*/cmd*.py`
- Preserves the command contract
- Wraps shared behavior into `StageResult`
- Remains the traceable per-command boundary

### Transports

- CLI in `wks/cli/`
- MCP in `wks/mcp/`
- REST in `wks/rest/`

Transport responsibilities are limited to parsing, wiring, serialization, and display.

## Testing Strategy

- Deep tests belong in the shared service/core layer.
- Per-command tests stay mapped to individual command wrappers.
- CLI, MCP, and REST use smoke or wiring-focused tests.
- Prefer real workflows over paper-thin tests.

Naming:

- `test_wks_service_<domain>.py`
- `test_wks_api_<domain>_<command>.py`
- `test_wks_cli_<domain>.py`
- `test_mcp_<domain>.py`
- `test_rest_<domain>.py`

## Generated Outputs

Generated metrics and traceability reports are not tracked in git. Regenerate them when needed:

```bash
venv/bin/python scripts/generate_all_stats.py
```

`README.md` contains a compact generated metrics block maintained by `scripts/update_readme_stats.py`.

## Quality Limits

- Function CCN must stay at or below `10`.
- Function NLOC must stay at or below `100`.
- Files over `900` lines must be split.
- Prefer explicit errors with concrete paths, expected values, and found values.

## CI

GitHub Actions enforces the same format, type, complexity, and test expectations. Local results should match CI results when run from `venv`.
