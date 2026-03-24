"""Tests for `vllmlx search` command."""

from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from vllmlx.cli.main import cli
from vllmlx.models.catalog import CatalogEntry


def _sample_entries() -> list[CatalogEntry]:
    return [
        CatalogEntry(
            repo_id="mlx-community/Qwen3-VL-8B-Instruct-4bit",
            alias="qwen3-vl-8b-instruct-4bit",
            description="Vision model for multimodal chat.",
            model_type="vision",
            release_date="2026-01-01",
            size_bytes=2_147_483_648,
            updated_at="2026-01-02T00:00:00Z",
        ),
        CatalogEntry(
            repo_id="mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
            alias="qwen3-embedding-4b-4bit-dwq",
            description="Embedding model for retrieval.",
            model_type="embedding",
            release_date="2026-01-10",
            size_bytes=1_073_741_824,
            updated_at="2026-01-12T00:00:00Z",
        ),
    ]


def test_search_command_lists_results():
    runner = CliRunner()
    with patch("vllmlx.cli.search.search_catalog", return_value=_sample_entries()):
        result = runner.invoke(cli, ["search", "qwen"])

    assert result.exit_code == 0
    assert "qwen3-vl-8b-instruct-4bit" in result.output
    assert "qwen3-embedding-4b-4bit-dwq" in result.output


def test_search_command_supports_type_filter():
    runner = CliRunner()

    def _fake_search_catalog(query: str, *, limit: int, model_type: str | None = None):
        entries = _sample_entries()
        if model_type:
            entries = [entry for entry in entries if entry.model_type == model_type]
        return entries[:limit]

    with patch("vllmlx.cli.search.search_catalog", side_effect=_fake_search_catalog):
        result = runner.invoke(cli, ["search", "qwen", "--type", "embedding"])

    assert result.exit_code == 0
    assert "qwen3-embedding-4b-4bit-dwq" in result.output
    assert "qwen3-vl-8b-instruct-4bit" not in result.output


def test_search_command_passes_type_filter_to_catalog_search():
    runner = CliRunner()
    with patch("vllmlx.cli.search.search_catalog", return_value=_sample_entries()) as mock_search:
        result = runner.invoke(cli, ["search", "qwen", "--type", "embedding"])

    assert result.exit_code == 0
    mock_search.assert_called_once_with("qwen", limit=20, model_type="embedding")


def test_search_command_outputs_json():
    runner = CliRunner()
    with patch("vllmlx.cli.search.search_catalog", return_value=_sample_entries()):
        result = runner.invoke(cli, ["search", "qwen", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["alias"] == "qwen3-vl-8b-instruct-4bit"
    assert payload[0]["repo_id"] == "mlx-community/Qwen3-VL-8B-Instruct-4bit"
    assert payload[0]["size_bytes"] == 2_147_483_648
    assert payload[1]["size_bytes"] == 1_073_741_824


def test_search_command_uses_packaged_size_bytes_by_default():
    runner = CliRunner()
    with patch("vllmlx.cli.search.search_catalog", return_value=_sample_entries()):
        result = runner.invoke(cli, ["search", "qwen", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["size_bytes"] == 2_147_483_648
    assert payload[1]["size_bytes"] == 1_073_741_824


def test_search_command_shows_no_results_message():
    runner = CliRunner()
    with patch("vllmlx.cli.search.search_catalog", return_value=[]):
        result = runner.invoke(cli, ["search", "nope"])

    assert result.exit_code == 0
    assert "No models found" in result.output
