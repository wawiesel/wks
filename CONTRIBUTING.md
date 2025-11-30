# Contributing to WKS

## Development Setup

```bash
# Clone and setup
git clone <repo-url>
cd 2025-WKS

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e '.[all]'
```

## Project Structure

```
wks/
├── cli/              # Command-line interface
│   ├── commands/     # Individual command modules
│   └── main.py       # CLI entry point
├── monitor/          # Filesystem monitoring
│   ├── controller.py # Monitor business logic
│   └── config.py     # MonitorConfig dataclass
├── vault/            # Obsidian vault integration
│   ├── indexer.py    # Link scanner
│   └── controller.py # Vault operations
├── transform/        # Document transformation
├── diff/             # Diff engines
├── mcp_server.py     # Model Context Protocol server
└── daemon.py         # Background service

tests/
├── test_*.py         # Unit tests
└── smoke/            # Integration tests
    ├── test_cli_smoke.py
    └── test_mcp_smoke.py
```

## Testing Strategy

### Unit Tests

Run all unit tests:
```bash
pytest tests/ -k "not smoke" -v
```

Run specific test file:
```bash
pytest tests/test_vault_indexer.py -v
```

**Coverage**: Current 46.20% (target: 100%)
```bash
pytest tests/ -k "not smoke" --cov=wks --cov-report=html
open htmlcov/index.html
```

Or use the coverage runner:
```bash
./scripts/run_coverage.sh
```

### Smoke Tests

End-to-end integration tests:
```bash
pytest tests/smoke/ -v
```

**Test Organization**:
- `tests/test_*.py` - Unit tests with mocked dependencies
- `tests/smoke/` - Integration tests with real CLI/MCP execution
- All tests use fixtures for isolation (temp dirs, mocked config)

### Coverage Guidelines

**High-priority modules** (target >80%):
- `daemon.py` (currently 36%)
- `vault/controller.py` (currently 31%)
- `cli/commands/service.py` (currently 25%)

**Well-tested modules** (>80%):
- `config.py` (85%)
- `mcp_bridge.py` (85%)
- `monitor_rules.py` (89%)
- `service_controller.py` (83%)

See `docs/COVERAGE.md` for detailed coverage analysis.

## Code Quality

### Complexity Limits
- **CCN (Cyclomatic Complexity)**: ≤ 10 per function
- **File Size**: ≤ 900 lines
- **Function Length**: ≤ 100 lines

Check complexity:
```bash
lizard wks/ -l python -C 10
```

### Style Guidelines
- **Python**: 3.10+ with type hints
- **Formatting**: PEP 8 (4 spaces, snake_case)
- **Imports**: Absolute imports, grouped by stdlib/third-party/local
- **Dataclasses**: Prefer dataclasses over dicts for config/models

### Configuration Pattern

Use `WKSConfig` dataclass (not raw dicts):
```python
from wks.config import WKSConfig

# Load config
config = WKSConfig.load()

# Access typed fields
vault_path = config.vault.base_dir
mongo_uri = config.mongo.uri
```

## Architecture Patterns

### Layer Independence
Each layer is self-contained:
- **Monitor**: Tracks filesystem state only
- **Vault**: Manages links, no similarity
- **Transform**: Conversion only, no indexing
- No cross-layer dependencies

### Controller Pattern
Business logic in controllers, views call controllers:
```python
# CLI calls controller
from wks.monitor import MonitorController
status = MonitorController.get_status(config)
display.show_status(status)

# MCP calls same controller
def mcp_monitor_status(config):
    status = MonitorController.get_status(config)
    return status.to_dict()
```

### Zero Code Duplication
CLI and MCP use identical business logic. Only display differs.

## Commit Guidelines

- **Format**: Conventional Commits (`feat:`, `fix:`, `refactor:`)
- **Scope**: Keep commits focused and atomic
- **Testing**: All tests must pass before PR
- **Documentation**: Update SPEC.md for behavior changes

## MCP Server Development

Test MCP server manually:
```bash
# Start server
wks0 mcp run --direct

# In another terminal, send requests
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | wks0 mcp run --direct
```

Test via smoke tests:
```bash
pytest tests/smoke/test_mcp_smoke.py -v
```

## Security

- **Never commit**: Credentials, API keys, personal vault paths
- **Config location**: `~/.wks/config.json` (user-specific)
- **MongoDB**: Local-only by default (`mongodb://localhost:27017`)
- **Filesystem access**: Respects configured include/exclude paths

## Getting Help

- **Bugs**: Open GitHub issue
- **Questions**: Start GitHub discussion
- **Spec questions**: See [SPEC.md](SPEC.md)
- **Next priorities**: See [NEXT.md](NEXT.md)
