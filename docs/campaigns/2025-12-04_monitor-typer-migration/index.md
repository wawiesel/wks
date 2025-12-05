# Complete WKS Typer/Pydantic Refactor

**Campaign Date:** 2025-12-04
**Status:** IN PROGRESS
**Branch:** `2025-12-04_monitor-typer-migration`

---

## Overview

Complete refactor of all WKS tools to use Typer for CLI and Pydantic for validation, eliminating the three parallel layers (MCP schema, CLI argparse, business logic) in favor of a single Python function signature as the source of truth. The monitor phase adopts the simplified spec (filter / priority / sync) described in `docs/specifications/monitor.md`—no legacy list/managed split, float priorities, and MCP/CLI parity.

This is a multi-phase campaign executed sequentially by a single agent:
- **Phase 1: Monitor** - Foundation and monitor tools
- **Phase 2: Vault** - Vault tools
- **Phase 3: Transform & Diff** - Transform and diff tools
- **Phase 4: Service & Infrastructure** - Service, DB, and config tools

## Complete Scope

**Phase 1: Monitor Tools** (Single Agent - IN PROGRESS)
- All monitor MCP tools (simplified): `wksm_monitor_status`, `wksm_monitor_check`, `wksm_monitor_sync`, `wksm_monitor_filter_show/add/remove`, `wksm_monitor_priority_show/add/remove`
- All monitor CLI commands (simplified): `wksc monitor status`, `wksc monitor check`, `wksc monitor sync`, `wksc monitor filter show/add/remove`, `wksc monitor priority show/add/remove`

**Phase 2: Vault Tools** (Agent 2 - PLANNED)
- Vault MCP tools: `wksm_vault_status`, `wksm_vault_sync`, `wksm_vault_links`, `wksm_vault_validate`, `wksm_vault_fix_symlinks`
- Vault CLI commands: `wksc vault status`, `wksc vault sync`, `wksc vault links`, `wksc vault validate`, `wksc vault fix-symlinks`

**Phase 3: Transform & Diff Tools** (Agent 3 - PLANNED)
- Transform MCP tools: `wksm_transform`, `wksm_cat`, `wksm_diff`
- Transform CLI commands: `wksc transform`, `wksc cat`, `wksc diff`

**Phase 4: Service & Infrastructure** (Agent 4 - PLANNED)
- Service MCP tools: `wksm_service`
- Service CLI commands: `wksc service status`, `wksc service start`, `wksc service stop`
- Config MCP tool: `wksm_config`
- Config CLI command: `wksc config`
- DB MCP tools: `wksm_db_query`

**Out of Scope:**
- MCP server infrastructure (JSON-RPC handling, stdio transport) - remains as-is
