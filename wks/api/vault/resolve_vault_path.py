"""Vault path resolution utility.

Resolves user input paths to vault:/// URIs with CWD-awareness.
Per vault specification:
- CWD inside vault: relative paths are relative to CWD within vault
- CWD outside vault: relative paths are relative to vault root
- Absolute paths in vault: converted to vault:/// URI
- Paths outside vault or non-existent: error
"""

from pathlib import Path

from .VaultPathError import VaultPathError


def resolve_vault_path(
    input_path: str,
    vault_path: Path,
    cwd: Path | None = None,
) -> tuple[str, Path]:
    """Resolve user input to vault URI and absolute filesystem path.

    Args:
        input_path: User input (relative path, absolute path, or vault:/// URI)
        vault_path: Absolute path to vault root directory
        cwd: Current working directory (defaults to Path.cwd())

    Returns:
        Tuple of (vault_uri, absolute_path)

    Raises:
        VaultPathError: If path is outside vault or doesn't exist
    """
    from wks.api.config.normalize_path import normalize_path

    vault_path = normalize_path(vault_path)
    cwd = normalize_path(cwd or Path.cwd())

    # Case 1: Already a vault:/// URI
    if input_path.startswith("vault:///"):
        rel_path_str = input_path[9:]  # Strip "vault:///"
        abs_path: Path = normalize_path(vault_path / rel_path_str)
        if not abs_path.exists():
            raise VaultPathError(f'"{input_path}" does not exist')
        return (input_path, abs_path)

    # Case 2: file:// URI - extract path and check if in vault
    if input_path.startswith("file://"):
        from wks.api.config.URI import URI

        abs_path = normalize_path(URI(input_path).path)
        try:
            rel_path = abs_path.relative_to(vault_path)
            vault_uri = f"vault:///{rel_path}"
            if not abs_path.exists():
                raise VaultPathError(f'"{vault_uri}" does not exist')
            return (vault_uri, abs_path)
        except ValueError:
            raise VaultPathError(f'"{input_path}" is not in the vault') from None

    # Case 3: Absolute path
    if Path(input_path).is_absolute():
        abs_path = normalize_path(input_path)
        try:
            rel_path = abs_path.relative_to(vault_path)
            vault_uri = f"vault:///{rel_path}"
            if not abs_path.exists():
                raise VaultPathError(f'"{vault_uri}" does not exist')
            return (vault_uri, abs_path)
        except ValueError:
            raise VaultPathError(f'"{input_path}" is not in the vault') from None

    # Case 4: Relative path
    # If CWD is inside vault, resolve relative to CWD
    # Otherwise, resolve relative to vault root
    try:
        _ = cwd.relative_to(vault_path)
        # CWD is inside vault - resolve relative to CWD
        abs_path = normalize_path(cwd / input_path)
    except ValueError:
        # CWD is outside vault - resolve relative to vault root
        abs_path = normalize_path(vault_path / input_path)

    # Check if resolved path is within vault
    try:
        rel_path = abs_path.relative_to(vault_path)
        vault_uri = f"vault:///{rel_path}"
        if not abs_path.exists():
            raise VaultPathError(f'"{vault_uri}" does not exist')
        return (vault_uri, abs_path)
    except ValueError:
        raise VaultPathError(f'"{input_path}" is not in the vault') from None
