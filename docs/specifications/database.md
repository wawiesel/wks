# Database Specification

## Overview

The WKS database layer provides a clean abstraction over database operations, allowing different database backends to be used without changing application code. All database-specific code is isolated in implementation modules, and the public API is database-agnostic.

## Architecture

### Database Abstraction Layer

The database API is located in `wks/api/db/` and provides:

- **`DatabaseCollection`**: Context manager for collection operations (find, update, delete, count)
- **`query()`**: Simple pass-through query function for read operations

These interfaces are database-agnostic and do not expose any database-specific concepts.

### Implementation Modules

Database implementations are located in `wks/api/db/_<type>/` subdirectories:

- **`_mongo/`**: MongoDB implementation using PyMongo
- **`_mockmongo/`**: In-memory mock implementation for testing

Each implementation module provides:

- **`client.py`**: Connection management (`connect()` function)
- **`collection.py`**: Collection operations wrapper class
- **`query.py`**: Query operations function
- **`*DbConfig.py`**: Configuration class for the database type

### Configuration

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

The `type` field determines which database implementation to use. The `prefix` field specifies the database name prefix for collections (default: "wks"). The unified `DbConfig` class in `wks/api/db/DbConfig.py` handles validation and loading of backend-specific configurations:

- When `type="mongo"`, the `data` field contains `_MongoDbConfigData` with MongoDB-specific settings (currently just `uri`)
- When `type="mongomock"`, the `data` field contains `_MongoMockDbConfigData` with mock-specific settings

Each backend can define its own configuration structure. The `DbConfig` class uses Pydantic validation to ensure the correct backend config is present when a type is specified.

**Collection Naming**: Collection names in config files (e.g., `monitor`, `vault`, `transform`) are automatically prefixed with the `prefix` value. For example, with `prefix: "wks"`, a collection named `"monitor"` is accessed as `"wks.monitor"`. The prefix is handled automatically by `DbCollection` - users should specify just the collection name without the prefix.

### Adding New Database Types

To add support for a new database backend:

1. Create a new directory `wks/api/db/_<type>/`
2. Implement the required interfaces:
   - `client.py` with a `connect(uri, timeout_ms)` function
   - `collection.py` with a collection class that subclasses `_Collection` from `wks/api/db/_Collection.py`
   - `query.py` with a `query(uri, database_name, collection_name, query_filter, limit, projection)` function
3. Add backend-specific config to `wks/api/db/DbConfig.py`:
   - Create a new `*DbConfigData` Pydantic model (e.g., `PostgresDbConfigData`) with backend-specific fields
   - Add the field to `DbConfig` class (e.g., `postgres: PostgresDbConfigData | None`)
   - Update `from_config_dict()` to handle the new type
   - Update `get_uri()` to return the URI for the new backend
4. Update `_create_collection_impl()` in `DatabaseCollection.py` to handle the new type
5. Update `query()` in `query.py` to handle the new type
6. Update `db_callback()` in `app.py` to handle the new type

The implementation must provide the same interface as the existing implementations, but the internal details and configuration structure are completely database-specific.

## Principles

1. **Isolation**: All database-specific code (imports, types, concepts) must be contained within `_<type>/` directories. The public API in `wks/api/db/` must never reference database-specific concepts.

2. **Interface Consistency**: All implementations must provide the same interface, allowing code to switch between backends by changing the `db.type` configuration value.

3. **Type-Based Loading**: The database implementation is determined at configuration load time based on `db.type`. The config system loads the appropriate `*DbConfig` class for the specified type.

4. **No Backend Enumeration**: The system does not maintain a hardcoded list of supported backends. Any backend that implements the required interfaces can be used by setting `db.type` appropriately.

## Usage

Application code uses the database abstraction layer:

```python
from wks.api.db import DbCollection

# Using DbCollection for operations (prefix is auto-prepended from config)
with DbCollection("monitor") as collection:
    count = collection.count_documents({})
    doc = collection.find_one({"path": "/some/path"})

# Using query() for simple queries (prefix is auto-prepended from config)
results = DbCollection.query("monitor", {"status": "active"}, limit=10)
```

The implementation details are hidden - the same code works with any database backend. Collection names are automatically prefixed with the `db.prefix` value from configuration.

