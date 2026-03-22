"""Tests for model loader download behavior."""

from __future__ import annotations


def test_download_uses_files_metadata_and_snapshot_download(monkeypatch):
    """Use files metadata and HF-native snapshot download path."""
    from vllmlx.models.loader import ensure_model_downloaded

    calls: list[dict] = []
    api_calls: list[dict] = []

    def fake_snapshot_download(model_path, **kwargs):
        calls.append(kwargs)
        if kwargs.get("local_files_only"):
            raise RuntimeError("not cached")
        return "/tmp/mock-model"

    class _FakeApi:
        class _Info:
            siblings = []

        def repo_info(self, model_path, repo_type="model", files_metadata=False):
            api_calls.append(
                {
                    "model_path": model_path,
                    "repo_type": repo_type,
                    "files_metadata": files_metadata,
                }
            )
            return self._Info()

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr("huggingface_hub.HfApi", _FakeApi)

    local_path, was_cached = ensure_model_downloaded("mlx-community/Qwen3-4B-4bit", quiet=False)

    assert local_path == "/tmp/mock-model"
    assert was_cached is False
    assert len(calls) == 2
    assert "resume_download" not in calls[-1]
    assert "tqdm_class" not in calls[-1]
    assert api_calls[0]["files_metadata"] is True


def test_verify_complete_returns_cached_when_sizes_match(monkeypatch):
    """When live metadata size matches local snapshot, treat cache as complete."""
    from vllmlx.models.loader import ensure_model_downloaded

    calls: list[dict] = []

    def fake_snapshot_download(model_path, **kwargs):
        calls.append(kwargs)
        return "/tmp/mock-model"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(
        "vllmlx.models.loader._fetch_remote_total_size",
        lambda _model_path: 1000,
    )
    monkeypatch.setattr(
        "vllmlx.models.loader._get_local_snapshot_size",
        lambda _snapshot_path: 1000,
    )

    local_path, was_cached = ensure_model_downloaded(
        "mlx-community/Qwen3-4B-4bit",
        quiet=True,
        verify_complete=True,
    )

    assert local_path == "/tmp/mock-model"
    assert was_cached is True
    assert len(calls) == 1
    assert calls[0]["local_files_only"] is True


def test_verify_complete_redownloads_when_cached_snapshot_is_incomplete(monkeypatch):
    """When cached size is below live size, force resume download."""
    from vllmlx.models.loader import ensure_model_downloaded

    calls: list[dict] = []

    def fake_snapshot_download(model_path, **kwargs):
        calls.append(kwargs)
        return "/tmp/mock-model"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(
        "vllmlx.models.loader._fetch_remote_total_size",
        lambda _model_path: 1000,
    )
    monkeypatch.setattr(
        "vllmlx.models.loader._get_local_snapshot_size",
        lambda _snapshot_path: 100,
    )

    local_path, was_cached = ensure_model_downloaded(
        "mlx-community/Qwen3-4B-4bit",
        quiet=True,
        verify_complete=True,
    )

    assert local_path == "/tmp/mock-model"
    assert was_cached is False
    assert len(calls) == 2
    assert calls[0]["local_files_only"] is True
    assert calls[1].get("local_files_only") is not True


def test_verify_complete_trusts_cached_model_when_remote_size_unavailable(monkeypatch):
    """Offline metadata lookup should not force a redownload of a cached model."""
    from vllmlx.models.loader import ensure_model_downloaded

    calls: list[dict] = []

    def fake_snapshot_download(model_path, **kwargs):
        calls.append(kwargs)
        return "/tmp/mock-model"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    def fail_remote_size(_model_path: str) -> int | None:
        raise OSError("offline")

    monkeypatch.setattr("vllmlx.models.loader._fetch_remote_total_size", fail_remote_size)
    monkeypatch.setattr(
        "vllmlx.models.loader._get_local_snapshot_size",
        lambda _snapshot_path: 100,
    )

    local_path, was_cached = ensure_model_downloaded(
        "mlx-community/Qwen3-4B-4bit",
        quiet=True,
        verify_complete=True,
    )

    assert local_path == "/tmp/mock-model"
    assert was_cached is True
    assert calls == [{"local_files_only": True}]


def test_offline_mode_rejects_uncached_download(monkeypatch):
    """Offline mode should fail fast when a model is not already cached."""
    import pytest

    from vllmlx.models.loader import ensure_model_downloaded

    def fake_snapshot_download(model_path, **kwargs):
        if kwargs.get("local_files_only"):
            raise RuntimeError("not cached")
        raise AssertionError("network download should not run in offline mode")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    with pytest.raises(RuntimeError, match="Offline mode is enabled"):
        ensure_model_downloaded("mlx-community/Qwen3-4B-4bit", quiet=True)


def test_quiet_mode_temporarily_disables_hf_progress_bars(monkeypatch):
    """Quiet mode should disable HF progress bars around active download only."""
    from vllmlx.models.loader import ensure_model_downloaded

    events: list[str] = []

    def fake_snapshot_download(model_path, **kwargs):
        if kwargs.get("local_files_only"):
            raise RuntimeError("not cached")
        events.append("download")
        return "/tmp/mock-model"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(
        "huggingface_hub.utils.are_progress_bars_disabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "huggingface_hub.utils.disable_progress_bars",
        lambda: events.append("disable"),
    )
    monkeypatch.setattr(
        "huggingface_hub.utils.enable_progress_bars",
        lambda: events.append("enable"),
    )

    local_path, was_cached = ensure_model_downloaded(
        "mlx-community/Qwen3-4B-4bit",
        quiet=True,
    )

    assert local_path == "/tmp/mock-model"
    assert was_cached is False
    assert events == ["disable", "download", "enable"]
