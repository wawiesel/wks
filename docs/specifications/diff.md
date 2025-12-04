# Diff Layer Specification

**Purpose**: Calculate differences between files

The diff layer supports an arbitrary number of engines but for prototype purposes,
we consider a binary and text diff.

1. **Binary** — Operates on bytes directly
   - `bsdiff3` — Binary diff using bsdiff3 algorithm
   - No content type requirements

2. **Text** — Operates on text with supported encodings
   - `myers` — Text diff using Myers algorithm
   - Requires text content or supported encoding
   - Fails fast if file is not text/supported type

3. **Code** — Operates on code with supported languages
   - `ast` — Code AST diff
   - Requires code content or supported language
   - Fails fast if file is not code/supported language

**Diffing Transformed Content**:
Since transformations (e.g., PDF to Markdown) create new representations of content, the diff layer explicitly supports diffing via checksums. These checksums are returned by the Transform Layer (`wksm_transform`) and refer to the cached transformed content. This allows comparing different transformations of a document.

**Diffing Indices**:
Indices (e.g., Code AST, Document Embeddings) can be diffed to reveal semantic or structural changes. For example, diffing two Code AST indices can show which functions were added or modified, ignoring formatting changes.

## MCP Interface (Primary)

- `wksm_diff(engine, target_a, target_b)` — Calculate diff between two targets (files, checksums, or indices).

## CLI Interface (Secondary)

- `wksc diff` — Calculate diff (e.g., `wksc diff <engine> <file_a> <file_b>` or `wksc diff <engine> <checksum_a> <checksum_b>`)
