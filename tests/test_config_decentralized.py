import pytest

from wks.transform.config import CacheConfig, EngineConfig, TransformConfig, TransformConfigError
from wks.vault.config import VaultConfig, VaultConfigError


class TestTransformConfig:
    def test_cache_config_validation(self):
        # Valid
        c = CacheConfig(location=".wks/cache", max_size_bytes=100)
        assert c.location == ".wks/cache"

        # Invalid location
        with pytest.raises(TransformConfigError) as exc:
            CacheConfig(location="", max_size_bytes=100)
        assert "location must be a non-empty string" in str(exc.value)

        # Invalid size
        with pytest.raises(TransformConfigError) as exc:
            CacheConfig(location="loc", max_size_bytes=0)
        assert "max_size_bytes must be a positive integer" in str(exc.value)

    def test_engine_config_validation(self):
        # Valid
        e = EngineConfig(name="test", enabled=True, options={})
        assert e.name == "test"

        # Invalid name
        with pytest.raises(TransformConfigError):
            EngineConfig(name="", enabled=True, options={})

        # Invalid enabled
        with pytest.raises(TransformConfigError):
            EngineConfig(name="test", enabled="yes", options={})

        # Invalid options
        with pytest.raises(TransformConfigError):
            EngineConfig(name="test", enabled=True, options="opts")

    def test_transform_config_from_dict(self):
        # Valid config
        cfg = {
            "transform": {
                "cache": {"location": "loc", "max_size_bytes": 100},
                "engines": {"docling": {"enabled": True, "opt1": "val1"}},
            }
        }
        tc = TransformConfig.from_config_dict(cfg)
        assert tc.cache.location == "loc"
        assert tc.engines["docling"].enabled is True
        assert tc.engines["docling"].options["opt1"] == "val1"

        # Missing transform section
        with pytest.raises(TransformConfigError):
            TransformConfig.from_config_dict({})

        # Invalid engine dict
        cfg["transform"]["engines"]["docling"] = "not a dict"
        with pytest.raises(TransformConfigError):
            TransformConfig.from_config_dict(cfg)


class TestVaultConfig:
    def test_vault_config_validation(self):
        # Valid
        v = VaultConfig(
            vault_type="obsidian",
            base_dir="/tmp/vault",
            wks_dir=".wks",
            update_frequency_seconds=10.0,
            database="wks.vault",
        )
        assert v.vault_type == "obsidian"

        # Invalid type
        with pytest.raises(VaultConfigError) as exc:
            VaultConfig(
                vault_type="other",
                base_dir="/tmp/vault",
                wks_dir=".wks",
                update_frequency_seconds=10.0,
                database="wks.vault",
            )
        assert "vault.type must be 'obsidian'" in str(exc.value)

        # Invalid database format
        with pytest.raises(VaultConfigError) as exc:
            VaultConfig(
                vault_type="obsidian",
                base_dir="/tmp/vault",
                wks_dir=".wks",
                update_frequency_seconds=10.0,
                database="wks",
            )
        assert "format 'database.collection'" in str(exc.value)

    def test_vault_config_from_dict(self):
        # Valid
        cfg = {"vault": {"base_dir": "/tmp/vault", "database": "db.coll"}}
        vc = VaultConfig.from_config_dict(cfg)
        assert vc.base_dir == "/tmp/vault"
        assert vc.database == "db.coll"
        assert vc.vault_type == "obsidian"  # default

        # Missing vault section
        with pytest.raises(VaultConfigError):
            VaultConfig.from_config_dict({})
