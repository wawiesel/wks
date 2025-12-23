# CLI Layer

The CLI layer uses **factory functions** to create Typer apps for each domain.

## Factory Pattern

Each CLI domain module exports a single factory function matching its filename:

| File | Factory | Description |
|------|---------|-------------|
| `config.py` | `config()` | Configuration operations |
| `daemon.py` | `daemon()` | Daemon runtime management |
| `database.py` | `database()` | Database operations |
| `link.py` | `link()` | Link/edge management |
| `log.py` | `log()` | Log management |
| `mcp.py` | `mcp()` | MCP installation |
| `monitor.py` | `monitor()` | File monitoring |
| `service.py` | `service()` | System service |
| `vault.py` | `vault()` | Vault operations |

## Uniformity Rules

All CLI files follow these patterns:

### Imports
- All imports at module level (no inline imports inside functions)
- Import order: stdlib → typer → API cmd_* functions → handle_stage_result

### App Creation
```python
app = typer.Typer(
    name="{domain}",
    help="{Description}",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
```

### Callback
```python
@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help(), err=True)
        raise typer.Exit()
```

### Commands
- Use `typer.Argument(...)` (required) to avoid manual None checks
- Use `typer.Argument(None)` only when the argument is truly optional
- Simple commands: just call `handle_stage_result(cmd_*)()`

## Why This Pattern?

1. **UNO Compliance** - One file, one public function
2. **Thin Router** - No business logic, just wiring to API
3. **Testability** - Fresh app instances per test
4. **Encapsulation** - Callbacks are function-scoped

## Adding Commands

1. Create `wks/api/{domain}/cmd_{name}.py` returning `StageResult`
2. Import at top of `wks/cli/{domain}.py`
3. Add command using `handle_stage_result(cmd_*)()`

No business logic in CLI - it's purely a router.
