"""Tests for config module."""

from pathlib import Path

import pytest

from vllmlx.config import BackendConfig, Config, DaemonConfig, ModelsConfig


class TestDaemonConfig:
    """Tests for DaemonConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = DaemonConfig()
        assert config.port == 11434
        assert config.host == "127.0.0.1"
        assert config.idle_timeout == 600
        assert config.log_level == "info"
        assert config.preload_default_model is False
        assert config.pin_default_model is False
        assert config.max_loaded_models == 3
        assert config.min_available_memory_gb == 2.0

    def test_custom_values(self):
        """Test custom values are accepted."""
        config = DaemonConfig(
            port=8080,
            host="0.0.0.0",
            idle_timeout=120,
            log_level="debug",
            preload_default_model=True,
            pin_default_model=True,
            max_loaded_models=5,
            min_available_memory_gb=4.0,
        )
        assert config.port == 8080
        assert config.host == "0.0.0.0"
        assert config.idle_timeout == 120
        assert config.log_level == "debug"
        assert config.preload_default_model is True
        assert config.pin_default_model is True
        assert config.max_loaded_models == 5
        assert config.min_available_memory_gb == 4.0


class TestModelsConfig:
    """Tests for ModelsConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = ModelsConfig()
        assert config.default == ""

    def test_custom_values(self):
        """Test custom values are accepted."""
        config = ModelsConfig(default="qwen2-vl-7b")
        assert config.default == "qwen2-vl-7b"


class TestBackendConfig:
    """Tests for BackendConfig."""

    def test_default_values(self):
        config = BackendConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 11435
        assert config.continuous_batching is False
        assert config.max_tokens == 32768

    def test_custom_values(self):
        config = BackendConfig(
            port=19000,
            continuous_batching=True,
            max_tokens=4096,
            reasoning_parser="qwen3",
        )
        assert config.port == 19000
        assert config.continuous_batching is True
        assert config.max_tokens == 4096
        assert config.reasoning_parser == "qwen3"


class TestConfig:
    """Tests for Config."""

    def test_default_config(self):
        """Test default config has expected values."""
        config = Config()
        assert config.daemon.port == 11434
        assert config.backend.port == 11435
        assert config.models.default == ""
        assert config.aliases == {}

    def test_config_path(self, tmp_path, monkeypatch):
        """Test config path is in home directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = Config.path()
        assert path == tmp_path / ".vllmlx" / "config.toml"

    def test_load_default_when_no_file(self, tmp_path, monkeypatch):
        """Test loading returns default config when file doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config.load()
        assert config.daemon.port == 11434
        assert config.models.default == ""
        assert config.aliases == {}

    def test_save_creates_directory(self, tmp_path, monkeypatch):
        """Test save creates directory if needed."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config()
        config.save()
        assert (tmp_path / ".vllmlx").exists()
        assert (tmp_path / ".vllmlx" / "config.toml").exists()

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """Test config can be saved and loaded."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create config with custom values
        original = Config(
            daemon=DaemonConfig(port=8080, idle_timeout=120),
            models=ModelsConfig(default="qwen2-vl-7b"),
            aliases={"my-model": "some-org/some-model-4bit"},
        )
        original.save()

        # Load and verify
        loaded = Config.load()
        assert loaded.daemon.port == 8080
        assert loaded.daemon.idle_timeout == 120
        assert loaded.models.default == "qwen2-vl-7b"
        assert loaded.aliases == {"my-model": "some-org/some-model-4bit"}

    def test_set_nested_value(self, tmp_path, monkeypatch):
        """Test setting nested config values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config()

        # Test setting nested daemon value
        config.set("daemon.port", 8080)
        assert config.daemon.port == 8080

        config.set("daemon.idle_timeout", 120)
        assert config.daemon.idle_timeout == 120

        config.set("daemon.preload_default_model", "true")
        assert config.daemon.preload_default_model is True

        config.set("daemon.pin_default_model", "true")
        assert config.daemon.pin_default_model is True

        config.set("daemon.max_loaded_models", "4")
        assert config.daemon.max_loaded_models == 4

        config.set("daemon.min_available_memory_gb", "3.5")
        assert config.daemon.min_available_memory_gb == 3.5

        config.set("models.default", "qwen2-vl-7b")
        assert config.models.default == "qwen2-vl-7b"

        config.set("backend.continuous_batching", "true")
        assert config.backend.continuous_batching is True

        config.set("backend.cache_memory_mb", "1024")
        assert config.backend.cache_memory_mb == 1024

    def test_set_alias_value(self, tmp_path, monkeypatch):
        """Test setting alias config values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config()

        config.set("aliases.my-model", "some-org/some-model-4bit")
        assert config.aliases["my-model"] == "some-org/some-model-4bit"

    def test_set_invalid_key_raises(self, tmp_path, monkeypatch):
        """Test setting invalid key raises error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config()

        with pytest.raises(KeyError):
            config.set("invalid.key", "value")

    def test_get_nested_value(self, tmp_path, monkeypatch):
        """Test getting nested config values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = Config(
            daemon=DaemonConfig(port=8080),
            aliases={"my-model": "some-org/some-model-4bit"},
        )

        assert config.get("daemon.port") == 8080
        assert config.get("aliases.my-model") == "some-org/some-model-4bit"
