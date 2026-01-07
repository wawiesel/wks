# Diff Layer Specification

**Purpose**: To provide a robust, pluggable mechanism for calculating and presenting differences between various forms of content, adhering strictly to WKS-DIFF requirements and NoHedging principles.

**Referenced Requirements**:
This specification fulfills the requirements outlined in `qa/reqs/diff/WKS-DIFF-00x.yml` (specifically WKS-DIFF-001 through WKS-DIFF-005).

## 1. Configuration (Config-First Approach)

The diff layer configuration SHALL be explicit and strongly-typed. All configurable options for diff engines and behaviors SHALL be defined in a dedicated configuration schema using immutable dataclasses. Defaults are discouraged; explicit values or clear error handling for missing configuration are mandated by NoHedging (WKS-DIFF-003).

The default values shown in the example dataclasses below (e.g., `timeout_seconds=60`, `context_lines=3`, `ignore_comments=True`) are illustrative of system-level defaults. In adherence to the NoHedging rule, these defaults SHALL be defined and managed at a single, authoritative boundary within the codebase (e.g., a dedicated configuration loading module or factory function), and will not be re-implemented or scattered throughout core business logic.

### Location
- Location: `{WKS_HOME}/config.json`
- Block: `diff`

### Engine Types vs. Named Engines
WKS defines **Diff Engine Types** (the underlying implementation, e.g., `bsdiff4`, `myers`, `ast`).
Users define **Named Diff Engines** in `config.json`.
- Multiple named diff engines can use the same type (e.g., `fast-text-diff`, `strict-text-diff`).
- The CLI refers to the **Named Diff Engine** (the key in the `engines` dict).

### Example `config.json` Structure
```json
"diff": {
    "cache": {
        "base_dir": "~/.wks/diff_cache",
        "max_size_bytes": 1073741824
    },
    "engines": {
       "myers-default": {
         "type": "myers",
         "data": {
           "context_lines": 3,
           "ignore_whitespace": false
         }
       },
       "myers-ignore-ws": {
         "type": "myers",
         "data": {
           "context_lines": 3,
           "ignore_whitespace": true
         }
       },
       "ast-python": {
         "type": "ast",
         "data": {
           "language": "python",
           "ignore_comments": true
         }
       },
       "bsdiff4-default": {
         "type": "bsdiff4",
         "data": {}
       }
    }
}
```

### Example Configuration Schema (Dataclass style)

```python
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any

# These dataclasses define the structure of options within the 'data' block
@dataclass(frozen=True)
class BinaryDiffOptions:
    # No specific options for bsdiff4 currently

@dataclass(frozen=True)
class TextDiffOptions:
    context_lines: int = 3
    ignore_whitespace: bool = False

@dataclass(frozen=True)
class CodeDiffOptions:
    language: str  # e.g., 'python', 'java' - Required, no default
    ignore_comments: bool = True

# This dataclass represents a single named diff engine's configuration as loaded from config.json
@dataclass(frozen=True)
class NamedDiffEngineConfig:
    type: Literal["bsdiff4", "myers", "ast"]
    data: Dict[str, Any] = field(default_factory=dict) # Raw options, validated against engine-specific dataclass

# This would be the overall Diff configuration block in WKSConfig
@dataclass(frozen=True)
class DiffConfigBlock:
    engines: Dict[str, NamedDiffEngineConfig] = field(default_factory=dict)
    # Global diff settings
    timeout_seconds: int = 60
    max_size_mb: int = 100
```



## 2. Diff Engines (WKS-DIFF-001)

The diff layer supports an arbitrary number of engines, each with specific content type requirements and configurations. The engine choice SHALL be explicit via the `DiffConfig`.

1.  **Binary Diff**:
    *   **Engine**: `bsdiff4` (as per `pyproject.toml` dependency).
    *   **Behavior**: Operates directly on byte streams. Produces a binary patch.
    *   **Requirements**: No content type requirements.
    *   **Config**: `BinaryDiffConfig`.

2.  **Text Diff**:
    *   **Engine**: `myers` (Myers algorithm).
    *   **Behavior**: Operates on text with supported encodings (e.g., UTF-8). Produces a unified diff format.
    *   **Requirements**: Input content must be valid text of a supported encoding. Failure to meet this SHALL result in an explicit error (WKS-DIFF-003).
    *   **Config**: `TextDiffConfig`.

3.  **Code Diff**:
    *   **Engine**: `ast` (Abstract Syntax Tree diff).
    *   **Behavior**: Operates on code, parsing it into an AST and comparing structural changes. Ignores purely formatting changes (configurable). Produces a structured report of code modifications (e.g., function added, variable renamed, statement changed).
    *   **Requirements**: Input content must be valid code for the specified `language`. Failure to meet this SHALL result in an explicit error (WKS-DIFF-003).
    *   **Config**: `CodeDiffConfig`.

## 3. "Full Diff" Behavior and Schema (WKS-DIFF-002)

The `wksm_diff` (MCP) and `wksc diff` (CLI) interfaces SHALL return a strongly-typed `DiffResult` object. This object encapsulates the diff output, metadata, and status, ensuring all necessary information is available for consumption.

### Input Parameters

The primary interface `wksm_diff` SHALL accept the following validated inputs:
-   `named_engine: str`: The name of the configured diff engine to use (as defined in `config.json`).
-   `target_a: str`: A reference to the first content for diffing. This MUST be a checksum of content residing in the transform cache.
-   `target_b: str`: A reference to the second content for diffing. This MUST be a checksum of content residing in the transform cache.

**Note**: Diff operations implicitly or explicitly require prior transformation. `target_a` and `target_b` represent the outputs of previous transform operations (e.g., Markdown from a PDF), and thus operate on files already residing in the transform cache.

### Output Schema (`DiffResult` - Dataclass style)

```python
from dataclasses import dataclass
from typing import Literal, Optional, List, Dict, Any

@dataclass(frozen=True)
class DiffMetadata:
    engine_used: str  # e.g., 'bsdiff4', 'myers', 'ast'
    is_identical: bool
    file_type_a: Optional[str] = None
    file_type_b: Optional[str] = None
    checksum_a: Optional[str] = None
    checksum_b: Optional[str] = None
    encoding_a: Optional[str] = None
    encoding_b: Optional[str] = None

@dataclass(frozen=True)
class TextDiffOutput:
    unified_diff: str
    patch_format: Literal["unified"] = "unified"

@dataclass(frozen=True)
class BinaryDiffOutput:
    patch_path: str
    patch_size_bytes: int

@dataclass(frozen=True)
class CodeDiffOutput:
    # Structured list of code changes (e.g., AST differences)
    # Example: [{"type": "function_added", "name": "new_func", "location": "file:line"}]
    structured_changes: List[Dict[str, Any]]

@dataclass(frozen=True)
class DiffResult:
    status: Literal["success", "failure"]
    metadata: DiffMetadata
    # The actual diff content is optional and type-specific
    diff_output: Optional[TextDiffOutput | BinaryDiffOutput | CodeDiffOutput] = None
    message: Optional[str] = None
    # In case of failure, a more detailed error object
    error_details: Optional[Dict[str, Any]] = None
```

## 4. Failure Modes and NoHedging (WKS-DIFF-003)

The diff layer SHALL adhere strictly to the NoHedging rule (WKS-DIFF-003).
-   **Missing/Invalid Inputs**: Any required input (e.g., `target_a`, `config`) that is missing or fails validation SHALL result in an immediate and explicit error. No placeholder defaults will be used.
-   **Unsupported Content Type**: If an engine (e.g., `text` or `ast`) receives content that it cannot process (e.g., binary file for `text` diff), it SHALL fail fast and return a `DiffResult` with `status: "failure"` and detailed `error_details`.
-   **Engine-Specific Errors**: Errors during diff computation (e.g., AST parsing failure, `bsdiff4` corruption) SHALL be caught and reported explicitly in `DiffResult.error_details`.
-   **Resource Limits**: If `timeout_seconds` or `max_size_mb` limits are exceeded, the operation SHALL terminate and return a `DiffResult` with `status: "failure"` and appropriate `error_details`.

## 5. Diffing Transformed Content and Indices (WKS-DIFF-004, WKS-DIFF-005)

The diff layer's interface `wksm_diff` is designed to be agnostic to the source of `target_a` and `target_b`. If these targets are checksums referencing cached transformed content (WKS-DIFF-004) or identifiers for indices (WKS-DIFF-005), the diff layer SHALL retrieve the actual content/data from a content store or index manager before performing the diff operation. This retrieval mechanism is external to the diff engine itself but integrated into the `wksm_diff` interface.

## 6. Database Integration
Since diffs (like transformed content) are resources derived from existing content, their metadata and artifacts (e.g., binary patches) SHALL be managed within the existing transform cache mechanism. Explicit diff records MAY be stored as metadata linked to the original content nodes or within a generalized metadata collection, but not in a separate `diff` collection.

**Considerations for Diff Metadata Storage:**

-   **Existing Node/Edge Metadata**: Diff-related properties (e.g., `diff_id`, `engine_type`, `engine_config_hash`, `patch_uri`, `structured_diff_uri`) could be attributes on `diff` type edges in the Knowledge Graph.
-   **Generic Metadata Collection**: A general metadata collection could store diff records, linked by `diff_id` or checksums.

Specific schema for diff records will depend on the chosen integration pattern with the existing Knowledge Graph and Transform database structure. It must allow for efficient retrieval and querying of diffs.

## 7. Graph Integration
When a diff is successfully computed (or retrieved from cache), the system MAY update the Knowledge Graph if deemed beneficial for traceability or analysis:

1.  **Nodes**: Ensure `checksum_a` and `checksum_b` (representing content nodes) exist in the `nodes` database.
2.  **Edge**: Create a directed edge from `checksum_a` to `checksum_b` with type `diff`.
    - This explicitly links the two versions that were compared.
    - The edge can optionally contain metadata about the diff (e.g., `engine_type`, `diff_id`).

This integration is optional but provides powerful capabilities for version analysis and change tracking within the Knowledge Graph.

## 8. CLI Interface

### diff
- Command: `wksc diff <named_engine> <target_a> <target_b> [options]`
- No args: `wksc diff` - Lists available named diff engines with their types and configurations.
- Named Engine only: `wksc diff <named_engine>` - Shows info about the named engine, its type, and configuration.
- Behavior: Computes a diff between two targets using the specified named engine. Returns a `DiffResult` (or a raw diff if `--raw` is used).
    - **Configuration Overrides**: Any key defined in the named engine's `data` configuration block (e.g., `context_lines` for `myers`) can be overridden via CLI flags.
    - **Scripting**: Use `--raw` to output *only* the raw diff content (e.g., unified diff string, binary patch path) to STDOUT.
    - **Example**: `wksc diff myers-default file_a.txt file_b.txt --context-lines 5`
- Output: `DiffResult` (or raw string/path if `--raw`)

### cat (top-level)
- Command: `wksc cat <diff_id_or_patch_path>`
- TARGET can be a `diff_id` (from the diff database) or a path to a cached diff patch.
- Behavior: Retrieves cached diff content and prints to stdout.
- Output: Raw diff content to stdout (e.g., unified diff, binary patch content).
