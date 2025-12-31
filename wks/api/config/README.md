# WKS Config Module

## Why This Design Exists

The config module uses **Pydantic for everything** to eliminate manual validation, provide type safety, and automatically construct nested models. No manual validation code, no special cases, automatic construction from raw dicts. The alternative would require hundreds of lines of error-prone code.

## Core Principles

### All Sections and Fields Are Required

Every section in `WKSConfig` and every field within sections is required (no `| None` or defaults). Forces explicit configuration - missing anything makes the config invalid. Explicit is better than implicit, invalid configs fail fast at load time, all configuration is visible in JSON.

### Uniform Handling

All sections treated identically: `model_dump()` for serialization, `cls(**raw)` construction, automatic appearance in `cmd_show` via `to_dict().keys()`, no if/else logic. Adding a new section requires zero changes to existing code.

### Pydantic Does Everything

No manual validation, custom constructors, or special handling. Pydantic handles validation, type coercion, nested construction, field descriptions. If writing `if field is None:` or `validate_*()`, use Pydantic validators instead.

## When to Add a Configuration Section

Add when: (1) new domain/feature needs persistent configuration, (2) configuration is substantial (multiple related settings), (3) configuration needs validation. Don't add for: single boolean flags (use CLI args), temporary features (use feature flags), frequently-changing settings (config should be stable).

## How to Add a Configuration Section

### 1. Create the Section Model

```python
# wks/api/newdomain/NewDomainConfig.py
from pydantic import BaseModel, Field

class NewDomainConfig(BaseModel):
    """New domain configuration."""
    required_setting: str = Field(..., description="Required setting")
    another_setting: int = Field(..., description="Another required setting")
```

**Standards:** One file per class, all fields required (`Field(...)`, no defaults), descriptive docstrings.

### 2. Add to WKSConfig

```python
# wks/api/config/WKSConfig.py
from ..newdomain.NewDomainConfig import NewDomainConfig

class WKSConfig(BaseModel):
    monitor: MonitorConfig
    database: DatabaseConfig
    daemon: DaemonConfig
    newdomain: NewDomainConfig  # REQUIRED, no | None
```

**Standards:** All sections required, import from domain module, logical order.

### 3. Add to to_dict()

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "monitor": self.monitor.model_dump(),
        "database": self.database.model_dump(),
        "daemon": self.daemon.model_dump(),
        "newdomain": self.newdomain.model_dump(),  # Add here
    }
```

**Standards:** Use `model_dump()` for all, maintain order, no conditional logic.

### 4. That's It

After these three changes: `WKSConfig.load()` validates/constructs automatically, `cmd_show` includes it automatically, `WKSConfig.save()` saves it automatically, CLI help shows it automatically. No other changes needed.

## Standards

**File Organization:** One file per class, domain modules own their config (`MonitorConfig` in `wks/api/monitor/`), no shared config files. Top-level domain configs (referenced in WKSConfig) MUST be public (e.g., `TransformConfig`), but sub-configurations SHOULD be private models prefixed with `_` (e.g., `_CacheConfig`) unless they have independent utility.

**Field Requirements:** All sections and fields required (no `| None`, no `Field(default=...)` or `default_factory`), no manual defaults.

**Validation:** Pydantic validators only (`@field_validator` or `@model_validator`), no custom constructors (`cls(**raw)`), fail fast (exceptions at load time).

**Serialization:** Always `model_dump()`, uniform format, no conditional logic (all sections always included).

**Commands:** `cmd_show` automatic (`to_dict().keys()`), no special cases, all sections handled identically.

**Output schemas:** All commands use registered output schemas from normative JSON schemas in `docs/specifications/config_output.schema.json`. Schemas are auto-registered via `schema_loader.register_from_schema("config")` in `__init__.py`. Import the schema class (e.g., `ConfigListOutput`), instantiate it with output data, and call `.model_dump(mode="python")` to convert to dict. This ensures type safety and consistent structure. The JSON schema is the single source of truth - Pydantic models are dynamically generated from it.

## Anti-Patterns

**Don't:** Optional sections (`newdomain: NewDomainConfig | None`), manual validation (`if "newdomain" not in raw`), special cases (`if section == "newdomain"`), custom constructors (`NewDomainConfig.from_dict(...)`), manual defaults (`raw.get("newdomain", default)`).

**Do:** Required sections (`newdomain: NewDomainConfig`), Pydantic validation, uniform handling (`model_dump()`), automatic construction (`cls(**raw)`), no defaults (`Field(...)`).
