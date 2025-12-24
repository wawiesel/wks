# Vault Module

The Vault module provides an abstraction layer for interacting with markdown knowledge bases (vaults). It is designed using a Facade + Bridge pattern similar to the Database module to support multiple backend implementations (e.g., Obsidian, plain markdown).

## Architecture

### Facade (`Vault.py`)
The `Vault` class is the main entry point. It implements the Context Manager protocol (`with Vault(...) as vault:`) and delegates operations to a concrete backend implementation determined by the configuration.

```python
from wks.api.vault.Vault import Vault

with Vault(config) as vault:
    for file_path in vault.iter_markdown_files():
        print(file_path)
```

### Configuration (`VaultConfig.py`)
The `VaultConfig` model defines the configuration schema. It requires a `type` field (e.g., "obsidian") and a `base_dir`.

```json
"vault": {
    "type": "obsidian",
    "base_dir": "~/my_vault"
}
```

### Backend Implementations
Backends are located in subpackages (e.g., `_obsidian`). Each backend must implement the `_AbstractBackend` interface.

- **_AbstractBackend.py**: Defines the contract for vault backends.
- **_obsidian/_Backend.py**: Concrete implementation for Obsidian vaults.

### Registry
The `VaultConfig._BACKEND_REGISTRY` maps backend type strings (e.g., "obsidian") to their module paths. This allows for dynamic loading of implementations.

## Key Components
- **Scanner**: (`_Scanner.py`) Responsible for parsing markdown files, extracting links, and validating them.

## Testing
The module is designed for testability. The `Vault` facade allows mocking the underlying implementation.

## Usage
Most commands (e.g., `cmd_sync`) interact with the vault via the `Vault` facade to ensure consistent resource management.
