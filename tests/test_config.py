"""Tests for configuration loading, including secret_key generation and persistence."""

import tomllib

from config import Config, load_config, _write_config


class TestSecretKey:
    def test_default_config_generates_secret_key(self):
        config = Config.default()
        assert config.secret_key
        assert len(config.secret_key) == 64  # secrets.token_hex(32) → 64 hex chars

    def test_two_default_configs_have_different_keys(self):
        c1 = Config.default()
        c2 = Config.default()
        assert c1.secret_key != c2.secret_key

    def test_load_config_generates_key_when_absent(self, tmp_path, monkeypatch):
        config_path = tmp_path / "necker.toml"
        monkeypatch.setattr("config.get_config_path", lambda: config_path)

        config = load_config()
        assert config.secret_key
        assert len(config.secret_key) == 64

    def test_load_config_persists_generated_key(self, tmp_path, monkeypatch):
        config_path = tmp_path / "necker.toml"
        monkeypatch.setattr("config.get_config_path", lambda: config_path)

        config = load_config()

        # Read the written TOML and verify secret_key is present
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["web"]["secret_key"] == config.secret_key

    def test_load_config_reuses_existing_key(self, tmp_path, monkeypatch):
        config_path = tmp_path / "necker.toml"
        monkeypatch.setattr("config.get_config_path", lambda: config_path)

        # First load generates and persists
        config1 = load_config()
        key1 = config1.secret_key

        # Second load should reuse the persisted key
        config2 = load_config()
        assert config2.secret_key == key1

    def test_write_config_includes_secret_key(self, tmp_path, monkeypatch):
        config_path = tmp_path / "necker.toml"
        monkeypatch.setattr("config.get_config_path", lambda: config_path)

        config = Config.default()
        config.secret_key = "my-test-secret-key"
        _write_config(config)

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["web"]["secret_key"] == "my-test-secret-key"
