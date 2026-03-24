"""Tests for `vllmlx ls` command."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from click.testing import CliRunner

from vllmlx.cli.ls import ls
from vllmlx.models.registry import ModelInfo


def _models() -> list[ModelInfo]:
    return [
        ModelInfo(
            name="mlx-community/Qwen3-VL-8B-Instruct-4bit",
            hf_path="mlx-community/Qwen3-VL-8B-Instruct-4bit",
            size_bytes=2_000_000_000,
            last_modified=datetime(2026, 3, 1, 10, 0, 0),
        ),
        ModelInfo(
            name="mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
            hf_path="mlx-community/Qwen3-Embedding-4B-4bit-DWQ",
            size_bytes=1_000_000_000,
            last_modified=datetime(2026, 3, 2, 10, 0, 0),
        ),
    ]


def test_ls_help_contains_type_option():
    runner = CliRunner()
    result = runner.invoke(ls, ["--help"])
    assert result.exit_code == 0
    assert "--type" in result.output


def test_ls_type_filter_embedding():
    runner = CliRunner()

    type_map = {
        "mlx-community/Qwen3-VL-8B-Instruct-4bit": "vision",
        "mlx-community/Qwen3-Embedding-4B-4bit-DWQ": "embedding",
    }
    alias_map = {
        "mlx-community/Qwen3-VL-8B-Instruct-4bit": "qwen3-vl-8b-instruct-4bit",
        "mlx-community/Qwen3-Embedding-4B-4bit-DWQ": "qwen3-embedding-4b-4bit-dwq",
    }

    with (
        patch("vllmlx.cli.ls.list_models", return_value=_models()),
        patch("vllmlx.cli.ls.get_model_type_for_path", side_effect=type_map.get),
        patch("vllmlx.cli.ls.get_alias_for_path", side_effect=alias_map.get),
    ):
        result = runner.invoke(ls, ["--type", "embedding"])

    assert result.exit_code == 0
    assert "qwen3-embedding-4b-4bit-dwq" in result.output
    assert "qwen3-vl-8b-instruct-4bit" not in result.output


def test_ls_type_filter_no_results():
    runner = CliRunner()
    with (
        patch("vllmlx.cli.ls.list_models", return_value=_models()),
        patch("vllmlx.cli.ls.get_model_type_for_path", return_value="vision"),
    ):
        result = runner.invoke(ls, ["--type", "embedding"])

    assert result.exit_code == 0
    assert "No downloaded models found for type" in result.output


def test_ls_shows_local_and_remote_size_when_incomplete():
    runner = CliRunner()
    model = ModelInfo(
        name="mlx-community/Qwen3.5-35B-A3B-6bit",
        hf_path="mlx-community/Qwen3.5-35B-A3B-6bit",
        size_bytes=2_000,
        last_modified=datetime(2026, 3, 2, 10, 0, 0),
    )

    with (
        patch("vllmlx.cli.ls.list_models", return_value=[model]),
        patch("vllmlx.cli.ls.get_model_type_for_path", return_value="vision"),
        patch("vllmlx.cli.ls.get_alias_for_path", return_value="qwen3-5-35b-a3b-6bit"),
        patch("vllmlx.cli.ls.get_catalog_size_for_path", return_value=20_000),
    ):
        result = runner.invoke(ls, [])

    assert result.exit_code == 0
    assert "Detected incomplete downloads" in result.output


def test_ls_uses_packaged_catalog_size_without_live_hub_lookup():
    runner = CliRunner()
    model = ModelInfo(
        name="mlx-community/Qwen3.5-35B-A3B-6bit",
        hf_path="mlx-community/Qwen3.5-35B-A3B-6bit",
        size_bytes=2_000,
        last_modified=datetime(2026, 3, 2, 10, 0, 0),
    )

    with (
        patch("vllmlx.cli.ls.list_models", return_value=[model]),
        patch("vllmlx.cli.ls.get_model_type_for_path", return_value="vision"),
        patch("vllmlx.cli.ls.get_alias_for_path", return_value="qwen3-5-35b-a3b-6bit"),
        patch("vllmlx.cli.ls.get_catalog_size_for_path", return_value=20_000),
    ):
        result = runner.invoke(ls, [])

    assert result.exit_code == 0
    assert "Detected incomplete downloads" in result.output
