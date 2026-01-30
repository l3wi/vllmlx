"""Model registry for managing HuggingFace cache."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from huggingface_hub import scan_cache_dir, snapshot_download


@dataclass
class ModelInfo:
    """Information about a downloaded model."""

    name: str
    hf_path: str
    size_bytes: int
    last_modified: Optional[datetime]


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human readable size string (e.g., '4.5 GB')
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def list_models() -> list[ModelInfo]:
    """List all downloaded MLX-VLM compatible models.

    Returns:
        List of ModelInfo objects for downloaded models
    """
    cache = scan_cache_dir()
    models = []

    for repo in cache.repos:
        # Filter for MLX models (heuristic: check for mlx in path)
        if "mlx" in repo.repo_id.lower():
            # Convert timestamp to datetime if needed
            last_mod = repo.last_modified
            if isinstance(last_mod, (int, float)):
                last_mod = datetime.fromtimestamp(last_mod)
            
            models.append(
                ModelInfo(
                    name=repo.repo_id,
                    hf_path=repo.repo_id,
                    size_bytes=repo.size_on_disk,
                    last_modified=last_mod,
                )
            )

    return models


def download_model(hf_path: str) -> None:
    """Download model from HuggingFace.

    Args:
        hf_path: Full HuggingFace path (e.g., 'mlx-community/Qwen2-VL-7B-Instruct-4bit')
    """
    snapshot_download(hf_path)


def delete_model(hf_path: str) -> bool:
    """Delete model from HuggingFace cache.

    Args:
        hf_path: Full HuggingFace path

    Returns:
        True if model was deleted, False if not found
    """
    cache = scan_cache_dir()

    for repo in cache.repos:
        if repo.repo_id == hf_path:
            # Get all revision commit hashes
            commit_hashes = [rev.commit_hash for rev in repo.revisions]
            delete_strategy = cache.delete_revisions(*commit_hashes)
            delete_strategy.execute()
            return True

    return False
