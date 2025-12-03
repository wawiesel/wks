# Patterns Layer Specification

**Vision**: Simple script-based organizational patterns with MCP server for AI access. Scripts are the source of truth for both code and documentation.

**Status**: Future work. Pattern discovery and execution are not yet implemented; the interfaces below represent the intended roadmap.

**Architecture**:
- **Location**: `~/.wks/patterns/` (configurable)
- **Format**: Executable scripts (bash, python, etc.)
- **Documentation**: Extracted from script header comments

**How It Works**:
- **Discovery**: WKS scans the patterns directory for executable scripts.
- **Documentation**: Header comments are parsed to provide tool descriptions.
- **Execution**: Scripts are executed directly by CLI or MCP.

## Planned MCP Interface (Primary)

- `wksm_pattern_list()` — List available patterns
- `wksm_pattern_run(name, args)` — Execute a pattern script
- `wksm_pattern_show(name)` — Show pattern documentation

## Planned CLI Interface (Secondary)

- `wksc pattern list` — List available patterns
- `wksc pattern run <name> [args...]` — Execute a pattern script
- `wksc pattern show <name>` — Show pattern documentation
