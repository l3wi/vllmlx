"""Configuration management for vllmlx."""

import os
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import toml
from pydantic import BaseModel


def get_runtime_home() -> Path:
    """Return the effective runtime home directory."""
    override = os.environ.get("VLLMLX_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home()


def get_state_dir() -> Path:
    """Return the effective vllmlx state directory."""
    override = os.environ.get("VLLMLX_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return get_runtime_home() / ".vllmlx"


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    port: int = 8000
    host: str = "127.0.0.1"
    idle_timeout: int = 600
    log_level: str = "info"
    preload_default_model: bool = False
    pin_default_model: bool = False
    max_loaded_models: int = 3
    min_available_memory_gb: float = 2.0
    health_ttl_seconds: float = 1.0


class BackendConfig(BaseModel):
    """Managed vllm-mlx worker configuration."""

    host: str = "127.0.0.1"
    port: int = 11435
    startup_timeout: int = 600
    stop_timeout: int = 15
    continuous_batching: bool = False
    max_tokens: int = 32768
    stream_interval: int = 1
    max_num_seqs: int = 256
    max_num_batched_tokens: int = 8192
    scheduler_policy: Literal["fcfs", "priority"] = "fcfs"
    prefill_batch_size: int = 8
    completion_batch_size: int = 32
    prefill_step_size: int = 2048
    enable_prefix_cache: bool = True
    prefix_cache_size: int = 100
    cache_memory_mb: int | None = None
    cache_memory_percent: float = 0.20
    no_memory_aware_cache: bool = False
    use_paged_cache: bool = False
    paged_cache_block_size: int = 64
    max_cache_blocks: int = 1000
    chunked_prefill_tokens: int = 0
    mid_prefill_save_interval: int = 8192
    api_key: str = ""
    rate_limit: int = 0
    timeout: float = 300.0
    mcp_config: str = ""
    reasoning_parser: str = ""
    default_temperature: float | None = None
    default_top_p: float | None = None
    embedding_model: str = ""


class ModelsConfig(BaseModel):
    """Models configuration."""

    default: str = ""


class Config(BaseModel):
    """Main vllmlx configuration."""

    daemon: DaemonConfig = DaemonConfig()
    backend: BackendConfig = BackendConfig()
    models: ModelsConfig = ModelsConfig()
    aliases: dict[str, str] = {}

    @classmethod
    def path(cls) -> Path:
        """Get the path to the config file."""
        return get_state_dir() / "config.toml"

    @classmethod
    def load(cls) -> "Config":
        """Load config from file, or return default if not exists."""
        path = cls.path()
        if path.exists():
            data = toml.load(path)
            return cls(**data)
        return cls()

    def save(self) -> None:
        """Save config to file."""
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            toml.dump(self.model_dump(), f)

    @staticmethod
    def _coerce_value(value: Any, annotation: Any) -> Any:
        """Coerce string values from CLI into typed model fields."""
        if not isinstance(value, str):
            return value

        lowered = value.strip().lower()
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is None:
            if annotation is bool:
                return lowered in {"1", "true", "yes", "on"}
            if annotation is int:
                return int(value)
            if annotation is float:
                return float(value)
            return value

        if origin in (list, tuple):
            raise ValueError("List/tuple config values are not supported via CLI")

        if args and type(None) in args:
            non_none = [arg for arg in args if arg is not type(None)]
            if lowered in {"none", "null", ""}:
                return None
            if non_none:
                return Config._coerce_value(value, non_none[0])

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a nested config value."""
        parts = key.split(".")
        if len(parts) < 2:
            raise KeyError(f"Invalid key: {key}")

        section = parts[0]
        subkey = ".".join(parts[1:])

        if section == "aliases":
            self.aliases[subkey] = str(value)
            return

        if section not in {"daemon", "backend", "models"}:
            raise KeyError(f"Invalid section: {section}")

        target = getattr(self, section)
        model_fields = target.__class__.model_fields
        if subkey not in model_fields:
            raise KeyError(f"Invalid {section} key: {subkey}")

        field = model_fields[subkey]
        coerced = self._coerce_value(value, field.annotation)
        setattr(target, subkey, coerced)

    def get(self, key: str) -> Any:
        """Get a nested config value."""
        parts = key.split(".")
        if len(parts) < 2:
            raise KeyError(f"Invalid key: {key}")

        section = parts[0]
        subkey = ".".join(parts[1:])

        if section == "aliases":
            return self.aliases.get(subkey)

        if section not in {"daemon", "backend", "models"}:
            raise KeyError(f"Invalid section: {section}")

        target = getattr(self, section)
        if not hasattr(target, subkey):
            raise KeyError(f"Invalid {section} key: {subkey}")

        return getattr(target, subkey)
