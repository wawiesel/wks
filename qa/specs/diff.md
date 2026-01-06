# Diff Layer Specification

**Purpose**: To provide a robust, pluggable mechanism for calculating and presenting differences between various forms of content, adhering strictly to WKS-DIFF requirements and NoHedging principles.

**Referenced Requirements**:
This specification fulfills the requirements outlined in `qa/reqs/diff/`.

## 1. Configuration (Config-First Approach)

The diff layer configuration SHALL be explicit and strongly-typed. All configurable options for diff engines and behaviors SHALL be defined in a dedicated configuration schema using immutable dataclasses. Defaults are discouraged; explicit values or clear error handling for missing configuration are mandated by NoHedging (WKS-DIFF-003).

### Example Configuration Schema (Dataclass style)

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass(frozen=True)
class BinaryDiffConfig:
    engine: Literal["bsdiff4"]
    # No specific options for bsdiff4 currently

@dataclass(frozen=True)
class TextDiffConfig:
    engine: Literal["myers"]
    context_lines: int = 3
    ignore_whitespace: bool = False

@dataclass(frozen=True)
class CodeDiffConfig:
    engine: Literal["ast"]
    language: str  # e.g., 'python', 'java' - Required, no default
    ignore_comments: bool = True

@dataclass(frozen=True)
class DiffConfig:
    # The engine config determines the mode
    engine_config: BinaryDiffConfig | TextDiffConfig | CodeDiffConfig
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
-   `config: DiffConfig`: An instance of the validated diff configuration.
-   `target_a: str`: A path to the first file, or a unique identifier (e.g., checksum) for content.
-   `target_b: str`: A path to the second file, or a unique identifier (e.g., checksum) for content.

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
