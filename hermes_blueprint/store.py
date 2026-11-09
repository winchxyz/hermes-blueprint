"""SQLite storage for projects, phase history, artifacts and session bindings.

Hermes gives the plugin a database through ``plugins.plugin_storage.plugin_db``; tests pass a
factory for a temporary file. Every operation opens a short-lived connection, so tool handlers on
different threads never share one. Artifacts and phase events are append-only: nothing in this
module updates or deletes them.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from typing import Any

Connect = Callable[[], sqlite3.Connection]

# Each entry upgrades the schema by one version (PRAGMA user_version). Append, never edit.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE projects (
        id INTEGER PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        idea TEXT NOT NULL,
        phase INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE TABLE phase_events (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        from_phase INTEGER,
        to_phase INTEGER NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        at REAL NOT NULL
    );
    CREATE TABLE artifacts (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        phase INTEGER NOT NULL,
        kind TEXT NOT NULL,
        producer TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE INDEX artifacts_by_project ON artifacts(project_id, kind);
    CREATE TABLE session_bindings (
        session_id TEXT PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        bound_at REAL NOT NULL
    );
    """,
    # v2: research ledger, predictions, builder profile, kanban cards, velocity ledger.
    """
    CREATE TABLE searches (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        query TEXT NOT NULL,
        purpose TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT '',
        results TEXT NOT NULL,
        at REAL NOT NULL
    );
    CREATE TABLE sources (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        url TEXT NOT NULL,
        domain TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0,
        fetched_at REAL NOT NULL
    );
    CREATE TABLE claims (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        text TEXT NOT NULL,
        type TEXT NOT NULL,
        label TEXT NOT NULL,
        evidence TEXT NOT NULL,
        as_of TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        note TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE TABLE predictions (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        statement TEXT NOT NULL,
        p_model REAL NOT NULL,
        p_user REAL,
        resolve_by TEXT NOT NULL,
        how TEXT NOT NULL,
        origin TEXT NOT NULL,
        outcome INTEGER,
        resolved_at REAL,
        created_at REAL NOT NULL
    );
    CREATE TABLE kv (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE TABLE cards (
        project_id INTEGER NOT NULL REFERENCES projects(id),
        unit_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        created_at REAL NOT NULL,
        PRIMARY KEY (project_id, unit_id)
    );
    CREATE TABLE actuals (
        id INTEGER PRIMARY KEY,
        project_id INTEGER,
        unit_id TEXT NOT NULL,
        unit_class TEXT NOT NULL,
        ref_class TEXT NOT NULL DEFAULT '',
        estimate_p50 REAL,
        actual REAL NOT NULL,
        source TEXT NOT NULL,
        at REAL NOT NULL
    );
    """,
    # v3: user turns seen per phase (from the pre_llm_call hook; turn ids only, never the text).
    """
    CREATE TABLE turns (
        project_id INTEGER NOT NULL REFERENCES projects(id),
        phase INTEGER NOT NULL,
        turn_id TEXT NOT NULL,
        at REAL NOT NULL,
        PRIMARY KEY (project_id, phase, turn_id)
    );
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)


@dataclass(frozen=True)
class Project:
    id: int
    slug: str
    title: str
    idea: str
    phase: int
    status: str
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class Artifact:
    id: int
    project_id: int
    phase: int
    kind: str
    producer: str
    payload: Any
    created_at: float


def slugify(text: str, limit: int = 40) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    if words and words[0] in ("a", "an", "the") and len(words) > 1:
        words = words[1:]
    slug = ""
    for word in words:  # whole words only, never cut one in half
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > limit:
            break
        slug = candidate
    return slug or (words[0][:limit] if words else "idea")


class Store:
    def __init__(self, connect: Connect, clock: Callable[[], float] = time.time) -> None:
        self._connect = connect
        self._clock = clock
        self._ready = False

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as conn:
            if not self._ready:
                migrate(conn)
                self._ready = True
            with conn:
                yield conn

    def tx(self) -> Any:
        """One transaction on a short-lived connection (for the domain modules)."""
        return self._tx()

    def now(self) -> float:
        return self._clock()

    # key-value (builder profile and other per-user settings) --------------------------------

    def kv_get(self, key: str, default: Any = None) -> Any:
        with self._tx() as conn:
            row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def kv_set(self, key: str, value: Any) -> None:
        with self._tx() as conn:
            conn.execute("INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?)"
                         " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                         " updated_at = excluded.updated_at",
                         (key, json.dumps(value, ensure_ascii=False, sort_keys=True),
                          self._clock()))

    # user turns -----------------------------------------------------------------------------

    def record_turn(self, project_id: int, phase: int, turn_id: str) -> None:
        with self._tx() as conn:
            conn.execute("INSERT OR IGNORE INTO turns (project_id, phase, turn_id, at)"
                         " VALUES (?, ?, ?, ?)", (project_id, phase, turn_id, self._clock()))

    def turn_counts(self, project_id: int) -> dict[int, int]:
        """User turns seen per phase; empty when the hook never ran for this project."""
        with self._tx() as conn:
            rows = conn.execute("SELECT phase, COUNT(*) FROM turns WHERE project_id = ?"
                                " GROUP BY phase", (project_id,)).fetchall()
        return {int(phase): int(n) for phase, n in rows}

    # projects -------------------------------------------------------------------------------

    def create_project(self, idea: str, title: str | None = None) -> Project:
        idea = idea.strip()
        if not idea:
            raise ValueError("idea text is empty")
        title = (title or idea.splitlines()[0])[:80].strip()
        now = self._clock()
        with self._tx() as conn:
            base = slugify(title)
            slug, n = base, 2
            while conn.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone():
                slug, n = f"{base}-{n}", n + 1
            cur = conn.execute(
                "INSERT INTO projects (slug, title, idea, phase, status, created_at, updated_at)"
                " VALUES (?, ?, ?, 1, 'active', ?, ?)", (slug, title, idea, now, now))
            pid = cur.lastrowid
            conn.execute("INSERT INTO phase_events (project_id, from_phase, to_phase, reason, at)"
                         " VALUES (?, NULL, 1, 'start', ?)", (pid, now))
        return self.get_project(pid)

    def get_project(self, ref: int | str) -> Project:
        with self._tx() as conn:
            if isinstance(ref, int) or str(ref).isdigit():
                row = conn.execute("SELECT * FROM projects WHERE id = ?", (int(ref),)).fetchone()
            else:
                row = conn.execute("SELECT * FROM projects WHERE slug = ?", (ref,)).fetchone()
        if row is None:
            raise KeyError(f"no project {ref!r}")
        return Project(*row)

    def list_projects(self) -> list[Project]:
        with self._tx() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [Project(*r) for r in rows]

    def set_phase(self, project_id: int, to_phase: int, reason: str) -> Project:
        now = self._clock()
        with self._tx() as conn:
            (current,) = conn.execute("SELECT phase FROM projects WHERE id = ?",
                                      (project_id,)).fetchone()
            conn.execute("UPDATE projects SET phase = ?, updated_at = ? WHERE id = ?",
                         (to_phase, now, project_id))
            conn.execute("INSERT INTO phase_events (project_id, from_phase, to_phase, reason, at)"
                         " VALUES (?, ?, ?, ?, ?)", (project_id, current, to_phase, reason, now))
        return self.get_project(project_id)

    def set_status(self, project_id: int, status: str) -> Project:
        with self._tx() as conn:
            conn.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                         (status, self._clock(), project_id))
        return self.get_project(project_id)

    def phase_events(self, project_id: int) -> list[tuple[int | None, int, str, float]]:
        with self._tx() as conn:
            return conn.execute(
                "SELECT from_phase, to_phase, reason, at FROM phase_events WHERE project_id = ?"
                " ORDER BY id", (project_id,)).fetchall()

    # artifacts ------------------------------------------------------------------------------

    def add_artifact(self, project_id: int, phase: int, kind: str, producer: str,
                     payload: Any) -> Artifact:
        now = self._clock()
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO artifacts (project_id, phase, kind, producer, payload, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)", (project_id, phase, kind, producer, body, now))
            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
        return Artifact(cur.lastrowid, project_id, phase, kind, producer, payload, now)

    def artifacts(self, project_id: int, kind: str | None = None) -> list[Artifact]:
        sql = "SELECT * FROM artifacts WHERE project_id = ?"
        params: tuple = (project_id,)
        if kind is not None:
            sql += " AND kind = ?"
            params += (kind,)
        with self._tx() as conn:
            rows = conn.execute(sql + " ORDER BY id", params).fetchall()
        return [Artifact(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), r[6]) for r in rows]

    def latest(self, project_id: int, kind: str) -> Artifact | None:
        found = self.artifacts(project_id, kind)
        return found[-1] if found else None

    # session bindings -----------------------------------------------------------------------

    def bind(self, session_id: str, project_id: int) -> None:
        with self._tx() as conn:
            conn.execute("INSERT INTO session_bindings (session_id, project_id, bound_at)"
                         " VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET"
                         " project_id = excluded.project_id, bound_at = excluded.bound_at",
                         (session_id, project_id, self._clock()))

    def unbind(self, session_id: str) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM session_bindings WHERE session_id = ?", (session_id,))

    def bound_project(self, session_id: str | None) -> Project | None:
        if not session_id:
            return None
        with self._tx() as conn:
            row = conn.execute("SELECT project_id FROM session_bindings WHERE session_id = ?",
                               (session_id,)).fetchone()
        return self.get_project(row[0]) if row else None


def migrate(conn: sqlite3.Connection) -> int:
    """Bring ``conn`` to SCHEMA_VERSION; refuse a database written by a newer plugin."""
    (version,) = conn.execute("PRAGMA user_version").fetchone()
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"database schema v{version} is newer than this plugin "
                           f"(v{SCHEMA_VERSION}); update hermes-blueprint")
    for target in range(version + 1, SCHEMA_VERSION + 1):
        with conn:
            conn.executescript(MIGRATIONS[target - 1])
            conn.execute(f"PRAGMA user_version = {target}")
    return SCHEMA_VERSION
