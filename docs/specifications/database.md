# Database Specification

## Overview

The WKS database layer provides a clean abstraction over database operations, allowing different database backends to be used without changing application code. The public API is database-agnostic and does not expose any database-specific concepts.

## Public Interface

The database layer provides:

- **Collection Operations**: Context manager for collection operations (find, update, delete, count)
- **Query Operations**: Simple pass-through query function for read operations

These interfaces are database-agnostic and work with any backend implementation.

## Configuration

Database configuration is specified in the WKS config file under the `db` section:

```json
{
  "db": {
    "type": "mongo",
    "prefix": "wks",
    "data": {
      "uri": "mongodb://localhost:27017/"
    }
  }
}
```

**Required Fields**:
- `type`: String identifying the database backend type (e.g., `"mongo"`, `"mongomock"`)
- `prefix`: String specifying the database name prefix for collections
- `data`: Object containing backend-specific configuration

**Configuration Requirements**:
- All configuration values must be present in the config file - no defaults are permitted in code
- If a required field is missing, validation must fail immediately with a clear error message
- Each backend type defines its own `data` structure
- The `prefix` value is automatically prepended to collection names

**Collection Naming**: Collection names specified in other config sections (e.g., `monitor.database: "monitor"`) are automatically prefixed with the `db.prefix` value. For example, with `prefix: "wks"`, a collection named `"monitor"` is accessed as `"wks.monitor"` in the database. Application code should specify just the collection name without the prefix.

## Backend Support

The system supports multiple database backends. The backend implementation is determined at configuration load time based on the `db.type` value. Each backend:

- Defines its own configuration structure in the `data` field
- Implements the same public interface as other backends
- Can be used by changing only the `db.type` configuration value

**Example Backends**:
- `"mongo"`: MongoDB implementation (example: requires `data.uri` field)
- `"mongomock"`: In-memory mock implementation for testing (example: may have different `data` requirements)

The specification does not require any specific backend - any backend that implements the required interface can be used.

## Principles

1. **Abstraction**: The public API must be database-agnostic. Application code must not reference database-specific concepts, types, or imports.

2. **Interface Consistency**: All backend implementations must provide the same interface, allowing code to switch between backends by changing only the `db.type` configuration value.

3. **Type-Based Selection**: The database implementation is determined at configuration load time based on `db.type`. The system must validate that the specified type is supported and that the provided `data` structure matches the requirements for that type.

4. **No Defaults in Code**: All configuration fields must be required. No defaults are permitted in code - all values must come from the config file. Missing values cause validation to fail immediately.

5. **Isolation**: All database-specific code must be isolated from the public API. The public API must never expose database-specific concepts, allowing implementations to be swapped without affecting application code.

