# WKS

<!-- BEGIN BADGES -->
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)
<!-- END BADGES -->

## Status

- WKS is alpha software.
- The shared execution model is `services/core -> cmd_* -> CLI/MCP/REST`.
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
venv/bin/wksr --host 127.0.0.1 --port 8765
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

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks, test expectations, and architecture rules.
