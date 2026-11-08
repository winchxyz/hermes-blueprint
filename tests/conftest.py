"""Shared fixtures: a fake Hermes ctx and a store on a temporary SQLite file. No network."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hermes_blueprint.store import Store  # noqa: E402


class FakeCtx:
    """Records register_* calls like Hermes' PluginContext."""

    def __init__(self, config: dict | None = None) -> None:
        self.tools: dict[str, dict] = {}
        self.hooks: list[tuple[str, object]] = []
        self.commands: dict[str, dict] = {}
        self.skills: list[dict] = []
        self.config = dict(config or {})
        self.dispatched: list[tuple[str, dict]] = []

    def register_tool(self, name, toolset, schema, handler, check_fn=None, requires_env=None,
                      is_async=False, description="", emoji="", override=False):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    def register_hook(self, hook_name, callback, *, hold_stream=False):
        self.hooks.append((hook_name, callback))

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = {"handler": handler, "description": description,
                               "args_hint": args_hint}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills.append({"name": name, "path": Path(path), "description": description})

    def get_config(self, key, default=None):
        return self.config.get(key, default)


class Clock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "data.db"
    return Store(lambda: sqlite3.connect(db), clock=Clock())


@pytest.fixture
def fake_ctx():
    return FakeCtx()
