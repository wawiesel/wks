# Link API

This directory implements the Link API, serving as the centralized Edge Provider for WKS.

## Core Principles

**One file = one thing**: Every exported function lives in its own file.

**Pure API layer**: No CLI/MCP specific code. Functions return `StageResult` or structured data.

**Parsers**: Link extraction logic is pluggable and located in `_parsers/`.

## Files
- `cmd_check.py` — Check links in a file (read-only)
- `cmd_sync.py` — Sync links to the database (write)
- `cmd_status.py` — Report link statistics
- `cmd_show.py` — Show edges for a URI
- `_sync_single_file.py` — Helper logic for syncing a single file
- `_identity.py` — Identity calculation for edges
- `_parsers/` — Link extractor implementations

## Usage
Commands are exposed via CLI (`wksc link`) and MCP (`wksm_link_*`).
