"""Packaged mlx-community model catalog helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class CatalogEntry:
    """Single model record in the packaged mlx-community catalog."""

    repo_id: str
    alias: str
    description: str
    model_type: str
    release_date: str
    size_bytes: int | None
    updated_at: str


def catalog_path() -> Path:
    """Return packaged catalog path."""
    return Path(__file__).parent / "data" / "mlx_community_models.json"


def _entry_from_payload(item: dict[str, object]) -> CatalogEntry:
    return CatalogEntry(
        repo_id=str(item.get("repo_id", "")),
        alias=str(item.get("alias", "")),
        description=str(item.get("description", "")),
        model_type=str(item.get("model_type", "")),
        release_date=str(item.get("release_date", "")),
        size_bytes=(int(item["size_bytes"]) if isinstance(item.get("size_bytes"), int) else None),
        updated_at=str(item.get("updated_at", "")),
    )


def load_catalog(path: Path | None = None) -> list[CatalogEntry]:
    """Load catalog entries from JSON payload."""
    target = path or catalog_path()
    if not target.exists():
        return []

    payload = json.loads(target.read_text(encoding="utf-8"))
    models = payload.get("models")
    if not isinstance(models, list):
        return []

    entries = []
    for item in models:
        if not isinstance(item, dict):
            continue
        entry = _entry_from_payload(item)
        if not entry.repo_id or not entry.alias:
            continue
        entries.append(entry)
    return entries


@lru_cache(maxsize=1)
def load_catalog_cached() -> tuple[CatalogEntry, ...]:
    """Load catalog once per process."""
    return tuple(load_catalog())


def build_alias_index(entries: list[CatalogEntry] | tuple[CatalogEntry, ...]) -> dict[str, str]:
    """Build case-insensitive alias -> repo_id mapping."""
    index: dict[str, str] = {}
    for entry in entries:
        key = entry.alias.strip().lower()
        if not key:
            continue
        index[key] = entry.repo_id
    return index


@lru_cache(maxsize=4096)
def get_repo_total_size_bytes(repo_id: str) -> int | None:
    """Return total bytes across all files in a HuggingFace model repo."""
    from huggingface_hub import HfApi

    api = HfApi()
    info = api.model_info(repo_id, files_metadata=True)
    sizes = [
        sibling.size
        for sibling in (info.siblings or [])
        if isinstance(getattr(sibling, "size", None), int)
    ]
    if not sizes:
        return None
    return int(sum(sizes))


def search_catalog(
    query: str,
    *,
    entries: list[CatalogEntry] | tuple[CatalogEntry, ...] | None = None,
    limit: int = 20,
    model_type: str | None = None,
) -> list[CatalogEntry]:
    """Search entries by alias, repo_id, type, and description."""
    pool = list(entries) if entries is not None else list(load_catalog_cached())
    if model_type:
        needle = model_type.strip().lower()
        pool = [entry for entry in pool if entry.model_type.lower() == needle]

    term = query.strip().lower()
    if not term:
        return pool[:limit]

    scored: list[tuple[int, CatalogEntry]] = []
    for entry in pool:
        alias = entry.alias.lower()
        repo_id = entry.repo_id.lower()
        model_type = entry.model_type.lower()
        description = entry.description.lower()

        score = 0
        if term == alias:
            score += 120
        if term in alias:
            score += 80
        if term in repo_id:
            score += 60
        if term == model_type:
            score += 40
        elif term in model_type:
            score += 25
        if term in description:
            score += 15

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: (-item[0], item[1].alias))
    return [entry for _, entry in scored[:limit]]
