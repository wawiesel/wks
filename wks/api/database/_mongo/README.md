# MongoDB Backend Implementation

This directory contains the MongoDB-specific implementation of the database API.

## MongoDB-Specific Details

**Collections**: MongoDB uses "collections" as its data organization unit. In the public API, these are referred to as "databases" for simplicity and backend-agnostic terminology.

**Implementation Mapping**:
- Public API `Database` class → MongoDB `Collection` object
- Public API `database_name` parameter → MongoDB collection name
- Public API `db_name` (prefix) → MongoDB database name

**Example**:
```python
# Public API usage
with Database(db_config, "monitor") as database:
    count = database.count_documents({})

# Internally maps to MongoDB:
# - Database: "wks" (from db_config.prefix)
# - Collection: "monitor" (from database_name parameter)
# - Full path: client["wks"]["monitor"]
```

## Configuration

MongoDB configuration uses the `_DbConfigData` class:

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

**Fields**:
- `uri` (string, required): MongoDB connection URI. Must start with `mongodb://` or `mongodb+srv://`.

## Implementation Details

The `_Impl` class in `_Impl.py` implements the abstract interface defined in `_AbstractImpl.py`. It:
- Uses `pymongo.MongoClient` for connections
- Maps public API methods to MongoDB collection operations
- Handles connection lifecycle via context manager

**Connection handling**: The implementation accesses its config data directly via `db_config.data.uri`. No need for convenience methods on `DatabaseConfig` - backends are self-contained and handle their own connection details.

**Note**: This implementation is internal. Application code should use the public `Database` API from `wks.api.database.Database`. If you need the MongoDB URI, access it from the backend's config data: `db_config.data.uri` (with proper type checking).
