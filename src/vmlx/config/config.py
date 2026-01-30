"""Configuration management for vmlx."""

from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    port: int = 11434
    host: str = "127.0.0.1"
    idle_timeout: int = 60
    log_level: str = "info"


class ModelsConfig(BaseModel):
    """Models configuration."""

    default: str = ""


class Config(BaseModel):
    """Main vmlx configuration."""

    daemon: DaemonConfig = DaemonConfig()
    models: ModelsConfig = ModelsConfig()
    aliases: dict[str, str] = {}

    @classmethod
    def path(cls) -> Path:
        """Get the path to the config file."""
        return Path.home() / ".vmlx" / "config.toml"

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
        with open(path, "w") as f:
            toml.dump(self.model_dump(), f)

    def set(self, key: str, value: Any) -> None:
        """Set a nested config value.

        Args:
            key: Dot-separated key (e.g., 'daemon.port', 'aliases.my-model')
            value: Value to set

        Raises:
            KeyError: If key is invalid
        """
        parts = key.split(".")
        if len(parts) < 2:
            raise KeyError(f"Invalid key: {key}")

        section = parts[0]
        subkey = ".".join(parts[1:])

        if section == "daemon":
            if hasattr(self.daemon, subkey):
                # Convert value to appropriate type
                field_type = type(getattr(self.daemon, subkey))
                setattr(self.daemon, subkey, field_type(value))
            else:
                raise KeyError(f"Invalid daemon key: {subkey}")
        elif section == "models":
            if hasattr(self.models, subkey):
                field_type = type(getattr(self.models, subkey))
                setattr(self.models, subkey, field_type(value))
            else:
                raise KeyError(f"Invalid models key: {subkey}")
        elif section == "aliases":
            # For aliases, subkey is the alias name
            self.aliases[subkey] = str(value)
        else:
            raise KeyError(f"Invalid section: {section}")

    def get(self, key: str) -> Any:
        """Get a nested config value.

        Args:
            key: Dot-separated key (e.g., 'daemon.port', 'aliases.my-model')

        Returns:
            The config value

        Raises:
            KeyError: If key is invalid
        """
        parts = key.split(".")
        if len(parts) < 2:
            raise KeyError(f"Invalid key: {key}")

        section = parts[0]
        subkey = ".".join(parts[1:])

        if section == "daemon":
            if hasattr(self.daemon, subkey):
                return getattr(self.daemon, subkey)
            else:
                raise KeyError(f"Invalid daemon key: {subkey}")
        elif section == "models":
            if hasattr(self.models, subkey):
                return getattr(self.models, subkey)
            else:
                raise KeyError(f"Invalid models key: {subkey}")
        elif section == "aliases":
            return self.aliases.get(subkey)
        else:
            raise KeyError(f"Invalid section: {section}")
