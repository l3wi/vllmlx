"""Tests for config CLI command."""

from pathlib import Path

from click.testing import CliRunner

from vllmlx.cli.config_cmd import config_cmd
from vllmlx.config import Config


def test_config_set_get_health_ttl_seconds_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    runner = CliRunner()

    set_result = runner.invoke(
        config_cmd,
        ["set", "daemon.health_ttl_seconds", "2.75"],
    )
    assert set_result.exit_code == 0

    get_result = runner.invoke(config_cmd, ["get", "daemon.health_ttl_seconds"])
    assert get_result.exit_code == 0
    assert "2.75" in get_result.output

    loaded = Config.load()
    assert loaded.daemon.health_ttl_seconds == 2.75
