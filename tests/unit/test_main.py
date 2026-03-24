"""Tests for CLI bootstrap environment configuration."""

from __future__ import annotations

import importlib


def test_main_does_not_disable_hf_progress_bars_by_default(monkeypatch):
    """CLI bootstrap should not globally suppress HF download progress bars."""
    monkeypatch.delenv("HF_HUB_DISABLE_PROGRESS_BARS", raising=False)

    import vllmlx.cli.main as main_module

    importlib.reload(main_module)

    assert "HF_HUB_DISABLE_PROGRESS_BARS" not in main_module.os.environ

