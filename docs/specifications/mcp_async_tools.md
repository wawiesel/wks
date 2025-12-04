# MCP Async Tools Specification

## Overview

For long-running MCP tool operations, WKS supports a 2-stage return pattern that provides immediate feedback with a runtime estimate, followed by progress notifications and a final result. This improves UX by giving users immediate feedback and managing expectations for operations that may take significant time.

## Design

### Stage 1: Immediate Response (Estimate)

When a tool is called, if it's a long-running operation, it can return immediately with:
- `success: true`
- `data.estimated_runtime_seconds: float` - Estimated time to complete
- `data.job_id: str` - Unique identifier for this operation
- `data.status: "queued" | "running"` - Current status
- `messages`: Info message explaining the operation is in progress

### Stage 2: Progress Notifications (Optional)

During execution, the tool can send progress notifications:
- Method: `notifications/progress` (JSON-RPC notification, no ID)
- Payload: `{ "job_id": "...", "progress": 0.0-1.0, "message": "...", "timestamp": "..." }`

### Stage 3: Final Result

When complete, the tool sends a final notification:
- Method: `notifications/tool_result` (JSON-RPC notification, no ID)
- Payload: `{ "job_id": "...", "result": MCPResult.to_dict(), "timestamp": "..." }`

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
                    "estimated_runtime_seconds": estimated_time,
                    "status": "queued"
                }
            )
            result.add_info(f"Operation queued. Estimated runtime: {estimated_time}s")

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
      "estimated_runtime_seconds": 45.0,
      "status": "queued"
    },
    "messages": [
      {
        "type": "info",
        "text": "Operation queued. Estimated runtime: 45s"
      }
    ]
  }
}
```

3. **Server sends progress notifications (during execution):**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "job_id": "abc-123-def-456",
    "progress": 0.3,
    "message": "Processing 150 of 500 files...",
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
1. Handle immediate responses with `job_id` and `estimated_runtime_seconds`
2. Listen for `notifications/progress` messages and correlate by `job_id`
3. Listen for `notifications/tool_result` messages and correlate by `job_id`
4. Display progress updates to users (progress bars, status messages)
5. Handle errors in final result notifications

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
- [ ] `wksm_monitor_sync` async implementation
- [ ] Client support for progress/result notifications
