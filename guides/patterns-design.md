# Pattern System Design

**Status:** Design phase (Phase 4)
**Prerequisites:** Phase 3 (Robustness) completion

## Overview

Simple script-based organizational patterns with MCP server for AI access.
Zero duplication: scripts are the source of truth for both code and documentation.

## Architecture

### Pattern Structure
```
~/.wks/patterns/
  picofday              # Executable script
  projfile
  deadfile
```

### Documentation Extraction

Scripts document themselves via header comments:
```bash
#!/usr/bin/env bash
# Short description (becomes pattern.description)
#
# Longer documentation (becomes pattern.documentation)
# Usage: command <args>
```

### Configuration

Add to `~/.wks/config.json`:
```json
{
  "patterns": {
    "scripts_dir": "~/.wks/patterns"
  }
}
```

## Implementation Files

### 1. Core Module: `wks/patterns.py`

Pattern discovery and execution logic.

```python
"""Pattern system: discover and execute organizational scripts."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Pattern:
    """A discovered pattern script."""
    name: str
    path: Path
    description: str
    documentation: str
    executable: bool

    @classmethod
    def from_path(cls, path: Path) -> Optional[Pattern]:
        """Create Pattern from script path."""
        if not path.is_file():
            return None

        name = path.name
        executable = os.access(path, os.X_OK)

        # Extract documentation from script comments
        description = ""
        doc_lines = []

        try:
            with open(path, 'r', encoding='utf-8') as f:
                in_header = False
                for line in f:
                    stripped = line.strip()

                    # Look for comment lines after shebang
                    if stripped.startswith('#!'):
                        in_header = True
                        continue

                    if in_header and stripped.startswith('#'):
                        # Remove leading '# '
                        content = stripped[1:].strip()
                        doc_lines.append(content)

                        # First non-empty line is the description
                        if not description and content:
                            description = content
                    elif in_header and not stripped:
                        # Empty line continues doc block
                        doc_lines.append("")
                    elif in_header:
                        # Non-comment line ends header
                        break
        except Exception:
            pass

        if not description:
            description = f"Pattern: {name}"

        documentation = '\n'.join(doc_lines)

        return cls(
            name=name,
            path=path,
            description=description,
            documentation=documentation,
            executable=executable
        )


def discover_patterns(patterns_dir: Optional[Path] = None) -> List[Pattern]:
    """Find all pattern scripts in the patterns directory."""
    if patterns_dir is None:
        from .constants import WKS_HOME_EXT
        patterns_dir = Path.home() / WKS_HOME_EXT / "patterns"

    patterns_dir = patterns_dir.expanduser()
    if not patterns_dir.exists():
        return []

    patterns = []
    for item in patterns_dir.iterdir():
        # Skip markdown docs, hidden files
        if item.name.startswith('.') or item.name.endswith('.md'):
            continue

        pattern = Pattern.from_path(item)
        if pattern:
            patterns.append(pattern)

    return sorted(patterns, key=lambda p: p.name)


def run_pattern(pattern: Pattern, args: List[str], interactive: bool = True) -> int:
    """Execute a pattern script with given arguments."""
    if not pattern.executable:
        print(f"Error: {pattern.path} is not executable")
        print(f"Run: chmod +x {pattern.path}")
        return 1

    cmd = [str(pattern.path)] + args

    try:
        if interactive:
            # Run with inherited stdin/stdout/stderr for interactive prompts
            result = subprocess.run(cmd, check=False)
            return result.returncode
        else:
            # Capture output for programmatic use
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='')
            return result.returncode
    except Exception as e:
        print(f"Error executing pattern: {e}")
        return 1


def get_patterns_dir(config: dict) -> Path:
    """Get patterns directory from config with fallback."""
    from .constants import WKS_HOME_EXT

    patterns_cfg = config.get("patterns", {})
    scripts_dir = patterns_cfg.get("scripts_dir", f"~/{WKS_HOME_EXT}/patterns")
    return Path(scripts_dir).expanduser()
```

### 2. CLI Commands: `wks/cli_pattern.py`

```python
"""CLI commands for pattern management."""

from pathlib import Path

from .config import load_user_config
from .patterns import discover_patterns, get_patterns_dir, run_pattern


def cmd_pattern_list(args) -> int:
    """List all available patterns."""
    cfg = load_user_config()
    patterns_dir = get_patterns_dir(cfg)

    patterns = discover_patterns(patterns_dir)

    if not patterns:
        print(f"No patterns found in {patterns_dir}")
        print(f"\nCreate executable scripts in this directory to define patterns.")
        return 0

    print(f"Patterns directory: {patterns_dir}\n")

    if args.format == 'json':
        import json
        output = [
            {
                "name": p.name,
                "path": str(p.path),
                "description": p.description,
                "executable": p.executable
            }
            for p in patterns
        ]
        print(json.dumps(output, indent=2))
    else:
        print(f"{'Name':<20} {'Description':<50} {'Path'}")
        print("-" * 100)
        for p in patterns:
            status = "✓" if p.executable else "✗"
            print(f"{status} {p.name:<18} {p.description:<50} {p.path}")

    return 0


def cmd_pattern_show(args) -> int:
    """Show documentation for a pattern."""
    cfg = load_user_config()
    patterns_dir = get_patterns_dir(cfg)

    patterns = discover_patterns(patterns_dir)
    pattern = next((p for p in patterns if p.name == args.name), None)

    if not pattern:
        print(f"Pattern not found: {args.name}")
        return 1

    print(f"Pattern: {pattern.name}")
    print(f"Path: {pattern.path}")
    print(f"Executable: {'Yes' if pattern.executable else 'No'}")
    print()

    # Show extracted documentation
    if pattern.documentation:
        print(pattern.documentation)
    else:
        print("No documentation available.")
        print("\nAdd comments after the shebang line to document this pattern:")
        print("  #!/usr/bin/env bash")
        print("  # Short description")
        print("  # ")
        print("  # Longer documentation...")

    return 0


def cmd_pattern_run(args) -> int:
    """Run a pattern with arguments."""
    cfg = load_user_config()
    patterns_dir = get_patterns_dir(cfg)

    patterns = discover_patterns(patterns_dir)
    pattern = next((p for p in patterns if p.name == args.name), None)

    if not pattern:
        print(f"Pattern not found: {args.name}")
        return 1

    return run_pattern(pattern, args.args, interactive=not args.non_interactive)


def setup_pattern_parser(subparsers):
    """Add pattern subcommands to the CLI parser."""
    pattern_parser = subparsers.add_parser('pattern', help='Pattern script management')
    pattern_sub = pattern_parser.add_subparsers(dest='pattern_command')

    # wks0 pattern list
    list_parser = pattern_sub.add_parser('list', help='List available patterns')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table')

    # wks0 pattern show <name>
    show_parser = pattern_sub.add_parser('show', help='Show pattern documentation')
    show_parser.add_argument('name', help='Pattern name')

    # wks0 pattern run <name> [args...]
    run_parser = pattern_sub.add_parser('run', help='Execute a pattern')
    run_parser.add_argument('name', help='Pattern name')
    run_parser.add_argument('args', nargs='*', help='Arguments to pass to pattern')
    run_parser.add_argument('--non-interactive', action='store_true',
                           help='Run without interactive prompts')
```

### 3. MCP Server: `wks/mcp/pattern_server.py`

```python
"""MCP server that exposes pattern scripts as tools."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..config import load_user_config
from ..patterns import discover_patterns, get_patterns_dir, Pattern


class PatternMCPServer:
    """MCP server for WKS patterns."""

    def __init__(self):
        self.server = Server("wks-patterns")
        self.patterns: List[Pattern] = []
        self._setup_handlers()

    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """Dynamically discover and expose patterns as tools."""
            cfg = load_user_config()
            patterns_dir = get_patterns_dir(cfg)
            self.patterns = discover_patterns(patterns_dir)

            tools = []
            for pattern in self.patterns:
                if not pattern.executable:
                    continue

                tools.append(Tool(
                    name=f"pattern_{pattern.name}",
                    description=pattern.description,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to file to process"
                            },
                            "additional_args": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Additional arguments for the pattern",
                                "default": []
                            }
                        },
                        "required": ["file_path"]
                    }
                ))

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a pattern script."""
            if not name.startswith("pattern_"):
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            pattern_name = name[8:]  # Remove "pattern_" prefix
            pattern = next((p for p in self.patterns if p.name == pattern_name), None)

            if not pattern:
                return [TextContent(
                    type="text",
                    text=f"Pattern not found: {pattern_name}"
                )]

            file_path = arguments.get("file_path", "")
            additional_args = arguments.get("additional_args", [])

            if not file_path:
                return [TextContent(
                    type="text",
                    text="Error: file_path is required"
                )]

            # Build command
            cmd_args = [file_path] + additional_args

            # Execute pattern
            import subprocess
            try:
                result = subprocess.run(
                    [str(pattern.path)] + cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False
                )

                output = []
                if result.stdout:
                    output.append(f"Output:\n{result.stdout}")
                if result.stderr:
                    output.append(f"Errors:\n{result.stderr}")

                if result.returncode == 0:
                    output.insert(0, f"✓ Pattern '{pattern_name}' completed successfully\n")
                else:
                    output.insert(0, f"✗ Pattern '{pattern_name}' failed (exit code {result.returncode})\n")

                return [TextContent(type="text", text="\n".join(output))]

            except subprocess.TimeoutExpired:
                return [TextContent(
                    type="text",
                    text=f"Pattern '{pattern_name}' timed out after 60 seconds"
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"Error executing pattern: {e}"
                )]

    async def run(self):
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Entry point for pattern MCP server."""
    server = PatternMCPServer()
    asyncio.run(server.run())
```

### 4. CLI Integration

Add to `wks/cli.py`:

```python
from .cli_pattern import setup_pattern_parser

# In main():
def main():
    parser = argparse.ArgumentParser(...)
    subparsers = parser.add_subparsers(dest='command')

    # ... existing commands ...

    # Pattern commands
    setup_pattern_parser(subparsers)

    # ... rest of argument parsing ...

    # Pattern command dispatch
    if args.command == 'pattern':
        from .cli_pattern import cmd_pattern_list, cmd_pattern_show, cmd_pattern_run

        if args.pattern_command == 'list':
            return cmd_pattern_list(args)
        elif args.pattern_command == 'show':
            return cmd_pattern_show(args)
        elif args.pattern_command == 'run':
            return cmd_pattern_run(args)
        else:
            print("Usage: wks0 pattern {list|show|run}")
            return 1

    # MCP serve dispatch
    if args.command == 'mcp':
        if args.mcp_command == 'serve':
            if args.server == 'patterns':
                from .mcp.pattern_server import main as pattern_server_main
                return pattern_server_main()
```

### 5. Dependencies

Add to `setup.py`:
```python
install_requires=[
    # ... existing ...
    "mcp>=0.9.0",  # MCP SDK for AI integration
],
```

## Example Pattern Script

`~/.wks/patterns/picofday`:
```bash
#!/usr/bin/env bash
# Picture of the Day organizer
#
# Organizes a single significant scientific/technical image per day.
#
# Usage: picofday <image-file>
#
# What it does:
#   1. Calculates day of year (1-366)
#   2. Creates ~/Pictures/YYYY-Daily_Image/DDD/ directory
#   3. Moves image to DDD-OriginalName.ext
#   4. Creates hard link in Obsidian at Pictures/OfTheDay/_links/YYYY/DDD.ext
#   5. Prompts for caption creation

set -e

if [ $# -lt 1 ]; then
    echo "Usage: picofday <image-file>"
    exit 1
fi

IMAGE_PATH="$1"

if [ ! -f "$IMAGE_PATH" ]; then
    echo "Error: File not found: $IMAGE_PATH"
    exit 1
fi

# Get day of year
DAY_NUM=$(date +%j)
YEAR=$(date +%Y)

# Create directory
DEST_DIR="$HOME/Pictures/${YEAR}-Daily_Image/${DAY_NUM}"
mkdir -p "$DEST_DIR"

# Get basename without extension
BASENAME=$(basename "$IMAGE_PATH")
EXT="${BASENAME##*.}"
NAME="${BASENAME%.*}"

# Move file
DEST_FILE="${DEST_DIR}/${DAY_NUM}-${NAME}.${EXT}"
mv "$IMAGE_PATH" "$DEST_FILE"

echo "✓ Moved to: $DEST_FILE"

# Create hard link for Obsidian
OBSIDIAN_LINK_DIR="$HOME/obsidian/Pictures/OfTheDay/_links/${YEAR}"
mkdir -p "$OBSIDIAN_LINK_DIR"

ln "$DEST_FILE" "${OBSIDIAN_LINK_DIR}/${DAY_NUM}.${EXT}"

echo "✓ Linked in Obsidian: Pictures/OfTheDay/_links/${YEAR}/${DAY_NUM}.${EXT}"

# Prompt for caption
echo ""
echo "Create caption? [Y/n]"
read -r response
if [[ "$response" =~ ^[Yy]$ ]] || [ -z "$response" ]; then
    CAPTION_FILE="${DEST_DIR}/${DAY_NUM}-${NAME}.md"

    # Open editor
    ${EDITOR:-nano} "$CAPTION_FILE"

    # Link caption too
    if [ -f "$CAPTION_FILE" ]; then
        ln "$CAPTION_FILE" "${OBSIDIAN_LINK_DIR}/${DAY_NUM}.md"
        echo "✓ Caption linked"
    fi
fi

echo "✓ Complete"
```

## Usage Examples

### Human CLI
```bash
# List patterns
wks0 pattern list
# Output:
# Patterns directory: ~/.wks/patterns
#
# Name                 Description                         Path
# ✓ picofday           Picture of the Day organizer       ~/.wks/patterns/picofday

# Show documentation
wks0 pattern show picofday

# Run pattern
wks0 pattern run picofday ~/Downloads/nuclear_data_plot.png

# JSON output
wks0 pattern list --format json
```

### AI MCP
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "wks-patterns": {
      "command": "wks0",
      "args": ["mcp", "serve", "patterns"]
    }
  }
}
```

AI can then use:
```
Tool: pattern_picofday
Arguments: {"file_path": "/Users/ww5/Downloads/figure.png"}
```

## Testing Strategy

### Unit Tests
- Pattern discovery from directory
- Documentation extraction from scripts
- Script execution (mocked)

### Integration Tests
- End-to-end CLI commands
- MCP server tool listing
- MCP server tool execution

### Manual Smoke Tests
1. Create test pattern script
2. `wks0 pattern list` shows it
3. `wks0 pattern show <name>` extracts docs
4. `wks0 pattern run <name>` executes
5. MCP server exposes as tool

## Design Principles

1. **Scripts are truth** - No separate documentation files
2. **Zero duplication** - Single execution path for CLI and MCP
3. **Minimal magic** - Simple discovery, simple execution
4. **User extensible** - Drop script in directory, it works
5. **Convention over config** - Comment format is the API
