# MCP 2-Stage Return Pattern

## Overview

For long-running MCP tool operations, we want to provide immediate feedback with a runtime estimate, then send the final result when complete. This improves UX by giving users immediate feedback and managing expectations.

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

## Implementation Options

### Option 1: Async with Background Threads

```python
import threading
import uuid
from typing import Any

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

    def _execute_tool_async(self, job_id: str, tool_name: str, arguments: dict[str, Any]) -> None:
        """Execute tool in background, sending progress notifications."""
        try:
            # Send progress updates
            self._send_progress_notification(job_id, 0.0, "Starting operation...")

            # Execute tool (this would call the actual tool function)
            result = self._execute_tool_sync(tool_name, arguments)

            # Send progress updates during execution
            self._send_progress_notification(job_id, 0.5, "Processing...")

            # Store result
            self._job_results[job_id] = result

            # Stage 3: Send final result notification
            self._send_result_notification(job_id, result)

        except Exception as e:
            error_result = MCPResult.error_result(str(e))
            self._job_results[job_id] = error_result
            self._send_result_notification(job_id, error_result)
        finally:
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]

    def _send_progress_notification(self, job_id: str, progress: float, message: str) -> None:
        """Send progress notification (JSON-RPC notification, no ID)."""
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/progress",
            "params": {
                "job_id": job_id,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        self._write_notification(notification)

    def _send_result_notification(self, job_id: str, result: MCPResult) -> None:
        """Send final result notification."""
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/tool_result",
            "params": {
                "job_id": job_id,
                "result": result.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        self._write_notification(notification)

    def _write_notification(self, notification: dict[str, Any]) -> None:
        """Write JSON-RPC notification (no ID, no response expected)."""
        message = json.dumps(notification)
        if self._lsp_mode:
            self._output.write(f"Content-Length: {len(message)}\r\n\r\n{message}")
        else:
            self._output.write(f"{message}\n")
        self._output.flush()
```

### Option 2: Polling-Based (Simpler)

Instead of notifications, client polls for results:

```python
def _handle_call_tool(self, request_id: int, params: dict[str, Any]) -> None:
    tool_name = params.get("name")

    if self._is_long_running_tool(tool_name):
        job_id = str(uuid.uuid4())
        estimated_time = self._estimate_runtime(tool_name, arguments)

        # Queue job
        self._queue_job(job_id, tool_name, arguments)

        # Return immediately with job_id
        result = MCPResult(
            success=True,
            data={
                "job_id": job_id,
                "estimated_runtime_seconds": estimated_time,
                "status": "queued",
                "poll_endpoint": "tools/poll_result"  # Client polls this
            }
        )
        self._write_response(request_id, result.to_dict())
    else:
        # Synchronous
        result = self._execute_tool_sync(tool_name, arguments)
        self._write_response(request_id, result.to_dict())

def _handle_poll_result(self, request_id: int, params: dict[str, Any]) -> None:
    """Handle polling for job result."""
    job_id = params.get("job_id")

    if job_id in self._job_results:
        # Job complete
        result = MCPResult(
            success=True,
            data={
                "job_id": job_id,
                "status": "complete",
                "result": self._job_results[job_id].to_dict()
            }
        )
        del self._job_results[job_id]
    elif job_id in self._active_jobs:
        # Job still running
        result = MCPResult(
            success=True,
            data={
                "job_id": job_id,
                "status": "running",
                "progress": self._get_job_progress(job_id)  # 0.0-1.0
            }
        )
    else:
        # Job not found
        result = MCPResult.error_result(f"Job not found: {job_id}")

    self._write_response(request_id, result.to_dict())
```

## Recommendation

**Use Option 1 (Notifications)** for better UX:
- Client gets immediate feedback
- No polling overhead
- Real-time progress updates
- Follows JSON-RPC notification pattern

**Requirements:**
1. MCP server must support sending notifications during tool execution
2. Client must handle `notifications/progress` and `notifications/tool_result`
3. Tools must declare if they support async execution (via tool schema)
4. Runtime estimation logic (can be simple initially, improve over time)

## Tool Schema Extension

Add to tool schema to indicate async support:

```json
{
  "name": "wksm_monitor_sync",
  "description": "Sync files to monitor database",
  "async": true,  // Indicates this tool supports 2-stage return
  "inputSchema": { ... }
}
```

## Example Usage Flow

1. **Client calls tool:**
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "tools/call",
     "params": {
       "name": "wksm_monitor_sync",
       "arguments": { "path": "/path/to/dir", "recursive": true }
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
         "job_id": "abc-123",
         "estimated_runtime_seconds": 45.0,
         "status": "queued"
       },
       "messages": [
         {"type": "info", "text": "Operation queued. Estimated runtime: 45s"}
       ]
     }
   }
   ```

3. **Server sends progress notifications:**
   ```json
   {
     "jsonrpc": "2.0",
     "method": "notifications/progress",
     "params": {
       "job_id": "abc-123",
       "progress": 0.3,
       "message": "Processing 150 of 500 files...",
       "timestamp": "2025-12-04T12:00:00Z"
     }
   }
   ```

4. **Server sends final result:**
   ```json
   {
     "jsonrpc": "2.0",
     "method": "notifications/tool_result",
     "params": {
       "job_id": "abc-123",
       "result": {
         "success": true,
         "data": {
           "files_processed": 500,
           "files_skipped": 10,
           "duration_seconds": 42.3
         },
         "messages": [...]
       },
       "timestamp": "2025-12-04T12:00:42Z"
     }
   }
   ```

## Implementation Plan

1. **Add async support to `MCPServer`**
   - Job tracking (`_active_jobs`, `_job_results`)
   - Notification sending (`_write_notification`)
   - Background thread execution

2. **Extend tool schema**
   - Add `async: bool` field to tool definitions
   - Tools can declare if they support 2-stage return

3. **Add runtime estimation**
   - Simple: Fixed estimates per tool type
   - Advanced: Historical data, complexity analysis

4. **Update `MCPResult`**
   - Add `job_id` field for async operations
   - Add `estimated_runtime_seconds` field

5. **Client support**
   - Handle progress notifications
   - Handle result notifications
   - Correlate notifications with original request
