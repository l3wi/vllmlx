# Task: Core Infrastructure

**Phase**: 1  
**Branch**: `feat/vmlx-phase-1`  
**Plan**: [docs/plans/vmlx.md](../plans/vmlx.md)  
**Spec**: [docs/specs/vmlx-spec.md](../specs/vmlx-spec.md)  
**Status**: pending

---

## Objective

Set up project foundation with config system, model alias registry, and basic CLI commands for model management (pull, ls, rm).

---

## Acceptance Criteria

- [ ] Project installable via `pip install -e .`
- [ ] `vmlx --help` shows available commands
- [ ] `vmlx pull qwen2-vl-2b` downloads model from HuggingFace
- [ ] `vmlx pull mlx-community/Some-Model` works with full HF paths
- [ ] `vmlx ls` lists downloaded models with name and size
- [ ] `vmlx rm qwen2-vl-2b` removes model from HF cache
- [ ] `vmlx config` displays current configuration
- [ ] `vmlx config set daemon.idle_timeout 120` updates config
- [ ] Config persists to `~/.vmlx/config.toml`
- [ ] Builtin aliases resolve correctly
- [ ] Custom aliases from config override builtins
- [ ] All unit tests pass
- [ ] Lint clean (ruff)

---

## Files to Create

| File | Description |
|------|-------------|
| `pyproject.toml` | Package config with dependencies: click, pydantic, toml, huggingface_hub, rich |
| `src/vmlx/__init__.py` | Package init with version |
| `src/vmlx/__main__.py` | Entry point for `python -m vmlx` |
| `src/vmlx/config/__init__.py` | Config module init |
| `src/vmlx/config/config.py` | Config dataclass, load/save, defaults |
| `src/vmlx/models/__init__.py` | Models module init |
| `src/vmlx/models/aliases.py` | BUILTIN_ALIASES dict, resolve function |
| `src/vmlx/models/registry.py` | HF cache scanning, model info extraction |
| `src/vmlx/cli/__init__.py` | CLI module init |
| `src/vmlx/cli/main.py` | Click group, command registration |
| `src/vmlx/cli/pull.py` | `vmlx pull` command |
| `src/vmlx/cli/ls.py` | `vmlx ls` command |
| `src/vmlx/cli/rm.py` | `vmlx rm` command |
| `src/vmlx/cli/config_cmd.py` | `vmlx config` command |
| `tests/__init__.py` | Tests package |
| `tests/unit/__init__.py` | Unit tests package |
| `tests/unit/test_config.py` | Config load/save tests |
| `tests/unit/test_aliases.py` | Alias resolution tests |
| `tests/unit/test_registry.py` | Model registry tests |

---

## Implementation Notes

### Project Structure

```
vmlx/
├── pyproject.toml
├── src/
│   └── vmlx/
│       ├── __init__.py          # __version__ = "0.1.0"
│       ├── __main__.py          # from vmlx.cli.main import cli; cli()
│       ├── config/
│       │   ├── __init__.py
│       │   └── config.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── aliases.py
│       │   └── registry.py
│       └── cli/
│           ├── __init__.py
│           ├── main.py
│           ├── pull.py
│           ├── ls.py
│           ├── rm.py
│           └── config_cmd.py
└── tests/
```

### pyproject.toml

```toml
[project]
name = "vmlx"
version = "0.1.0"
description = "Ollama-style CLI for MLX-VLM"
requires-python = ">=3.12"
dependencies = [
    "click>=8.0",
    "pydantic>=2.0",
    "toml>=0.10",
    "huggingface_hub>=0.20",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]

[project.scripts]
vmlx = "vmlx.cli.main:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vmlx"]
```

### Config Schema (config.py)

```python
from pydantic import BaseModel
from pathlib import Path
import toml

class DaemonConfig(BaseModel):
    port: int = 11434
    host: str = "127.0.0.1"
    idle_timeout: int = 60
    log_level: str = "info"

class ModelsConfig(BaseModel):
    default: str = ""

class Config(BaseModel):
    daemon: DaemonConfig = DaemonConfig()
    models: ModelsConfig = ModelsConfig()
    aliases: dict[str, str] = {}

    @classmethod
    def path(cls) -> Path:
        return Path.home() / ".vmlx" / "config.toml"

    @classmethod
    def load(cls) -> "Config":
        path = cls.path()
        if path.exists():
            data = toml.load(path)
            return cls(**data)
        return cls()

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            toml.dump(self.model_dump(), f)
```

### Builtin Aliases (aliases.py)

```python
BUILTIN_ALIASES = {
    "qwen2-vl-2b": "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    "qwen2-vl-7b": "mlx-community/Qwen2-VL-7B-Instruct-4bit",
    "qwen2.5-vl-3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
    "qwen2.5-vl-7b": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
    "qwen2.5-vl-32b": "mlx-community/Qwen2.5-VL-32B-Instruct-8bit",
    "qwen2.5-vl-72b": "mlx-community/Qwen2.5-VL-72B-Instruct-4bit",
    "pixtral-12b": "mlx-community/pixtral-12b-4bit",
    "llava-qwen-0.5b": "mlx-community/llava-interleave-qwen-0.5b-bf16",
    "llava-qwen-7b": "mlx-community/llava-interleave-qwen-7b-4bit",
}

def resolve_alias(name: str, custom_aliases: dict[str, str] = None) -> str:
    """Resolve model alias to full HuggingFace path."""
    if custom_aliases and name in custom_aliases:
        return custom_aliases[name]
    if name in BUILTIN_ALIASES:
        return BUILTIN_ALIASES[name]
    # Assume it's already a full path
    return name
```

### Model Registry (registry.py)

```python
from huggingface_hub import scan_cache_dir, snapshot_download
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ModelInfo:
    name: str
    hf_path: str
    size_bytes: int
    last_modified: Optional[datetime]

def list_models() -> list[ModelInfo]:
    """List all downloaded MLX-VLM compatible models."""
    cache = scan_cache_dir()
    models = []
    for repo in cache.repos:
        # Filter for MLX models (heuristic: check for mlx in path or config)
        if "mlx" in repo.repo_id.lower():
            models.append(ModelInfo(
                name=repo.repo_id,
                hf_path=repo.repo_id,
                size_bytes=repo.size_on_disk,
                last_modified=repo.last_modified,
            ))
    return models

def download_model(hf_path: str) -> None:
    """Download model from HuggingFace."""
    snapshot_download(hf_path)

def delete_model(hf_path: str) -> bool:
    """Delete model from cache. Returns True if deleted."""
    cache = scan_cache_dir()
    for repo in cache.repos:
        if repo.repo_id == hf_path:
            delete_strategy = cache.delete_revisions(
                *[rev.commit_hash for rev in repo.revisions]
            )
            delete_strategy.execute()
            return True
    return False
```

### CLI Commands

Use `rich` for pretty output:
- `vmlx ls`: Table with model name, size (human readable), last used
- `vmlx pull`: Progress bar during download
- `vmlx rm`: Confirmation prompt, success message

---

## Testing Requirements

### Unit Tests

**test_config.py:**
- Load default config when file doesn't exist
- Load config from existing file
- Save config creates directory if needed
- Config set updates nested values

**test_aliases.py:**
- Resolve builtin alias returns full path
- Resolve custom alias overrides builtin
- Resolve unknown returns input unchanged
- Full HF path passes through

**test_registry.py:**
- List models returns ModelInfo objects
- Size formatting is human readable
- Delete model removes from cache (mock)

---

## Agent Instructions

1. Read the full spec at `docs/specs/vmlx-spec.md` for context
2. Create project structure first (`pyproject.toml`, directories)
3. Implement config module with tests
4. Implement aliases module with tests
5. Implement registry module with tests
6. Implement CLI commands
7. Run `ruff check` and fix any lint issues
8. Run `pytest` and ensure all tests pass
9. Test manually: `pip install -e . && vmlx --help`
10. Commit with descriptive messages using `wt commit`
