# Status Specification

## Purpose
Top-level aggregation command that reports system health across all subsystems in a single view.

## CLI

- Entry: `wksc status` (top-level command, not a subgroup)
- Output formats: `--display yaml` (default) or `--display json`
- Rich formatting: When displayed as yaml (default), uses color-coded Rich output. Structured output via `-d json` or `-q`.

### status
- Command: `wksc status`
- Behavior: Runs status commands from each subsystem and aggregates results into a single output.
- Subsystems queried (in order): service, log, monitor, link, vault.
- Each subsystem returns its own output dict; errors in one subsystem do not block others.
- Output: Dict with keys `service`, `log`, `monitor`, `link`, `vault`, each containing the respective subsystem's status output (or `{"error": "..."}` on failure).

## MCP

| Tool | Description |
|------|-------------|
| `wksm_status()` | Get aggregated system status |

- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Individual subsystem failures are captured as `{"error": "..."}` within the output; the overall command still succeeds.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- STATUS.1 — `wksc status` aggregates status from service, log, monitor, link, and vault.
- STATUS.2 — Subsystem failures are isolated; one failing subsystem does not block others.
- STATUS.3 — CLI/MCP parity: same data and structure for equivalent commands.
