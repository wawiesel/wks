# Handoff: URI Consistency Refactoring

## Current State

**PR #54**: `refactor/use-uri-consistently` branch is open and ready for continued work.

**What's Been Done:**
- ✅ Updated `convert_to_uri()` to return `URI` instead of `str`
- ✅ Updated `uri_to_path()` to accept `URI | str` instead of just `str`
- ✅ Both utility functions now support URI objects as input
- ✅ All tests pass, linting passes
- ✅ Created `REFACTOR_URI_PLAN.md` with migration plan

## Goal

Migrate all string-based URI handling to use the `URI` type throughout the codebase. This ensures type safety, prevents URI format errors, and makes the codebase more maintainable.

## Important Context

### URI Type Location
- `wks/api/URI.py` - The URI value object class
- URI objects are frozen dataclasses that validate URI format (must contain `://`)
- URI has methods: `from_path()`, `from_any()`, `to_path()`, `.path` property
- URI objects can be converted to strings with `str(uri)` or `uri.value`

### Current Utility Functions
- `convert_to_uri()` - Now returns `URI` (was `str`)
- `uri_to_path()` - Now accepts `URI | str` (was just `str`)
- Both functions handle backward compatibility

### Key Patterns to Follow

1. **Database Models**: Pydantic models store URIs as strings in MongoDB, but should use `URI` type in Python code
   - Use `str(uri)` when serializing to dict/JSON
   - Use `URI(uri_str)` when deserializing from dict/JSON

2. **API Functions**: Public API functions should accept `URI` type for URI parameters
   - Use `_ensure_arg_uri()` helper for validation
   - Example: `cmd_check(uri: URI, ...)` already uses this pattern

3. **Internal Functions**: Can use `URI` type directly
   - Avoid string concatenation for URIs: use `URI.from_path()` or `URI.from_any()`
   - Avoid `f"file://..."` - use URI constructors instead

## Next Steps (Priority Order)

### 1. Update Database Models (High Impact)
**File**: `wks/api/transform/_TransformRecord.py`

Current state:
```python
file_uri: str
cache_uri: str
referenced_uris: list[str]
```

Should become:
```python
file_uri: URI
cache_uri: URI
referenced_uris: list[URI]
```

**Implementation notes:**
- Pydantic models need custom serialization for `URI` type
- Use `@field_serializer` and `@field_validator` decorators
- Serialize to string for MongoDB: `str(uri)`
- Deserialize from string: `URI(uri_str)`
- Update `from_dict()` and `to_dict()` methods
- Update `cache_path_from_uri()` method (already uses URI internally)

**Files to check:**
- `wks/api/transform/_TransformController.py` - Uses `_TransformRecord`
- All places that create/update transform records

### 2. Update Transform Controller Methods
**File**: `wks/api/transform/_TransformController.py`

Methods to update:
- `_update_graph(file_uri: str, ...)` → `_update_graph(file_uri: URI, ...)`
- `remove_by_uri(file_uri: str)` → `remove_by_uri(file_uri: URI)`
- `update_uri(old_uri: str, new_uri: str)` → `update_uri(old_uri: URI, new_uri: URI)`
- `get_content(target: str, ...)` → `get_content(target: URI | str, ...)` (backward compat)

**Implementation notes:**
- Update all internal uses to work with `URI` type
- When storing in MongoDB, convert to string: `str(uri)`
- When reading from MongoDB, convert to URI: `URI(uri_str)`

### 3. Update Other API Functions
**Files to update:**
- `wks/api/monitor/resolve_remote_uri.py` - Return `URI | None` instead of `str | None`
- `wks/api/vault/_identity.py` - Use `URI` for `target_uri` parameter
- `wks/api/link/_identity.py` - Use `URI` for URI parameters
- `wks/api/vault/_obsidian/_Scanner.py` - `_note_to_uri()` should return `URI`

### 4. Update Internal Helper Functions
**Files to update:**
- Functions that create URIs should return `URI` type
- Functions that accept URI strings should accept `URI | str` for backward compatibility
- Remove inline URI string formatting (`f"file://..."`)

### 5. Database Operations
- Ensure all database write operations validate URI fields
- Convert `URI` to `str` when writing to MongoDB
- Convert `str` to `URI` when reading from MongoDB
- Add validation that URIs are properly formatted

## Testing Strategy

1. **Run tests after each change**: `pytest tests/ -x`
2. **Check for type errors**: `mypy wks/`
3. **Check linting**: `ruff check wks/`
4. **Test database operations**: Ensure transform records still work
5. **Test API functions**: Ensure public APIs still work

## Common Patterns

### Pattern 1: Accepting URI input (backward compatible)
```python
def my_function(uri: URI | str) -> SomeResult:
    # Convert to URI if needed
    uri_obj = URI(uri) if isinstance(uri, str) else uri
    # Use uri_obj...
```

### Pattern 2: Returning URI
```python
def my_function(...) -> URI:
    return URI.from_path(some_path)
```

### Pattern 3: Database serialization
```python
# In Pydantic model
@field_serializer('file_uri')
def serialize_uri(self, uri: URI) -> str:
    return str(uri)

@field_validator('file_uri', mode='before')
def validate_uri(cls, v: str | URI) -> URI:
    return URI(v) if isinstance(v, str) else v
```

### Pattern 4: Database operations
```python
# Writing to MongoDB
mongo_db["collection"].update_one(
    {"uri": str(uri_obj)},  # Convert to string
    {"$set": {"uri": str(uri_obj)}}
)

# Reading from MongoDB
doc = mongo_db["collection"].find_one({"uri": str(uri_obj)})
if doc:
    uri = URI(doc["uri"])  # Convert back to URI
```

## Important Constraints

1. **Backward Compatibility**: Many callers may still pass strings - support both `URI` and `str` where possible
2. **Database Storage**: MongoDB stores URIs as strings - always convert when reading/writing
3. **Type Safety**: Use type hints consistently - `URI` for URI objects, `str` only for URI strings when necessary
4. **Validation**: The `URI` class validates format automatically - trust it
5. **No Inline Formatting**: Never use `f"file://{path}"` - use `URI.from_path()` or `URI.from_any()`

## Files to Review

Key files that likely need updates:
- `wks/api/transform/_TransformRecord.py` - Database model
- `wks/api/transform/_TransformController.py` - Transform operations
- `wks/api/transform/get_content.py` - Public API
- `wks/api/monitor/resolve_remote_uri.py` - Remote URI resolution
- `wks/api/vault/_obsidian/_Scanner.py` - Vault scanning
- `wks/api/link/_identity.py` - Link identity generation
- `wks/api/vault/_identity.py` - Vault identity generation

## Reference

- **Plan Document**: `REFACTOR_URI_PLAN.md`
- **URI Class**: `wks/api/URI.py`
- **NEXT.md**: "Use URI Consistently Everywhere [P1]" section
- **Current PR**: https://github.com/wawiesel/wks/pull/54

## Questions to Consider

1. Should we update all callers of `convert_to_uri()` immediately, or do it gradually?
2. How should we handle existing database records with string URIs?
3. Should we add migration scripts for existing data?

## Success Criteria

- [ ] All database models use `URI` type for URI fields
- [ ] All API functions accept `URI` type for URI parameters
- [ ] All internal functions use `URI` type instead of strings
- [ ] No inline URI string formatting (`f"file://..."`)
- [ ] All tests pass
- [ ] Type checking passes (`mypy`)
- [ ] Linting passes (`ruff`)

Good luck! 🚀
