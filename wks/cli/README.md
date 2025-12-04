# CLI Layer

The CLI layer (`wks/cli/__init__.py`) is a thin router that delegates all commands to domain-specific Typer apps in `wks/api/{domain}/app.py`.

## Architecture

All commands are handled by domain-specific Typer apps:
- `wks/api/monitor/app.py` - Monitor commands
- `wks/api/vault/app.py` - Vault commands
- `wks/api/transform/app.py` - Transform commands
- `wks/api/diff/app.py` - Diff commands
- `wks/api/service/app.py` - Service commands
- `wks/api/config/app.py` - Config commands
- `wks/api/db/app.py` - Database commands

Each domain app implements the unified 4-stage pattern for both CLI and MCP:
1. Functions return `StageResult` with 4-stage data (announce, progress, result, output)
2. Wrapper handles 4-stage pattern for CLI display
3. MCP server extracts data from `StageResult` for protocol responses

## Structure

The main CLI file (`wks/cli/__init__.py`) contains:
- **Domain app registration**: All domain Typer apps are registered as subcommands
- **Infrastructure commands**: MCP server operations (`wksc mcp`)
- **Flag handlers**: Version and display flag handling
- **Main entry point**: Routes to appropriate domain apps

## Adding New Commands

To add a new command:
1. Create the API function in `wks/api/{domain}/{command}.py` that returns `StageResult`
2. Register it in `wks/api/{domain}/app.py` using the `_handle_stage_result` wrapper
3. The CLI automatically picks it up through the domain app registration

No business logic should be added to the CLI layer - it's purely a router.
