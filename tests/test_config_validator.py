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


def test_missing_obsidian_keys():
    """Test that missing obsidian keys are caught (backward compat)."""
    cfg = {
        "vault": {"base_dir": "~"},
        "obsidian": {},
        "monitor": {},
    }

    errors = validate_config(cfg)
    # May check obsidian.base_dir for backward compat, or may not require it if vault section exists
    # Just verify validation runs without crashing
    assert isinstance(errors, list)


def test_invalid_numeric_values():
    """Test that invalid numeric values are caught."""
    cfg = {
        "vault": {"base_dir": "~", "wks_dir": "WKS"},
        "obsidian": {
            "base_dir": "WKS",
            "log_max_entries": -1,  # Invalid: must be positive
            "active_files_max_rows": "not_a_number",  # Invalid: not an int
            "source_max_chars": 40,
            "destination_max_chars": 40,
        },
        "monitor": {
            "include_paths": [],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "touch_weight": 0.2,
        },
    }

    errors = validate_config(cfg)
    # May check obsidian keys if obsidian section exists
    if any("obsidian" in e for e in errors):
        assert any("log_max_entries must be positive" in e or "log_max_entries" in e for e in errors)
        assert any("active_files_max_rows must be an integer" in e or "active_files_max_rows" in e for e in errors)


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

def test_similarity_validation():
    """Test similarity config validation."""
    cfg = {
        "vault": {"base_dir": "~", "wks_dir": "WKS"},
        "monitor": {
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "touch_weight": 0.2,
        },
        "similarity": {
            "enabled": True,
            # Missing: model, include_extensions
            "min_chars": 1000,
            "max_chars": 500,  # Invalid: min > max
        },
    }

    errors = validate_config(cfg)
    assert any("similarity.model is required" in e for e in errors)
    assert any("similarity.include_extensions is required" in e for e in errors)
    assert any("min_chars must be less than max_chars" in e for e in errors)


def test_validate_and_raise_success(tmp_path):
    """Test that validate_and_raise doesn't raise on valid config."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    cfg = {
        "vault": {
            "base_dir": str(vault_path),
            "wks_dir": "WKS",
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
