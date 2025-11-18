"""Tests for config validation."""

import pytest
from pathlib import Path

from wks.config_validator import validate_config, validate_and_raise, ConfigValidationError


def test_valid_minimal_config(tmp_path):
    """Test that minimal valid config passes validation."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    include_path = tmp_path / "include"
    include_path.mkdir()

    cfg = {
        "vault": {
            "base_dir": str(vault_path),
            "wks_dir": "WKS",
            "update_frequency_seconds": 60,
            "database": "wks.vault",
        },
        "monitor": {
            "include_paths": [str(include_path)],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [".git"],
            "include_globs": [],
            "exclude_globs": ["*.tmp"],
            "touch_weight": 0.2,
        },
        "db": {
            "type": "mongodb",
            "uri": "mongodb://localhost:27017/",
        },
    }

    errors = validate_config(cfg)
    assert errors == []


def test_missing_vault():
    """Test that missing vault section is caught."""
    cfg = {
        "monitor": {},
    }

    errors = validate_config(cfg)
    # Config validator may still check for vault_path for backward compat
    # or may check for vault.base_dir - both are acceptable
    assert any("vault" in e.lower() or "vault_path" in e.lower() for e in errors)


def test_nonexistent_vault_path():
    """Test that non-existent vault path is caught."""
    cfg = {
        "vault": {
            "base_dir": "/nonexistent/path/to/vault",
            "wks_dir": "WKS",
        },
        "monitor": {},
    }

    errors = validate_config(cfg)
    # May check vault.base_dir or vault_path (backward compat)
    assert any("does not exist" in e or "nonexistent" in e.lower() for e in errors)



def test_touch_weight_validation(tmp_path):
    """monitor.touch_weight must be numeric and within range."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    include_path = tmp_path / "include"
    include_path.mkdir()

    cfg = {
        "vault": {
            "base_dir": str(vault_path),
            "wks_dir": "WKS",
        },
        "monitor": {
            "include_paths": [str(include_path)],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "touch_weight": 0.0,
        },
    }

    errors = validate_config(cfg)
    assert any("touch_weight" in e for e in errors)

    cfg["monitor"]["touch_weight"] = "not-a-number"
    errors = validate_config(cfg)
    assert any("touch_weight" in e for e in errors)

    cfg["monitor"]["touch_weight"] = 0.0005
    errors = validate_config(cfg)
    assert any("touch_weight" in e for e in errors)

    cfg["monitor"]["touch_weight"] = 0.2
    errors = validate_config(cfg)
    assert not any("touch_weight" in e for e in errors)

def test_validate_and_raise_success(tmp_path):
    """Test that validate_and_raise doesn't raise on valid config."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    cfg = {
        "vault": {
            "base_dir": str(vault_path),
            "wks_dir": "WKS",
            "update_frequency_seconds": 60,
            "database": "wks.vault",
        },
        "monitor": {
            "include_paths": [str(tmp_path)],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "touch_weight": 0.2,
        },
        "db": {
            "type": "mongodb",
            "uri": "mongodb://localhost:27017/",
        },
    }

    # Should not raise
    validate_and_raise(cfg)


def test_validate_and_raise_failure():
    """Test that validate_and_raise raises on invalid config."""
    cfg = {
        "vault": {"base_dir": ""},  # Invalid: empty
        "monitor": {},  # Missing required keys
    }

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_and_raise(cfg)

    # May check vault_path or vault.base_dir
    assert "vault" in str(exc_info.value).lower() or "vault_path" in str(exc_info.value).lower()
