# Configuration Specification

## Purpose
Single JSON configuration consumed uniformly by CLI and MCP.

## Configuration File Structure
- Location: `{WKS_HOME}/config.json` (override with `export WKS_HOME=/custom/path`, default `~/.wks`)
- Composition: The file is the aggregation of the normative schemas of its constituent config blocks. It MUST include each required top-level block as defined in the top-level specification (`qa/specs/wks.md`); do not duplicate the list here.
- All sections and fields defined by those block schemas are required; missing anything fails validation.

## Normative Schema
- The authoritative definition is the composition of the constituent block schemas (see `qa/specs/wks.md` for the set of blocks). Implementations MUST validate against that composition; avoid hand-maintained duplicate definitions. Unknown fields MUST be rejected.

## CLI

- Entry: `wksc config`
- Output formats: `--display yaml` (default) or `--display json`

### list
- Command: `wksc config list`
- Behavior: Lists all configuration section names.
- Output schema (normative): `ConfigShowOutput` defined in the canonical output schema artifact `qa/specs/config_output.schema.json`. Implementations MUST consume/generate from that artifact; do not redefine fields in code.

### show
- Command: `wksc config show <section>`
- Behavior: Shows the configuration for the specified section.
- Output schema (normative): `ConfigShowOutput` defined in `qa/specs/config_output.schema.json`. Implementations MUST consume/generate from that artifact; the schema file is the single source of truth.

### version
- Command: `wksc config version`
- Behavior: Shows the current version string only.
- Output schema (normative): `ConfigVersionOutput` defined in `qa/specs/config_output.schema.json`. Implementations MUST consume/generate from that artifact; the schema file is the single source of truth.

### set
- Command: `wksc config set <key> <value> [--delete]`
- Behavior: Set, modify, or remove a configuration value by dot-path key (e.g., `monitor.max_documents`). Values are JSON-parsed (falling back to plain string). With `--delete`, removes the key instead.
- Validation: After modification, the full config is validated through Pydantic. Invalid changes are rejected before saving.
- Output schema (normative): `ConfigSetOutput` with fields: `errors`, `warnings`, `key`, `value`, `config_path`.

## MCP
- Commands mirror CLI:
  - `wksm_config_list` — lists all sections.
  - `wksm_config_show <section>` — shows the specified section (section argument is required).
  - `wksm_config_version` — shows the current version string.
  - `wksm_config_set <key> <value> [delete]` — set or remove a config value.
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Missing or unknown section/field MUST yield a validation error; no partial success is permitted.
- `show <section>` with an unknown section MUST return `ConfigShowOutput` populated with the error in `errors` and `success` must be false (implicit via schema + StageResult).
- All outputs MUST validate against their schemas before being returned to CLI or MCP.

## Formal Requirements
- CONFIG.1 — Complete config is mandatory: Loading fails if any required section or field is missing; nothing is implied or defaulted.
- CONFIG.2 — No defaults: Every value is provided explicitly; the system must not inject or assume defaults at runtime.
- CONFIG.3 — `wksc config list` lists all sections of the config.
- CONFIG.4 — `wksc config show <section>` requires a section argument and returns that section’s config; omission is invalid.
- CONFIG.5 — `wksc config version` shows the current version string.
- CONFIG.6 — `wksc config set` modifies config by dot-path key; validates through Pydantic before saving; rejects invalid changes.
- CONFIG.7 — Unknown or invalid section and any schema violation must return a schema-conformant error response (populate `errors`, no partial success).
