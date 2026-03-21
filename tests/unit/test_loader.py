"""Tests for model loader download behavior."""

from __future__ import annotations


def test_download_uses_files_metadata_and_resume_download(monkeypatch):
    """Use files metadata for total size and resume partial downloads."""
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
    assert calls[-1]["resume_download"] is True
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


def test_verify_complete_resumes_when_cached_snapshot_is_incomplete(monkeypatch):
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
    assert calls[1]["resume_download"] is True
