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

Use Conventional Commits such as `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, or `chore:`.

## Architecture

- `wks/services/`: shared typed logic, no transport protocol code
- `wks/api/*/cmd*.py`: per-command contract wrappers returning `StageResult`
- `wks/cli/`, `wks/mcp/`, `wks/rest/`: thin parsing, wiring, serialization, and display layers

## Quality Limits

- Function CCN must stay at or below `10`.
- Function NLOC must stay at or below `100`.
- Files over `900` lines must be split.
- Prefer explicit errors with concrete paths, expected values, and found values.
