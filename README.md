# WKS

<!-- BEGIN BADGES -->
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)
<!-- END BADGES -->

## Status

- WKS is alpha software.
- The shared execution model is `services/core -> cmd_* -> CLI/MCP` plus a read-only REST layer over the same services.
- REST support is mandatory.

## Overview

WKS monitors configured paths, transforms files into cached text, tracks vault links, builds searchable indexes, and exposes the same behavior through:

- CLI: `wksc`
- MCP: `wksm`
- REST: `wksr`
- Python: `wks.services.WKSService`

## Install

```bash
python3 -m venv venv
venv/bin/pip install -e .
```

## Quick Start

```bash
venv/bin/wksc status
venv/bin/wksc search "reactor"
venv/bin/wksc cat /path/to/file.pdf
venv/bin/wksr
```

```python
from wks.services import WKSService

service = WKSService.from_config()
result = service.search(query="reactor", k=5)
```

## Architecture

- `wks/services/`: typed shared business logic
- `wks/api/`: one command wrapper per command contract
- `wks/cli/`: Typer transport over command wrappers
- `wks/mcp/`: MCP transport over command wrappers
- `wks/rest/`: read-only FastAPI transport over shared services

Rules that stay fixed:

- shared behavior belongs in services or command wrappers, not transports
- command-level traceability remains 1:1 with `cmd_*` files
- CLI, MCP, and REST stay thin
- configuration loads once, validates early, and fails hard on bad input

## Command Surface

Primary command groups:

- `status`
- `monitor`
- `vault`
- `link`
- `transform`
- `index`
- `search`
- `mv`
- `daemon`
- `service`
- `config`
- `database`
- `mcp`

## Code Quality Metrics

<!-- BEGIN GENERATED METRICS -->
Run `venv/bin/python scripts/generate_all_stats.py` or `venv/bin/python scripts/update_readme_stats.py`
to populate the latest local metrics.
<!-- END GENERATED METRICS -->

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks, tests, and architecture rules.
