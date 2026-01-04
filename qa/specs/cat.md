# Cat Specification

`wksc cat` transforms a file and outputs text to stdout.

## CLI

```
wksc cat [--engine <engine>] <file>
```

| Argument | Required | Description |
|----------|----------|-------------|
| `file` | Yes | File to transform |
| `--engine` | No | Override default engine |

## Config

```json
{
  "cat": {
    "default_engine": "dx"
  }
}
```

## Behavior

1. Resolve engine: `--engine` flag > `cat.default_engine` config
2. Transform file (uses cache if available)
3. Output content to stdout

## Errors

- Missing engine: fail if no `--engine` and no `cat.default_engine`
- Transform failure: print error to stderr, exit 1

## Examples

```bash
# Use default engine from config
wksc cat report.pdf

# Override engine
wksc cat --engine dx report.pdf
```
