"""Schema migrations, projects, append-only artifacts, session bindings."""
from __future__ import annotations

import sqlite3

import pytest

from hermes_blueprint.store import SCHEMA_VERSION, Store, migrate, slugify


def test_migrate_is_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "x.db")
    assert migrate(conn) == SCHEMA_VERSION
    assert migrate(conn) == SCHEMA_VERSION
    (version,) = conn.execute("PRAGMA user_version").fetchone()
    assert version == SCHEMA_VERSION


def test_refuses_newer_schema(tmp_path):
    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="newer"):
        migrate(conn)


def test_create_project_starts_in_phase_1(store: Store):
    p = store.create_project("A Telegram bot that books padel courts")
    assert (p.phase, p.status) == (1, "active")
    assert p.slug == "telegram-bot-that-books-padel-courts"
    assert store.phase_events(p.id)[0][:3] == (None, 1, "start")


def test_slugs_are_unique(store: Store):
    a = store.create_project("Same idea")
    b = store.create_project("Same idea")
    assert (a.slug, b.slug) == ("same-idea", "same-idea-2")
    assert store.get_project("same-idea-2").id == b.id
    assert store.get_project(str(a.id)).id == a.id


def test_empty_idea_rejected(store: Store):
    with pytest.raises(ValueError):
        store.create_project("   ")


def test_unknown_project(store: Store):
    with pytest.raises(KeyError):
        store.get_project(42)


def test_artifacts_keep_order_and_payload(store: Store):
    p = store.create_project("x")
    store.add_artifact(p.id, 1, "brief", "idea_phase", {"text": "one"})
    store.add_artifact(p.id, 1, "brief", "idea_phase", {"text": "two"})
    assert [a.payload["text"] for a in store.artifacts(p.id, "brief")] == ["one", "two"]
    assert store.latest(p.id, "brief").payload == {"text": "two"}
    assert store.latest(p.id, "plan") is None


def test_bindings(store: Store):
    a = store.create_project("a")
    b = store.create_project("b")
    store.bind("s1", a.id)
    assert store.bound_project("s1").id == a.id
    store.bind("s1", b.id)
    assert store.bound_project("s1").id == b.id
    store.unbind("s1")
    assert store.bound_project("s1") is None
    assert store.bound_project("") is None


def test_slugify():
    assert slugify("  Hello, World!  ") == "hello-world"
    assert slugify("!!!") == "idea"
    assert len(slugify("x" * 200)) == 40
