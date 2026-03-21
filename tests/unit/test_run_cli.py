"""Tests for `vllmlx run` CLI behavior."""

from click.testing import CliRunner

from vllmlx.cli.main import cli


def test_run_help_has_no_daemon_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])

    assert result.exit_code == 0
    assert "--daemon" not in result.output


def test_run_rejects_legacy_daemon_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--daemon"])

    assert result.exit_code != 0
    assert "No such option" in result.output
