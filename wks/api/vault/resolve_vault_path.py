from pathlib import Path

from .VaultPathError import VaultPathError


def resolve_vault_path(
    input_path: str,
    vault_path: Path,
    cwd: Path | None = None,
) -> tuple[str, Path]:
    from wks.api.config.normalize_path import normalize_path

    vault_path = normalize_path(vault_path)
    cwd = normalize_path(cwd or Path.cwd())

    if input_path.startswith("vault:///"):
        rel_path_str = input_path[9:]  # Strip "vault:///"
        abs_path: Path = normalize_path(vault_path / rel_path_str)
        if not abs_path.exists():
            raise VaultPathError(f'"{input_path}" does not exist')
        return (input_path, abs_path)

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

    try:
        _ = cwd.relative_to(vault_path)
        abs_path = normalize_path(cwd / input_path)
    except ValueError:
        abs_path = normalize_path(vault_path / input_path)

    try:
        rel_path = abs_path.relative_to(vault_path)
        vault_uri = f"vault:///{rel_path}"
        if not abs_path.exists():
            raise VaultPathError(f'"{vault_uri}" does not exist')
        return (vault_uri, abs_path)
    except ValueError:
        raise VaultPathError(f'"{input_path}" is not in the vault') from None
