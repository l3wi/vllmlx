"""Tests for version single-sourcing and API version wiring."""

from __future__ import annotations

import tomllib
from pathlib import Path

from vllmlx import __version__
from vllmlx.daemon.server import create_app


def test_pyproject_uses_dynamic_version_from_package_file():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert "version" not in project
    assert "version" in project.get("dynamic", [])
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/vllmlx/__init__.py"


def test_fastapi_app_version_matches_package_version():
    app = create_app()
    assert app.version == __version__
