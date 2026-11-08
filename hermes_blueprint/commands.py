"""The ``/idea`` slash command: project state changes and status, no model tokens.

Slash-command output goes to the user, not to the model, so ``start`` and ``resume`` tell the
user to send a message to begin; the model then sees the project through the ``idea_phase`` tool.
"""
from __future__ import annotations

import shlex
import time
from collections.abc import Callable
from typing import Any

from . import phases
from .store import Project, Store

HELP = """/idea: turn a raw idea into a plan you can build.

  /idea start <your idea>   start a project and bind it to this chat
  /idea status              phase, gate and what is missing
  /idea phase [n] [reason]  show the phase, or move to phase n (forward only if gates are met)
  /idea list                all projects
  /idea resume <id|slug>    bind an existing project to this chat
  /idea log                 phase history and recorded artifacts
  /idea stop                unbind this chat (the project is kept)
"""


def _when(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def status_text(store: Store, project: Project) -> str:
    lines = [f"#{project.id} {project.title} [{project.slug}]",
             f"Status: {project.status}. Phase {phases.phase_name(project.phase)}."]
    if project.status == "active":
        gap = phases.missing(store, project, project.phase)
        if gap:
            lines.append("To finish this phase: " + "; ".join(gap) + ".")
        else:
            lines.append("Gate met: the phase can advance.")
    track = " > ".join(
        (f"[{n}]" if n == project.phase else str(n)) for n in phases.PHASES)
    lines.append(f"Phases: {track}")
    return "\n".join(lines)


class IdeaCommand:
    """Callable handler for ``ctx.register_command('idea', ...)``."""

    def __init__(self, store_factory: Callable[[], Store]) -> None:
        self._store_factory = store_factory

    def __call__(self, raw_args: str, session_id: str = "", session_key: str = "",
                 **_: Any) -> str:
        key = session_id or session_key
        try:
            parts = shlex.split(raw_args or "")
        except ValueError:
            parts = (raw_args or "").split()
        sub, rest = (parts[0].lower(), parts[1:]) if parts else ("help", [])
        handler = getattr(self, f"_cmd_{sub}", None)
        if handler is None:
            return f"Unknown subcommand '{sub}'.\n\n{HELP}"
        try:
            return handler(self._store_factory(), key, rest, raw_args or "")
        except (KeyError, ValueError, phases.GateClosed) as exc:
            return f"/idea {sub}: {exc}"

    def _cmd_help(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        return HELP

    def _cmd_start(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        idea = raw.strip()[len("start"):].strip()
        if not idea:
            return "Usage: /idea start <your idea in a sentence or two>"
        project = store.create_project(idea)
        if key:
            store.bind(key, project.id)
        bound = "" if key else "\n(No chat session found: run /idea resume in the chat.)"
        return (f"Started #{project.id} {project.title} [{project.slug}].\n"
                f"Phase {phases.phase_name(1)}. Send any message to begin: the agent will "
                f"interview you about the idea first.{bound}")

    def _cmd_status(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat. /idea start <idea> or /idea resume <id>."
        return status_text(store, project)

    def _cmd_list(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        projects = store.list_projects()
        if not projects:
            return "No projects yet. /idea start <idea>."
        current = store.bound_project(key)
        rows = []
        for p in projects:
            mark = "*" if current and current.id == p.id else " "
            rows.append(f"{mark} #{p.id} {p.title} [{p.slug}]: phase {p.phase}, {p.status},"
                        f" updated {_when(p.updated_at)}")
        return "\n".join(rows)

    def _cmd_resume(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        if not rest:
            return "Usage: /idea resume <id|slug>"
        if not key:
            return "No chat session found to bind the project to."
        project = store.get_project(rest[0])
        store.bind(key, project.id)
        return status_text(store, project) + "\nBound to this chat. Send a message to continue."

    def _cmd_phase(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat."
        if not rest:
            return status_text(store, project)
        if not rest[0].isdigit():
            return "Usage: /idea phase <1-6> [reason]"
        reason = " ".join(rest[1:]) or "user jump"
        project = phases.go_to(store, project, int(rest[0]), reason)
        return status_text(store, project)

    def _cmd_log(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat."
        lines = [f"#{project.id} {project.title}: history"]
        for from_phase, to_phase, reason, at in store.phase_events(project.id):
            arrow = f"{from_phase} > {to_phase}" if from_phase else f"start at {to_phase}"
            lines.append(f"  {_when(at)}  phase {arrow}  ({reason})")
        for art in store.artifacts(project.id):
            lines.append(f"  {_when(art.created_at)}  {art.kind} (phase {art.phase},"
                         f" by {art.producer})")
        return "\n".join(lines)

    def _cmd_stop(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat."
        store.unbind(key)
        return f"Unbound #{project.id} from this chat. /idea resume {project.id} to return."
