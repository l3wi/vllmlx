"""Tests for the mlx-community catalog refresh script."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from scripts.update_mlx_community_catalog import _extract_size_bytes


def test_extract_size_bytes_sums_all_repo_file_sizes():
    model = SimpleNamespace(id="mlx-community/test-model")

    sibling_1 = SimpleNamespace(rfilename="model-00001-of-00002.safetensors", size=100)
    sibling_2 = SimpleNamespace(rfilename="model-00002-of-00002.safetensors", size=250)
    sibling_3 = SimpleNamespace(rfilename="config.json", size=50)
    sibling_4 = SimpleNamespace(rfilename="README.md", size=None)

    api = MagicMock()
    api.model_info.return_value = SimpleNamespace(
        siblings=[sibling_1, sibling_2, sibling_3, sibling_4]
    )

    total = _extract_size_bytes(model, api)

    assert total == 400
    api.model_info.assert_called_once_with("mlx-community/test-model", files_metadata=True)


def test_extract_size_bytes_returns_none_when_no_file_sizes_are_available():
    model = SimpleNamespace(id="mlx-community/test-model")

    api = MagicMock()
    api.model_info.return_value = SimpleNamespace(
        siblings=[SimpleNamespace(rfilename="README.md", size=None)]
    )

    assert _extract_size_bytes(model, api) is None
