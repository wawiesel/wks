# Patterns Layer Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).

**Vision**: Simple script-based organizational patterns with MCP server for AI access. Scripts are the source of truth for both code and documentation.

**Architecture**:
- **Location**: `{WKS_HOME}/patterns/` (where `WKS_HOME` defaults to `~/.wks` if not set via environment variable)
- **Format**: Executable scripts (bash, python, etc.)
- **Documentation**: Extracted from script header comments

**How It Works**:
- **Discovery**: WKS scans the patterns directory for executable scripts.
- **Documentation**: Header comments are parsed to provide tool descriptions.
- **Execution**: Scripts are executed directly by CLI or MCP.

## MCP Interface (Primary)

- `wksm_pattern_list()` — List available patterns
- `wksm_pattern_run(name, args)` — Execute a pattern script
- `wksm_pattern_show(name)` — Show pattern documentation

## CLI Interface (Secondary)

- `wksc pattern list` — List available patterns
- `wksc pattern run <name> [args...]` — Execute a pattern script
- `wksc pattern show <name>` — Show pattern documentation
