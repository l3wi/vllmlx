"""Tests for `vllmlx pull` confirmation behavior."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from vllmlx.cli.pull import pull


def test_pull_prompts_for_non_mlx_namespace_and_downloads_on_confirm():
    runner = CliRunner()

    with (
        patch("vllmlx.cli.pull.Config.load") as mock_load,
        patch("vllmlx.cli.pull.ensure_model_downloaded") as mock_download,
    ):
        mock_load.return_value.aliases = {}
        mock_download.return_value = ("/tmp/model", False)

        result = runner.invoke(pull, ["Qwen/Qwen3-Embedding-4B"], input="y\n")

    assert result.exit_code == 0
    assert "outside mlx-community" in result.output
    mock_download.assert_called_once_with(
        "Qwen/Qwen3-Embedding-4B",
        verify_complete=True,
    )


def test_pull_aborts_for_non_mlx_namespace_when_not_confirmed():
    runner = CliRunner()

    with (
        patch("vllmlx.cli.pull.Config.load") as mock_load,
        patch("vllmlx.cli.pull.ensure_model_downloaded") as mock_download,
    ):
        mock_load.return_value.aliases = {}

        result = runner.invoke(pull, ["Qwen/Qwen3-Embedding-4B"], input="n\n")

    assert result.exit_code != 0
    assert "outside mlx-community" in result.output
    mock_download.assert_not_called()


def test_pull_does_not_prompt_for_mlx_community_namespace():
    runner = CliRunner()

    with (
        patch("vllmlx.cli.pull.Config.load") as mock_load,
        patch("vllmlx.cli.pull.ensure_model_downloaded") as mock_download,
        patch("vllmlx.cli.pull.click.confirm") as mock_confirm,
    ):
        mock_load.return_value.aliases = {}
        mock_download.return_value = ("/tmp/model", False)

        result = runner.invoke(pull, ["mlx-community/Qwen3-8B-4bit"])

    assert result.exit_code == 0
    mock_confirm.assert_not_called()
    mock_download.assert_called_once_with(
        "mlx-community/Qwen3-8B-4bit",
        verify_complete=True,
    )


def test_pull_yes_skips_prompt_for_non_mlx_namespace():
    runner = CliRunner()

    with (
        patch("vllmlx.cli.pull.Config.load") as mock_load,
        patch("vllmlx.cli.pull.ensure_model_downloaded") as mock_download,
        patch("vllmlx.cli.pull.click.confirm") as mock_confirm,
    ):
        mock_load.return_value.aliases = {}
        mock_download.return_value = ("/tmp/model", False)

        result = runner.invoke(pull, ["--yes", "Qwen/Qwen3-Embedding-4B"])

    assert result.exit_code == 0
    mock_confirm.assert_not_called()
    mock_download.assert_called_once_with(
        "Qwen/Qwen3-Embedding-4B",
        verify_complete=True,
    )


def test_pull_does_not_print_alias_resolution_message():
    runner = CliRunner()

    with (
        patch("vllmlx.cli.pull.Config.load") as mock_load,
        patch("vllmlx.cli.pull.ensure_model_downloaded") as mock_download,
    ):
        mock_load.return_value.aliases = {}
        mock_download.return_value = ("/tmp/model", False)

        result = runner.invoke(pull, ["qwen3-8b-4bit"])

    assert result.exit_code == 0
    assert "Resolving" not in result.output
