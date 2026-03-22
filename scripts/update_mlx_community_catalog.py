"""Regenerate packaged mlx-community model catalog from Hugging Face."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    REPO_ROOT / "src" / "vllmlx" / "models" / "data" / "mlx_community_models.json"
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "model"


def _infer_model_type(pipeline_tag: str | None, tags: list[str], repo_name: str) -> str:
    text = " ".join([pipeline_tag or "", *tags, repo_name]).lower()

    if "embedding" in text or "feature-extraction" in text:
        return "embedding"
    if "image" in text or "vision" in text or "-vl" in text:
        return "vision"
    if "speech" in text or "audio" in text or "text-to-speech" in text:
        return "audio"
    return "text"


def _format_description(repo_name: str) -> str:
    cleaned = re.sub(r"[-_]+", " ", repo_name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return ""


def _to_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return ""


def _extract_size_bytes(model: Any) -> int | None:
    # list_models metadata does not expose exact per-file sizes. Real total size
    # is resolved at query time via model_info(..., files_metadata=True).
    _ = model
    return None


def _build_records() -> list[dict[str, Any]]:
    api = HfApi()
    source_models = list(
        api.list_models(
            author="mlx-community",
            expand=[
                "createdAt",
                "lastModified",
                "pipeline_tag",
                "tags",
                "safetensors",
                "gguf",
            ],
        )
    )
    source_models.sort(key=lambda model: model.id.lower())

    used_aliases: dict[str, int] = {}
    records: list[dict[str, Any]] = []

    for model in source_models:
        repo_id = model.id
        _, repo_name = repo_id.split("/", 1)
        base_alias = _slugify(repo_name)
        next_index = used_aliases.get(base_alias, 0) + 1
        used_aliases[base_alias] = next_index
        alias = base_alias if next_index == 1 else f"{base_alias}-{next_index}"

        tags = list(getattr(model, "tags", []) or [])
        model_type = _infer_model_type(
            pipeline_tag=getattr(model, "pipeline_tag", None),
            tags=tags,
            repo_name=repo_name,
        )
        records.append(
            {
                "repo_id": repo_id,
                "alias": alias,
                "description": _format_description(repo_name),
                "model_type": model_type,
                "release_date": _to_date(getattr(model, "created_at", None)),
                "size_bytes": _extract_size_bytes(model),
                "updated_at": _to_iso(getattr(model, "last_modified", None)),
            }
        )

    return records


def main() -> None:
    models = _build_records()
    payload = {
        "source": "huggingface",
        "org": "mlx-community",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "count": len(models),
        "models": models,
    }
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(models)} models to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
