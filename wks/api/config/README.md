# WKS Config Module

This module provides the top-level configuration system for WKS. All configuration sections are defined as Pydantic models and automatically validated.

## Architecture

- **`WKSConfig`**: Top-level Pydantic model that contains all configuration sections
- **Section Models**: Each section (monitor, database, daemon) is a separate Pydantic model
- **Automatic Validation**: Pydantic validates required fields and constructs nested models automatically
- **Uniform Handling**: All sections are treated identically - no special cases

## Adding a New Configuration Section

To add a new configuration section (e.g., `vault`, `metrics`, `cache`):

### 1. Create the Section Model

Create a new Pydantic model in the appropriate module (or create a new module if needed):

```python
# wks/api/newsection/NewSectionConfig.py
from pydantic import BaseModel, Field

class NewSectionConfig(BaseModel):
    """New section configuration."""

    setting1: str = Field(..., description="Required setting")
    setting2: int = Field(default=42, description="Optional setting with default")
```

### 2. Add to WKSConfig

Import and add the new section as a required field in `WKSConfig`:

```python
# wks/api/config/WKSConfig.py
from ..newsection.NewSectionConfig import NewSectionConfig

class WKSConfig(BaseModel):
    monitor: MonitorConfig
    database: DatabaseConfig
    daemon: DaemonConfig
    newsection: NewSectionConfig  # Add here
    # ...
```

### 3. Add to to_dict()

Add the new section to the `to_dict()` method:

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "monitor": self.monitor.model_dump(),
        "database": self.database.model_dump(),
        "daemon": self.daemon.model_dump(),
        "newsection": self.newsection.model_dump(),  # Add here
    }
```

### 4. That's It!

- **Automatic Validation**: Pydantic will automatically validate the new section on `WKSConfig.load()`
- **Automatic Construction**: Nested models are constructed automatically - no special handling needed
- **Automatic Discovery**: `cmd_show` will automatically include the new section (it uses `config.to_dict().keys()`)
- **Automatic Serialization**: `save()` will automatically include the new section via `to_dict()`

## Important Principles

1. **No Special Cases**: All sections are handled uniformly by Pydantic
2. **Required Fields**: All sections in `WKSConfig` are required (no `| None` or defaults)
3. **Pydantic Validation**: Let Pydantic handle validation - don't add manual checks
4. **Uniform Construction**: All sections are constructed the same way: `cls(**raw)` in `load()`

## Example: Adding a "vault" Section

```python
# 1. Create wks/api/vault/VaultConfig.py
from pydantic import BaseModel, Field

class VaultConfig(BaseModel):
    encryption_key: str = Field(..., description="Encryption key for vault")
    auto_sync: bool = Field(default=True, description="Auto-sync vault changes")

# 2. Update wks/api/config/WKSConfig.py
from ..vault.VaultConfig import VaultConfig

class WKSConfig(BaseModel):
    monitor: MonitorConfig
    database: DatabaseConfig
    daemon: DaemonConfig
    vault: VaultConfig  # Add here

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitor": self.monitor.model_dump(),
            "database": self.database.model_dump(),
            "daemon": self.daemon.model_dump(),
            "vault": self.vault.model_dump(),  # Add here
        }
```

After these changes:
- `WKSConfig.load()` will automatically validate and construct the vault section
- `wksc config` will automatically show "vault" in the sections list
- `wksc config vault` will automatically show the vault configuration
- `WKSConfig.save()` will automatically save the vault section

No other changes needed!
