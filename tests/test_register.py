"""Registration matches plugin.yaml and stays free of side effects."""
from __future__ import annotations

from pathlib import Path

import yaml
from conftest import FakeCtx

from hermes_blueprint import __version__, register

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))


def test_register_matches_manifest():
    ctx = FakeCtx()
    register(ctx)
    assert set(ctx.tools) == set(MANIFEST["provides_tools"])
    assert [h for h, _ in ctx.hooks] == MANIFEST["provides_hooks"]
    assert "idea" in ctx.commands


def test_register_opens_no_database():
    calls = []

    def factory():
        calls.append(1)
        raise AssertionError("store opened during register")

    register(FakeCtx(), store_factory=factory)
    assert calls == []


def test_versions_agree():
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert MANIFEST["version"] == pyproject["project"]["version"] == __version__


def test_tool_schemas_are_named_like_their_tools():
    ctx = FakeCtx()
    register(ctx)
    for name, entry in ctx.tools.items():
        assert entry["schema"]["name"] == name
        assert entry["schema"]["parameters"]["type"] == "object"
