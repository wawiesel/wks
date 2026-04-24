"""Shared vault test helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from wks.api.database.DatabaseConfig import DatabaseConfig


def write_unit_config(wks_home: Path, config: dict) -> None:
    """Write one unit-test config file under the provided WKS home."""
    (wks_home / "config.json").write_text(json.dumps(config), encoding="utf-8")


def setup_vault_env(
    monkeypatch,
    tmp_path: Path,
    minimal_config_dict: dict,
    *,
    include_priority_dir: bool = False,
    create_vault_dir: bool = True,
    vault_base_dir: Path | None = None,
) -> tuple[Path, Path, dict]:
    """Create a minimal vault-oriented WKS home and return `(wks_home, vault_dir, config)`."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (vault_base_dir or (tmp_path / "vault")).resolve()
    if create_vault_dir:
        vault_dir.mkdir(parents=True, exist_ok=True)

    config = copy.deepcopy(minimal_config_dict)
    config["vault"]["base_dir"] = str(vault_dir)
    config["vault"]["type"] = "obsidian"
    if include_priority_dir:
        config["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}

    write_unit_config(wks_home, config)
    return wks_home, vault_dir, config


def vault_database_config(config: dict) -> DatabaseConfig:
    """Build the typed database config used by vault command tests."""
    return DatabaseConfig(**config["database"])
