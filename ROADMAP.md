# WKS Roadmap

A forward-looking view of outcomes and constraints. Use this as a compass; the checklists live in `TASKS.md`.

## Phase 1 — Foundation (DONE)

Outcome: A clean baseline with structure, a minimal vault, and a settled spec.
Exit criteria:
- Home has year-scoped work roots; vault skeleton exists; spec is versioned.

## Phase 2 — Migration (DONE)

Outcome: Legacy material is re-homed; staging areas are quiet; embeds reflect truth.
Exit criteria:
- Legacy trees are archived or adopted; loose files are routed; embeds resolve.

## Phase 3 — Agent (IN PROGRESS)

Outcome: A background agent keeps filesystem and vault in sync with minimal noise.
Exit criteria:
- Link drift is corrected automatically; actionable suggestions are surfaced sparingly.

### Recent Cleanup Work (2025-11-13)

**CLI Refactoring & Cleanup**:
- Split monolithic `wks/cli.py` (3122 lines) into modular structure:
  - `wks/cli/main.py` - Main entry point and argument parsing
  - `wks/cli/commands/` - Command-specific modules (service, monitor, config, index, related, db)
  - `wks/cli/display_strategies.py` - Display mode strategies (CLI/MCP)
  - `wks/cli/helpers.py` - Shared helper functions
  - `wks/cli/dataclasses.py` - CLI-specific dataclasses
  - `wks/cli/constants.py` - CLI constants
- Renamed CLI from `wkso` to `wks0` (dev version)
- Unified table display format for `service status` and `monitor status`:
  - Reflowing two-column layout with panels
  - Health section on left, File System on right for service status
  - Bold cyan headings for section headers
  - Consistent styling with `MAX_DISPLAY_WIDTH = 80`
- Added `--live` option to both `service status` and `monitor status` for auto-updating displays
- Standardized CLI output: 4-step process (STDERR for status/progress, STDOUT for output)
- Removed all backward compatibility code and hedging
- Applied fail-hard principle: explicit validation, no defaults/fallbacks
- Reduced complexity: refactored functions with CCN>10 or NLOC>100
- Used dataclasses instead of dicts for internal data structures
- Applied design patterns: Registry, Builder, Strategy

**Status**: Service, monitor, config, and db commands are in good shape. **Next: Vault layer.**

## Phase 4 — Iteration

Outcome: The system improves through measured changes tied to real usage.
Exit criteria:
- A light review cadence exists; pain points are logged and addressed.

## Constraints

- Prefer offline operation and local models.
- Keep the vault readable without plugins; treat helpers as optional.
- Favor small, reversible changes over large refactors.

## Risk Notes

- Naming drift can obscure meaning → normalize proactively.
- Embeds can stale when files move → maintain a consistent `_links/` hub.
- Automation can overreach → require explicit opt‑in for destructive changes.
