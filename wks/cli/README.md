# CLI Layer

Thin argparse wrappers that only call MCP tools (see `wks/cli/__init__.py`). Do not add business logic; format output via the display helpers and keep STDOUT/STDERR separation per CONTRIBUTING. Add new commands by wiring arguments to `call_tool("wksm_*")`.
