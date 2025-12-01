## Priority 1

Make MCP consistent with CLI for all commands through "diff" in @SPEC.md.

- wksm_config (was wks_config)
- wksm_monitor (was wks_monitor)
- wksm_vault (was wks_vault)
- wksm_transform (was wks_transform)
- wksm_cat (was wks_cat)
- wksm_diff (was wks_diff)

There should be no code that is not used by the MCP or CLI. There should be 100% code coverage in unit tests. There should be smoke tests for the MCP and CLI. 
Follow @CONTRIBUTING.md for contribution guidelines.
Follow @.cursor/rules/important.mdc for important rules.

Refactor code to remove duplication and have better structure.
Delete all unused code.

### Code Organization

**Architecture Layers:**
1. **Python API** (`wks/` modules): All business logic in controllers (e.g., `wks.monitor.controller`, `wks.transform.controller`, `wks.vault.controller`, `wks.diff.controller`)
2. **MCP Layer** (`wks/mcp_server.py`): Thin wrapper that calls API, returns structured `MCPResult`
3. **CLI Layer** (`wks/cli/`): Thin wrapper that calls MCP tools, formats output

**Organization:**
- CLI: `wks/cli/__init__.py` contains all simple MCP-wrapped commands (transform, cat, diff, etc.)
- Commands with subcommands or special formatting can be in separate files but still only call MCP
- No business logic in CLI - it's strictly argument parsing → MCP call → output formatting
- Controllers accessible via `wks.monitor.controller`, `wks.transform.controller`, etc.
- Engines accessible via `wks.transform.engines`, `wks.diff.engines`

### Renaming

Rename the command line `wksc` instead of `wks0`:
- Update `setup.py` entry_points
- Update CLI parser `prog` argument
- Update version strings
- Update service controller labels
- Update smoke tests
- Update SPEC.md documentation
- Update all test references

Rename the MCP tools to `wksm_*` instead of `wks_*`:
- Update all tool names in MCP server
- Update tool registry keys and handler references
- Update smoke tests to use new names
- Update SPEC.md documentation

### Locality of Data Principle

Locality of data is important: Config files and data structures should be defined close to where they are used.

- Vault config should be located next to vault code (e.g., `wks/vault/config.py`)
- Monitor config should be next to monitor code (e.g., `wks/monitor/config.py`)
- Transform config should be next to transform code (e.g., `wks/transform/config.py`)
- During refactoring, verify and move any config definitions that are not colocated with their usage
- Central config loading in `wks/config.py` should reference/import from layer-specific config modules, not define them

### Engine-Specific Config Organization

When engines are introduced, engine-specific config should be in separate files:
- Docling config for transform engine should be at `wks/transform/docling/config.py`
- Myers diff engine config should be at `wks/diff/myers/config.py`
- Each engine's config module defines its own parameters, defaults, validation, and schema

### Single Source of Truth for Arguments

CLI arguments, MCP parameters, and config defaults must be defined in ONE place.

- The engine's config module (e.g., `wks/transform/docling/config.py`) should define:
  - Parameter names and types
  - Default values
  - Validation rules
  - Schema for MCP inputSchema
  - Argument parser definitions for CLI
- CLI and MCP should import and reference this single definition, not duplicate it
- This ensures consistency across all interfaces and reduces maintenance burden
- Refactor existing code to consolidate argument definitions into engine-specific config modules

### MCP and CLI Consistency

**All CLI commands must call MCP tools - no exceptions:**
- Every CLI command is: parse arguments → call `call_tool("wksm_*", args)` → format output
- Verify all CLI subcommands have corresponding MCP tools
- Add missing MCP tools if any CLI functionality is missing
- Ensure parameter validation matches between CLI and MCP
- Ensure feature parity for all commands through "diff" layer
- Refactor any CLI commands that contain business logic to use MCP tools instead
- Commands like monitor, vault, service, config must all call MCP tools, not implement logic directly

### Test Coverage

- Run coverage analysis to identify gaps
- Add unit tests for all uncovered code paths
- Ensure all controller methods are tested
- Ensure all CLI commands have tests
- Ensure all MCP tools have tests
- Update smoke tests: Use `wksc` instead of `wks0`, use `wksm_*` tool names
- Confirm `.coveragerc` has `fail_under = 100`
- Ensure all tests pass

### Code Quality

- Follow CONTRIBUTING.md guidelines:
  - CCN ≤ 10 per function
  - NLOC ≤ 100 per function
  - Keep files ≤ 900 lines
  - Use dataclasses for configs
  - Follow error handling patterns
- Remove duplication:
  - Ensure CLI and MCP share controllers (zero duplication)
  - Consolidate display logic
  - Share validation logic


## Priority 2

Revisit all the existing test code to make it more beautiful.

Tests should be simple and easy to read.
If the tests, pass then the capability referenced in @SPEC.md has been implemented successfully. If the tests fail then the capability referenced in @SPEC.md has not been implemented successfully. There must be logical equivalence between these. 
Do this only for the commands that are implemented, i.e. not index, search, or patterns.

## Priority 3

Implement the commands of index and search.

## Priority 4

Implement the patterns capability.