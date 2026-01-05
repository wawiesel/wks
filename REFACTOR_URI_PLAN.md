# URI Consistency Refactoring Plan

## Overview
Migrate all string-based URI handling to use the `URI` type throughout the codebase.

## Priority Areas

### 1. Utility Functions (High Impact)
- [ ] Update `convert_to_uri()` to return `URI` instead of `str`
- [ ] Update `uri_to_path()` to accept `URI` instead of `str`
- [ ] Update all callers of these functions

### 2. Database Models (High Impact)
- [ ] Update `_TransformRecord.file_uri` from `str` to `URI`
- [ ] Update `_TransformRecord.cache_uri` from `str` to `URI`
- [ ] Update `_TransformRecord.referenced_uris` from `list[str]` to `list[URI]`
- [ ] Update serialization/deserialization logic

### 3. API Functions
- [ ] Update `_TransformController._update_graph()` to use `URI` for `file_uri`
- [ ] Update `_TransformController.remove_by_uri()` to use `URI`
- [ ] Update `_TransformController.update_uri()` to use `URI`
- [ ] Update `get_content()` to use `URI` for `target`
- [ ] Update `resolve_remote_uri()` to return `URI | None` instead of `str | None`

### 4. Internal Functions
- [ ] Update `_identity()` functions to use `URI` for URI parameters
- [ ] Update `_note_to_uri()` to return `URI`
- [ ] Update `_note_path()` to return `URI`

### 5. Database Operations
- [ ] Ensure all database write operations validate URI fields
- [ ] Update database query functions to work with `URI` type

## Implementation Strategy

1. Start with utility functions (foundational)
2. Update database models (affects persistence layer)
3. Update API functions (public interface)
4. Update internal functions (implementation details)
5. Add validation and type hints
