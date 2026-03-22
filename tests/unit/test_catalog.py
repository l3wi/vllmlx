"""Tests for packaged mlx-community catalog helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from vllmlx.models.catalog import (
    CatalogEntry,
    build_alias_index,
    get_repo_total_size_bytes,
    load_catalog,
    search_catalog,
)


def _write_catalog(path: Path, items: list[dict[str, object]]) -> None:
    payload = {
        "source": "huggingface",
        "org": "mlx-community",
        "generated_at": "2026-03-22T00:00:00Z",
        "models": items,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_catalog_from_custom_path(tmp_path: Path):
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(
        catalog_path,
        [
            {
                "repo_id": "mlx-community/Qwen3-8B-4bit",
                "alias": "qwen3-8b-4bit",
                "description": "Qwen 3 8B quantized for MLX.",
                "model_type": "text",
                "release_date": "2026-03-01",
                "size_bytes": 1234,
                "updated_at": "2026-03-02T12:00:00Z",
            }
        ],
    )

    entries = load_catalog(catalog_path)
    assert entries == [
        CatalogEntry(
            repo_id="mlx-community/Qwen3-8B-4bit",
            alias="qwen3-8b-4bit",
            description="Qwen 3 8B quantized for MLX.",
            model_type="text",
            release_date="2026-03-01",
            size_bytes=1234,
            updated_at="2026-03-02T12:00:00Z",
        )
    ]


def test_build_alias_index_is_case_insensitive():
    entries = [
        CatalogEntry(
            repo_id="mlx-community/Qwen3-8B-4bit",
            alias="QWEN3:8B",
            description="desc",
            model_type="text",
            release_date="2026-03-01",
            size_bytes=10,
            updated_at="2026-03-02T12:00:00Z",
        )
    ]

    aliases = build_alias_index(entries)
    assert aliases["qwen3:8b"] == "mlx-community/Qwen3-8B-4bit"


def test_search_catalog_matches_alias_type_and_description():
    entries = [
        CatalogEntry(
            repo_id="mlx-community/Qwen3-VL-8B-Instruct-4bit",
            alias="qwen3-vl:8b",
            description="Vision-language model for multimodal chat.",
            model_type="vision",
            release_date="2026-01-01",
            size_bytes=100,
            updated_at="2026-01-02T00:00:00Z",
        ),
        CatalogEntry(
            repo_id="mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
            alias="qwen3-embedding:4b",
            description="Embedding model for retrieval.",
            model_type="embedding",
            release_date="2026-01-01",
            size_bytes=100,
            updated_at="2026-01-02T00:00:00Z",
        ),
    ]

    results = search_catalog("embedding", entries=entries)
    assert results[0].alias == "qwen3-embedding:4b"

    results = search_catalog("vision", entries=entries)
    assert results[0].alias == "qwen3-vl:8b"


def test_search_catalog_filters_type_before_limit():
    entries = [
        CatalogEntry(
            repo_id="mlx-community/Qwen-Text-Model",
            alias="qwen-a",
            description="Text model.",
            model_type="text",
            release_date="2026-01-01",
            size_bytes=100,
            updated_at="2026-01-02T00:00:00Z",
        ),
        CatalogEntry(
            repo_id="mlx-community/Qwen-Embedding-Model",
            alias="qwen-z",
            description="Embedding model.",
            model_type="embedding",
            release_date="2026-01-01",
            size_bytes=100,
            updated_at="2026-01-02T00:00:00Z",
        ),
    ]

    results = search_catalog("qwen", entries=entries, model_type="embedding", limit=1)
    assert len(results) == 1
    assert results[0].alias == "qwen-z"


def test_get_repo_total_size_bytes_sums_all_file_sizes():
    mock_sibling_1 = MagicMock()
    mock_sibling_1.size = 100
    mock_sibling_2 = MagicMock()
    mock_sibling_2.size = 250
    mock_sibling_3 = MagicMock()
    mock_sibling_3.size = None

    mock_info = MagicMock()
    mock_info.siblings = [mock_sibling_1, mock_sibling_2, mock_sibling_3]

    with patch("huggingface_hub.HfApi") as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.model_info.return_value = mock_info

        # Clear cache for deterministic test behavior.
        get_repo_total_size_bytes.cache_clear()
        total = get_repo_total_size_bytes("mlx-community/test-model")

    assert total == 350
