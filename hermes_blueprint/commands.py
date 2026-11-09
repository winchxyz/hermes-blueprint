"""The ``/idea`` slash command: project state changes and status, no model tokens.

Slash-command output goes to the user, not to the model, so ``start`` and ``resume`` tell the
user to send a message to begin; the model then sees the project through the ``idea_*`` tools.
The handoff writes outside the plugin's data (a folder, kanban cards), so it lives here, where
the user types it and confirms it.
"""
from __future__ import annotations

import os
import shlex
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import handoff, phases, profile, recheck
from .store import Project, Store

HELP = """/idea: turn a raw idea into a plan you can build.

  /idea start <your idea>   start a project and bind it to this chat
  /idea status              phase, gate and what is missing
  /idea phase [n] [reason]  show the phase, or move to phase n (forward only if gates are met)
  /idea list                all projects
  /idea resume <id|slug>    bind an existing project to this chat
  /idea log                 phase history and recorded artifacts
  /idea stop                unbind this chat (the project is kept)
  /idea profile             your builder profile (who builds: agents, hours, accounts)
  /idea handoff             after the plan: what the handoff will create
  /idea handoff folder <dir>    write README, PLAN, DECISIONS, RESEARCH, AGENTS into <dir>
  /idea handoff cards [--hold]  create the plan's units as Hermes kanban cards
  /idea recheck             progress, due predictions, estimate vs actual
  /idea ledger              your velocity ledger vs the base rates
"""


def _when(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def status_text(store: Store, project: Project) -> str:
    lines = [f"#{project.id} {project.title} [{project.slug}]",
             f"Status: {project.status}. Phase {phases.phase_name(project.phase)}."]
    if project.status == "active":
        gap = phases.open_items(store, project)
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

    def __init__(self, store_factory: Callable[[], Store], ctx: Any = None) -> None:
        self._store_factory = store_factory
        self._ctx = ctx

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
        except (KeyError, ValueError, OSError, phases.GateClosed) as exc:
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

    # profile and ledger ------------------------------------------------------------------------

    def _cmd_profile(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        prof = profile.load(store)
        if not prof["fields"]:
            return ("No builder profile yet. In a brainstorm the agent asks for it in phase 1. "
                    "Fields: " + ", ".join(profile.FIELDS) + ".")
        lines = [f"Builder profile v{prof['version']}:"]
        lines += [f"  {k}: {v}" for k, v in sorted(prof["fields"].items())]
        lines.append("To change it, tell the agent (it calls idea_profile set).")
        return "\n".join(lines)

    def _cmd_ledger(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        lines = ["Unit class: P10 / P50 / P90 active hours (basis)"]
        for r in profile.class_rates(store):
            lines.append(f"  {r['class']}: {r['p10_h']:g} / {r['p50_h']:g} / {r['p90_h']:g}"
                         f" ({r['basis']})")
        lines.append(f"Actuals recorded: {len(profile.actuals(store))}. A class with 3 or more "
                     "uses your own numbers.")
        return "\n".join(lines)

    # handoff -----------------------------------------------------------------------------------

    def _confirm(self, question: str, choices: list[dict], flags: set[str]) -> str | None:
        if "--yes" in flags:
            return str(choices[0]["value"])
        ask = getattr(self._ctx, "ask_choice", None)
        if ask is None:
            return None
        try:
            return ask(question, choices)
        except Exception:
            return None

    def _dispatch(self, name: str, args: dict) -> str:
        if self._ctx is None:
            raise ValueError("kanban is not available here")
        return self._ctx.dispatch_tool(name, args)

    def _setting(self, name: str, default: str) -> str:
        try:
            value = self._ctx.get_config(name, default) if self._ctx is not None else default
        except Exception:
            value = default
        return str(value or default)

    def _resolve(self, text: str) -> Path:
        path = Path(os.path.expandvars(text.strip().strip('"'))).expanduser()
        if path.is_absolute():
            return path
        base = ""
        try:
            base = self._ctx.session_cwd() if self._ctx is not None else ""
        except Exception:
            base = ""
        return (Path(base) if base else Path.home() / "blueprint-projects") / path

    def _cmd_handoff(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat."
        plan = handoff.plan_payload(store, project)
        if plan is None:
            return "No validated plan yet: the handoff comes after phase 6."
        flags = {r for r in rest if r.startswith("--")}
        args = [r for r in rest if not r.startswith("--")]
        units = plan["plan"]["units"]
        assignee = self._setting("kanban_assignee", "default")
        if not args:
            counts = {c: sum(u["class"] == c for u in units) for c in "AHW"}
            return (f"Plan: {len(units)} units ({counts['A']} agent, {counts['H']} yours, "
                    f"{counts['W']} waits).\n"
                    "  /idea handoff folder <dir>    project folder for the coding agent\n"
                    "  /idea handoff cards [--hold]  kanban cards: agent units go to the "
                    f"'{assignee}' profile; your units and waits are held (blocked) until you "
                    "mark them done.\n"
                    "Run folder first so the cards point at it.")
        if args[0] == "folder":
            if len(args) < 2:
                return "Usage: /idea handoff folder <dir>"
            target = self._resolve(" ".join(args[1:]))
            files = handoff.scaffold_files(store, project)
            choice = self._confirm(
                f"Write {len(files)} files ({', '.join(files)}) to {target}?",
                [{"value": "write", "label": "Write the files"},
                 {"value": "cancel", "label": "Cancel"}], flags)
            if choice is None:
                return f"Confirm with: /idea handoff folder \"{target}\" --yes"
            if choice != "write":
                return "Cancelled."
            written = handoff.write_scaffold(target, files)
            store.add_artifact(project.id, project.phase, "scaffold", "idea_handoff",
                               {"path": str(target), "files": written})
            return f"Wrote {', '.join(written)} to {target}."
        if args[0] == "cards":
            tenant = self._setting("kanban_tenant", "blueprint")
            choice = self._confirm(
                f"Create {len(units)} kanban cards for #{project.id} (agent units assigned to "
                f"'{assignee}')?",
                [{"value": "create", "label": "Create; agents can start"},
                 {"value": "hold", "label": "Create all held (blocked)"},
                 {"value": "cancel", "label": "Cancel"}], flags)
            if choice is None:
                return "Confirm with: /idea handoff cards --yes (add --hold to hold them)"
            if choice == "cancel":
                return "Cancelled."
            made = handoff.create_cards(store, project, self._dispatch, assignee=assignee,
                                        tenant=tenant,
                                        hold="--hold" in flags or choice == "hold")
            lines = [f"Kanban cards for #{project.id} (tenant {tenant}):"]
            for m in made:
                lines.append(f"  {m['unit']}: " + (f"{m['task_id']} ({m['status']})"
                                                   if "task_id" in m else f"error {m['error']}"))
            lines.append("Re-running is safe: the same units return the same cards.")
            return "\n".join(lines)
        return "Usage: /idea handoff [folder <dir> | cards [--hold]]"

    # recheck -----------------------------------------------------------------------------------

    def _cmd_recheck(self, store: Store, key: str, rest: list[str], raw: str) -> str:
        project = store.bound_project(key)
        if project is None:
            return "No project in this chat."
        dispatch = self._dispatch if self._ctx is not None else (lambda n, a: "{}")
        data = recheck.RecheckTool(lambda: store, dispatch).act_report(store, project, {})
        lines = [f"#{project.id} {project.title}: re-check"]
        for u in data["units"]:
            extra = f", card {u.get('status') or '-'}" if "card" in u else ""
            if "actual" in u:
                extra += f", actual {u['actual']:g} vs P50 {u['p50']:g}"
            lines.append(f"  {u['unit']} {u['title']} ({u['class']}{extra})")
        s = data["scores"]
        line = (f"Predictions resolved: {s['resolved']}; due now: "
                f"{len(data['predictions_due'])}.")
        if s["brier_model"] is not None:
            line += f" Brier: model {s['brier_model']}"
            if s["brier_user"] is not None:
                line += f", you {s['brier_user']}"
            line += " (0 is perfect, always-50% scores 0.25)."
        lines.append(line)
        lines.append("Send a message (for example 'recheck') and the agent goes through the "
                     "due predictions and actual hours with you.")
        return "\n".join(lines)
