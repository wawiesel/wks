"""Config save behavior.

Requirements Satisfied:

- CONFIG.1
- CONFIG.2
"""

import json

import pytest

from wks.api.config.WKSConfig import WKSConfig


@pytest.mark.config
def test_save_writes_file(tmp_path, monkeypatch, minimal_config_dict):
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir()
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    cfg = WKSConfig(**minimal_config_dict)

    cfg.save()

    config_path = home_dir / "config.json"
    assert config_path.exists()
    loaded = json.loads(config_path.read_text())
    assert "monitor" in loaded
    assert "database" in loaded
    assert "daemon" in loaded


@pytest.mark.config
def test_save_atomic_write(tmp_path, monkeypatch, minimal_config_dict):
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir()
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    cfg = WKSConfig(**minimal_config_dict)
    config_path = home_dir / "config.json"

    cfg.save()
    temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    assert not temp_path.exists()
    assert config_path.exists()


@pytest.mark.config
def test_save_cleans_up_temp_on_error(tmp_path, monkeypatch, minimal_config_dict):
    home_dir = tmp_path / "wks_home"
    home_dir.mkdir()
    monkeypatch.setenv("WKS_HOME", str(home_dir))
    cfg = WKSConfig(**minimal_config_dict)
    config_path = home_dir / "config.json"
    temp_path = config_path.with_suffix(config_path.suffix + ".tmp")

    # Make the directory read-only to cause an error during save
    config_path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = config_path.parent.stat().st_mode
    config_path.parent.chmod(0o444)
    try:
        with pytest.raises(RuntimeError):
            cfg.save()
    finally:
        # Restore permissions before checking temp file existence
        # This prevents permission errors when pytest-xdist tries to clean up
        config_path.parent.chmod(original_mode)

    assert not temp_path.exists()
