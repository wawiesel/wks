# MCP Async Tools Specification

**Note**: This specification needs to be updated to align with the principles established in the monitor and database specifications. It should follow the config-first approach (configuration discussed early, database schema discussed later), remove implementation details, and focus on WHAT (interface, behavior, requirements) rather than HOW (implementation details).


## Overview

For long-running operations (both CLI and MCP), WKS uses a unified 4-step pattern that provides immediate feedback, progress with time estimates, and final results. This improves UX by giving users immediate feedback and managing expectations for operations that may take significant time.

**Unified Pattern**: The same 4-step pattern works for both CLI and MCP, with different display mechanisms:

- **Step 1: Announce** (CLI: STDERR, MCP: immediate response with job_id)
- **Step 2: Progress** (CLI: progress bar on STDERR with time estimate, MCP: progress notifications with time estimate)
- **Step 3: Result** (CLI: STDERR, MCP: result notification messages)
- **Step 4: Output** (CLI: STDOUT, MCP: result notification data)

**Time Estimates**: Time estimates are provided when progress starts (Step 2), not in the initial announcement. This ensures estimates are based on actual work being performed, not just queued.

This unified approach means Typer functions can implement the 4-step pattern once, and it works for both CLI (via `CLIDisplay`) and MCP (via `MCPDisplay` + async notifications).

## Design

### Stage 1: Immediate Response - Maps to CLI "Announce"

When a tool is called, if it's a long-running operation, it can return immediately with:
- `success: true`
- `data.job_id: str` - Unique identifier for this operation
- `data.status: "queued" | "running"` - Current status
- `messages`: Info message explaining the operation is starting

**CLI equivalent**: `display.status("Syncing files...")` (Step 1: Announce)

**Note**: Time estimates are NOT provided in Stage 1. They are provided in Stage 2 when progress actually starts, ensuring estimates are based on actual work being performed.

### Stage 2: Progress Notifications - Maps to CLI "Progress"

During execution, the tool sends progress notifications with time estimates:
- Method: `notifications/progress` (JSON-RPC notification, no ID)
- Payload: `{ "job_id": "...", "progress": 0.0-1.0, "message": "...", "estimated_remaining_seconds": float, "timestamp": "..." }`

**CLI equivalent**: `with display.progress(total=N, description="Processing...", estimated_time=45.0):` (Step 2: Progress)

**Time Estimates**: Estimates are calculated when progress starts, based on:
- Total work items (e.g., number of files to process)
- Historical performance data (if available)
- Current system load

The first progress notification should include the initial time estimate. Subsequent notifications can update the estimate based on actual progress.

### Stage 3: Final Result - Maps to CLI "Result" + "Output"

When complete, the tool sends a final notification:
- Method: `notifications/tool_result` (JSON-RPC notification, no ID)
- Payload: `{ "job_id": "...", "result": MCPResult.to_dict(), "timestamp": "..." }`

The `result` contains:
- `messages`: Status/error messages (maps to CLI Step 3: Result)
- `data`: Actual result data (maps to CLI Step 4: Output)

**CLI equivalent**:
- `display.success("Done")` or `display.error("Failed")` (Step 3: Result)
- `display.json_output(data)` or `display.table(data)` (Step 4: Output)

## Implementation

### Server-Side

The MCP server tracks active jobs and executes them in background threads:

```python
class MCPServer:
    def __init__(self):
        self._active_jobs: dict[str, threading.Thread] = {}
        self._job_results: dict[str, MCPResult] = {}

    def _handle_call_tool(self, request_id: int, params: dict[str, Any]) -> None:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        # Check if tool supports async execution
        if self._is_long_running_tool(tool_name):
            # Stage 1: Immediate response with estimate
            job_id = str(uuid.uuid4())
            estimated_time = self._estimate_runtime(tool_name, arguments)

            result = MCPResult(
                success=True,
                data={
                    "job_id": job_id,
                    "status": "queued"
                }
            )
            result.add_info("Operation queued. Starting...")

            self._write_response(request_id, result.to_dict())

            # Stage 2 & 3: Execute in background, send notifications
            thread = threading.Thread(
                target=self._execute_tool_async,
                args=(job_id, tool_name, arguments),
                daemon=True
            )
            thread.start()
            self._active_jobs[job_id] = thread
        else:
            # Synchronous execution for fast tools
            result = self._execute_tool_sync(tool_name, arguments)
            self._write_response(request_id, result.to_dict())
```

### Tool Schema Extension

Tools that support async execution declare it in their schema:

```json
{
  "name": "wksm_monitor_sync",
  "description": "Sync files to monitor database",
  "async": true,
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Path to sync"},
      "recursive": {"type": "boolean", "description": "Recurse into subdirectories"}
    },
    "required": ["path"]
  }
}
```

The `async: true` field indicates this tool supports the 2-stage return pattern.

### Runtime Estimation

Runtime estimation can be:
- **Simple**: Fixed estimates per tool type (e.g., `monitor_sync`: 1 second per 100 files)
- **Advanced**: Historical data, complexity analysis, file count estimation

Initial implementation uses simple fixed estimates. Historical data can be added later.

## Unified Implementation Pattern

The same Typer function can implement the 4-step pattern for both CLI and MCP async tools. The function detects the context and adapts:

```python
@monitor_app.command(name="sync")
@inject_config
def sync(
    path: str = typer.Argument(..., help="Path to sync"),
    recursive: bool = typer.Option(False, "--recursive"),
    config: WKSConfig | None = None,
) -> dict[str, Any]:
    display = get_display("cli")
    is_cli = isinstance(display, CLIDisplay)

    if is_cli:
        # CLI: Follow 4-step pattern directly
        # Step 1: Announce
        display.status("Syncing files...")

        # Step 2: Progress
        file_count = _count_files(path, recursive)
        with display.progress(total=file_count, description="Processing files..."):
            result = _do_sync(path, recursive, display)

        # Step 3: Result
        if result["success"]:
            display.success(f"Synced {result['files_processed']} files")
        else:
            display.error(f"Sync failed: {result['error']}")

        # Step 4: Output
        display.json_output(result)

        return result
    else:
        # MCP Async: Return immediately, execute in background
        job_id = str(uuid.uuid4())

        # Stage 1: Immediate response (maps to Step 1: Announce)
        # MCP server will handle this and execute in background
        # The function returns early, background thread handles Steps 2-4
        # Time estimate will be provided in Step 2 when progress starts
        return {
            "job_id": job_id,
            "status": "queued"
        }
```

For MCP async tools, the MCP server:
1. Receives the immediate response with `job_id`
2. Executes the tool in a background thread
3. Sends progress notifications (Step 2 equivalent)
4. Sends final result notification (Steps 3+4 equivalent)

The background execution can use the same `_do_sync()` function, which internally uses `display.progress()` calls that get converted to MCP progress notifications.

## Protocol Flow

### Example: `wksm_monitor_sync`

1. **Client calls tool:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "wksm_monitor_sync",
    "arguments": {
      "path": "/path/to/dir",
      "recursive": true
    }
  }
}
```

2. **Server responds immediately:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "data": {
      "job_id": "abc-123-def-456",
      "status": "queued"
    },
    "messages": [
      {
        "type": "info",
        "text": "Operation queued. Starting..."
      }
    ]
  }
}
```

3. **Server sends progress notifications (during execution) with time estimates:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "job_id": "abc-123-def-456",
    "progress": 0.0,
    "message": "Processing 0 of 500 files...",
    "estimated_remaining_seconds": 45.0,
    "timestamp": "2025-12-04T12:00:00Z"
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "job_id": "abc-123-def-456",
    "progress": 0.3,
    "message": "Processing 150 of 500 files...",
    "estimated_remaining_seconds": 31.5,
    "timestamp": "2025-12-04T12:00:13Z"
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "job_id": "abc-123-def-456",
    "progress": 0.6,
    "message": "Processing 300 of 500 files...",
    "timestamp": "2025-12-04T12:00:20Z"
  }
}
```

4. **Server sends final result:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tool_result",
  "params": {
    "job_id": "abc-123-def-456",
    "result": {
      "success": true,
      "data": {
        "files_processed": 500,
        "files_skipped": 10,
        "files_updated": 490,
        "duration_seconds": 42.3
      },
      "messages": [
        {
          "type": "success",
          "text": "Sync completed successfully"
        }
      ]
    },
    "timestamp": "2025-12-04T12:00:42Z"
  }
}
```

## Client Requirements

Clients must:
1. Handle immediate responses with `job_id` (no time estimate in initial response)
2. Listen for `notifications/progress` messages and correlate by `job_id`
3. Extract `estimated_remaining_seconds` from progress notifications (provided when progress starts)
4. Listen for `notifications/tool_result` messages and correlate by `job_id`
5. Display progress updates to users (progress bars, status messages, time estimates)
6. Handle errors in final result notifications

## Error Handling

If an error occurs during async execution:
- The final `notifications/tool_result` will contain an error result:
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tool_result",
  "params": {
    "job_id": "abc-123-def-456",
    "result": {
      "success": false,
      "data": {},
      "messages": [
        {
          "type": "error",
          "text": "Failed to sync: Permission denied",
          "details": "Full error traceback..."
        }
      ]
    },
    "timestamp": "2025-12-04T12:00:42Z"
  }
}
```

## Tools That Support Async

Currently, the following tools support async execution:
- `wksm_monitor_sync` - Syncs files/directories to monitor database (can be long-running for large directories)

Future tools that may support async:
- `wksm_vault_index` - Indexes entire vault (long-running)
- `wksm_transform_batch` - Transforms multiple files (if added)

## Implementation Status

- [ ] Server-side job tracking (`_active_jobs`, `_job_results`)
- [ ] Background thread execution (`_execute_tool_async`)
- [ ] Notification sending (`_write_notification`, `_send_progress_notification`, `_send_result_notification`)
- [ ] Tool schema extension (`async: bool` field)
- [ ] Runtime estimation logic
- [ ] Unified 4-step pattern in Typer functions (works for both CLI and MCP async)
- [ ] `wksm_monitor_sync` async implementation
- [ ] Client support for progress/result notifications
