"""Tests for model registry module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from vllmlx.models.registry import ModelInfo, delete_model, format_size, list_models


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_model_info_creation(self):
        """Test ModelInfo can be created."""
        model = ModelInfo(
            name="qwen2-vl-7b",
            hf_path="mlx-community/Qwen2-VL-7B-Instruct-4bit",
            size_bytes=4_000_000_000,
            last_modified=datetime(2026, 1, 30, 10, 0, 0),
        )
        assert model.name == "qwen2-vl-7b"
        assert model.hf_path == "mlx-community/Qwen2-VL-7B-Instruct-4bit"
        assert model.size_bytes == 4_000_000_000
        assert model.last_modified == datetime(2026, 1, 30, 10, 0, 0)

    def test_model_info_without_last_modified(self):
        """Test ModelInfo can be created without last_modified."""
        model = ModelInfo(
            name="test-model",
            hf_path="test-org/test-model",
            size_bytes=1_000_000,
            last_modified=None,
        )
        assert model.last_modified is None


class TestFormatSize:
    """Tests for format_size function."""

    def test_format_bytes(self):
        """Test formatting bytes."""
        assert format_size(500) == "500 B"

    def test_format_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(2048) == "2.0 KB"

    def test_format_megabytes(self):
        """Test formatting megabytes."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 100) == "100.0 MB"

    def test_format_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_size(1024 * 1024 * 1024 * 4.5) == "4.5 GB"


class TestListModels:
    """Tests for list_models function."""

    def test_list_models_returns_model_info_list(self):
        """Test list_models returns list of ModelInfo objects."""
        # Create mock cache
        mock_repo = MagicMock()
        mock_repo.repo_id = "mlx-community/Qwen2-VL-7B-Instruct-4bit"
        mock_repo.size_on_disk = 4_000_000_000
        mock_repo.last_modified = datetime(2026, 1, 30, 10, 0, 0)

        mock_cache = MagicMock()
        mock_cache.repos = [mock_repo]

        with patch("vllmlx.models.registry.scan_cache_dir", return_value=mock_cache):
            models = list_models()

        assert len(models) == 1
        assert models[0].hf_path == "mlx-community/Qwen2-VL-7B-Instruct-4bit"
        assert models[0].size_bytes == 4_000_000_000

    def test_list_models_filters_non_mlx(self):
        """Test list_models filters out non-MLX models."""
        # Create mock cache with MLX and non-MLX repos
        mlx_repo = MagicMock()
        mlx_repo.repo_id = "mlx-community/Qwen2-VL-7B-Instruct-4bit"
        mlx_repo.size_on_disk = 4_000_000_000
        mlx_repo.last_modified = datetime(2026, 1, 30, 10, 0, 0)

        non_mlx_repo = MagicMock()
        non_mlx_repo.repo_id = "meta-llama/Llama-2-7b"
        non_mlx_repo.size_on_disk = 13_000_000_000
        non_mlx_repo.last_modified = datetime(2026, 1, 29, 10, 0, 0)

        mock_cache = MagicMock()
        mock_cache.repos = [mlx_repo, non_mlx_repo]

        with patch("vllmlx.models.registry.scan_cache_dir", return_value=mock_cache):
            models = list_models()

        assert len(models) == 1
        assert models[0].hf_path == "mlx-community/Qwen2-VL-7B-Instruct-4bit"

    def test_list_models_empty_cache(self):
        """Test list_models returns empty list for empty cache."""
        mock_cache = MagicMock()
        mock_cache.repos = []

        with patch("vllmlx.models.registry.scan_cache_dir", return_value=mock_cache):
            models = list_models()

        assert models == []


class TestDeleteModel:
    """Tests for delete_model function."""

    def test_delete_model_success(self):
        """Test delete_model returns True on success."""
        # Create mock repo
        mock_revision = MagicMock()
        mock_revision.commit_hash = "abc123"

        mock_repo = MagicMock()
        mock_repo.repo_id = "mlx-community/Qwen2-VL-7B-Instruct-4bit"
        mock_repo.revisions = [mock_revision]

        # Create mock cache
        mock_strategy = MagicMock()
        mock_cache = MagicMock()
        mock_cache.repos = [mock_repo]
        mock_cache.delete_revisions.return_value = mock_strategy

        with patch("vllmlx.models.registry.scan_cache_dir", return_value=mock_cache):
            result = delete_model("mlx-community/Qwen2-VL-7B-Instruct-4bit")

        assert result is True
        mock_cache.delete_revisions.assert_called_once_with("abc123")
        mock_strategy.execute.assert_called_once()

    def test_delete_model_not_found(self):
        """Test delete_model returns False when model not found."""
        mock_cache = MagicMock()
        mock_cache.repos = []

        with patch("vllmlx.models.registry.scan_cache_dir", return_value=mock_cache):
            result = delete_model("non-existent/model")

        assert result is False
