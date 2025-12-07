# Database Specification

All layers store data in a configurable database backend. This specification describes the database abstraction and supported backends.

**CLI Interface**:
```bash
# List databases
wksc database list                           # List available databases

# Show databases
wksc database show <database>                # Show database contents
wksc database show <database> --query '{"key": "value"}'  # Show with filter
wksc database show <database> --limit 100    # Limit number of results

# Reset databases (destructive)
wksc database reset <database>                # Clear all documents from database
```

**Database Names**: Database names are specified without the prefix. The prefix from `database.prefix` configuration is automatically prepended. For example, with `prefix: "wks"`, specifying `monitor` accesses the `wks.monitor` database. Users must never specify the prefix in database names - only provide the database name itself.

## Overview

The WKS database layer provides a clean abstraction over database operations, allowing different database backends to be used without changing application code. The public API is database-agnostic and does not expose any database-specific concepts.

## Public Interface

The database layer provides:

- **Database Operations**: Context manager for database operations (find, update, delete, count)
- **Query Operations**: Simple pass-through query function for read operations

These interfaces are backend-agnostic and work with any database backend implementation.

## Configuration

Database configuration is specified in the WKS config file under the `database` section:

```json
{
  "database": {
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

**Database Naming**: Database names specified in other config sections (e.g., `monitor.database: "monitor"`) are automatically prefixed with the `database.prefix` value. For example, with `prefix: "wks"`, a database named `"monitor"` is accessed as `"wks.monitor"` in the backend. Application code should specify just the database name without the prefix.

## Backend Support

The system supports multiple database backends. The backend implementation is determined at configuration load time based on the `database.type` value. Each backend:

- Defines its own configuration structure in the `data` field
- Implements the same public interface as other backends
- Can be used by changing only the `database.type` configuration value

**Example Backends**:
- `"mongo"`: MongoDB implementation (example: requires `data.uri` field)
- `"mongomock"`: In-memory mock implementation for testing (example: may have different `data` requirements)

The specification does not require any specific backend - any backend that implements the required interface can be used.

## Principles

1. **Abstraction**: The public API must be database-agnostic. Application code must not reference database-specific concepts, types, or imports.

2. **Interface Consistency**: All backend implementations must provide the same interface, allowing code to switch between backends by changing only the `database.type` configuration value.

3. **Type-Based Selection**: The database implementation is determined at configuration load time based on `database.type`. The system must validate that the specified type is supported and that the provided `data` structure matches the requirements for that type.

4. **No Defaults in Code**: All configuration fields must be required. No defaults are permitted in code - all values must come from the config file. Missing values cause validation to fail immediately.

5. **Isolation**: All database-specific code must be isolated from the public API. The public API must never expose database-specific concepts, allowing implementations to be swapped without affecting application code.

