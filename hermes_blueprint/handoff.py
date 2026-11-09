"""Build handoff: a project folder for the coding agent and the plan as Hermes kanban cards.

Both write outside the plugin's own data, so they run only from ``/idea handoff ...``: a slash
command the user types and confirms (``ctx.dispatch_tool`` skips Hermes' approval hooks, so the
confirmation lives here). Card creation is idempotent: re-running the handoff returns the same
cards instead of duplicating them.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import verdict
from .store import Project, Store

Dispatch = Callable[[str, dict], str]


def plan_payload(store: Store, project: Project) -> dict[str, Any] | None:
    art = store.latest(project.id, "plan")
    return art.payload if art else None


def scaffold_files(store: Store, project: Project) -> dict[str, str]:
    plan = plan_payload(store, project)
    if plan is None:
        raise ValueError("no validated plan yet (phase 6)")
    v = verdict.current(store, project) or {}
    briefing = store.latest(project.id, "briefing")
    choice = store.latest(project.id, "choice")
    brief = store.latest(project.id, "brief")
    files: dict[str, str] = {}
    choice_text = ""
    if choice:
        choice_text = f"{choice.payload.get('variant')}: {choice.payload.get('reason')}"
    files["README.md"] = "\n".join([
        f"# {project.title}", "",
        *([project.idea, ""] if project.idea.strip().lower() != project.title.strip().lower()
          else []),
        f"**Chosen direction:** {choice_text or '-'}", "",
        f"**Thesis:** {v.get('thesis', '-')}", "",
        f"**Critic verdict:** {v.get('verdict', '-')} (P(success) {v.get('p_success', '-')}, "
        f"reference class: {(v.get('reference_class') or {}).get('name', '-')}).", "",
        "Files: PLAN.md (units, estimates, gates), DECISIONS.md (why), RESEARCH.md (evidence "
        "with sources), AGENTS.md (instructions for coding agents).", ""])
    files["PLAN.md"] = plan["markdown"]
    decisions = [f"# Decisions: {project.title}", ""]
    if brief:
        decisions += ["## Brief", "", _text(brief.payload), ""]
    if choice:
        decisions += ["## Direction", "", choice_text, ""]
    if v:
        decisions += ["## Critic verdict", "",
                      f"- Verdict: {v.get('verdict')}; thesis: {v.get('thesis')}",
                      f"- Outside view: {(v.get('reference_class') or {}).get('name')}: "
                      f"{(v.get('reference_class') or {}).get('base_rate')}",
                      f"- P(success): {v.get('p_success')}", "", "Premortem (share of "
                      "failures):"]
        for item in v.get("premortem") or []:
            decisions.append(f"- {item.get('cause')} ({item.get('p_given_failure')})")
        decisions += ["", "Tripwires:"]
        for t in v.get("tripwires") or []:
            decisions.append(f"- {t.get('metric')}: {t.get('threshold')} by {t.get('by')}")
        if v.get("changed_because"):
            cb = v["changed_because"]
            decisions += ["", f"Revised (v{v.get('version')}) because: {cb.get('reason')} "
                          f"Evidence: {'; '.join(cb.get('evidence') or [])}"]
        decisions += ["", "## Predictions to score at re-checks", ""]
        for p in predictions(store, project.id):
            decisions.append(f"- P{p['id']} ({p['p_model']}) {p['statement']}, by "
                             f"{p['resolve_by']}: {p['how']}")
    files["DECISIONS.md"] = "\n".join(decisions) + "\n"
    files["RESEARCH.md"] = (briefing.payload["markdown"] if briefing
                            else "# Research\n\nNo briefing stored.\n")
    files["AGENTS.md"] = "\n".join([
        f"# Instructions for coding agents: {project.title}", "",
        "- Build unit by unit in the order of PLAN.md. Each kanban card is one unit.",
        "- A unit is done when its acceptance criteria pass AND the result works for real "
        "use, not only in tests.",
        "- H units are the human's: decisions, taste, device tests, accounts. Do not do them; "
        "ask.",
        "- W units are external waits (reviews, approvals). Do not block on them silently; "
        "report.",
        "- Record actual active hours per unit in the card result, so re-checks can compare "
        "them with the estimate.",
        "- Facts with sources are in RESEARCH.md. Do not add unsourced claims to user-facing "
        "text.", ""])
    return files


BRIEF_ORDER = ("who", "problem", "idea", "not", "why_now", "success", "constraints", "kind")


def _text(payload: Any) -> str:
    """A recorded artifact as Markdown: a text field as is, an object as labelled lines."""
    if isinstance(payload, dict) and set(payload) == {"text"}:
        return str(payload["text"])
    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, indent=1)
    keys = [k for k in BRIEF_ORDER if k in payload] + sorted(k for k in payload
                                                             if k not in BRIEF_ORDER)
    lines = []
    for key in keys:
        value = payload[key]
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            lines.append(f"- **{label}:**")
            lines += [f"  - {_inline(item)}" for item in value]
        elif value not in (None, ""):
            lines.append(f"- **{label}:** {_inline(value)}")
    return "\n".join(lines)


def _inline(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def write_scaffold(target: Path, files: dict[str, str]) -> list[str]:
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"{target} exists and is not empty; pick a new folder")
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in files.items():
        (target / name).write_text(text, encoding="utf-8")
        written.append(name)
    return written


def predictions(store: Store, project_id: int) -> list[dict[str, Any]]:
    with store.tx() as conn:
        rows = conn.execute("SELECT id, statement, p_model, p_user, resolve_by, how, origin,"
                            " outcome, resolved_at FROM predictions WHERE project_id = ?"
                            " ORDER BY id", (project_id,)).fetchall()
    return [{"id": r[0], "statement": r[1], "p_model": r[2], "p_user": r[3], "resolve_by": r[4],
             "how": r[5], "origin": r[6], "outcome": r[7], "resolved_at": r[8]} for r in rows]


def cards(store: Store, project_id: int) -> dict[str, str]:
    with store.tx() as conn:
        rows = conn.execute("SELECT unit_id, task_id FROM cards WHERE project_id = ?",
                            (project_id,)).fetchall()
    return dict(rows)


def card_body(project: Project, unit: dict, folder: str) -> str:
    unit_word = "days (external wait)" if unit["class"] == "W" else "active hours"
    lines = [f"Blueprint project #{project.id} {project.title}, unit {unit['id']} "
             f"(class {unit['class']}).", "",
             f"Estimate: P10 {unit['p10']:g} / P50 {unit['p50']:g} / P90 {unit['p90']:g} "
             f"{unit_word}."]
    if folder:
        lines.append(f"Project folder: {folder} (PLAN.md, DECISIONS.md, RESEARCH.md, AGENTS.md)")
    if unit["acceptance"]:
        lines += ["", "## Acceptance"] + [f"- [ ] {a}" for a in unit["acceptance"]]
    if unit["class"] == "H":
        lines += ["", "This is the human's unit (decision, review or test). Mark it done when "
                  "finished; dependent agent units wait for it."]
    if unit["class"] == "W":
        lines += ["", "External wait. Mark it done when the wait is over."]
    if unit["note"]:
        lines += ["", f"Note: {unit['note']}"]
    return "\n".join(lines)


def create_cards(store: Store, project: Project, dispatch: Dispatch, *, assignee: str,
                 tenant: str, hold: bool) -> list[dict[str, Any]]:
    plan = plan_payload(store, project)
    if plan is None:
        raise ValueError("no validated plan yet (phase 6)")
    scaffold = store.latest(project.id, "scaffold")
    folder = scaffold.payload.get("path", "") if scaffold else ""
    existing = cards(store, project.id)
    out = []
    for unit in plan["plan"]["units"]:
        held = hold or unit["class"] in ("H", "W")
        payload: dict[str, Any] = {
            "title": f"[{project.slug}] {unit['id']} {unit['title']}"
                     + {"H": " (you)", "W": " (wait)"}.get(unit["class"], ""),
            "assignee": assignee, "tenant": tenant,
            "body": card_body(project, unit, folder),
            "idempotency_key": f"blueprint:{project.slug}:{unit['id']}",
            "parents": [existing[d] for d in unit["depends_on"] if d in existing],
        }
        if held:
            payload["initial_status"] = "blocked"
        if folder and unit["class"] == "A":
            payload.update(workspace_kind="dir", workspace_path=folder)
        raw = dispatch("kanban_create", payload)
        try:
            reply = json.loads(raw)
        except (TypeError, ValueError):
            reply = {"error": str(raw)[:300]}
        task_id = reply.get("task_id") if isinstance(reply, dict) else None
        if not task_id:
            out.append({"unit": unit["id"], "error": str(reply)[:300]})
            continue
        existing[unit["id"]] = task_id
        with store.tx() as conn:
            conn.execute("INSERT OR REPLACE INTO cards (project_id, unit_id, task_id, created_at)"
                         " VALUES (?, ?, ?, ?)", (project.id, unit["id"], task_id, store.now()))
        out.append({"unit": unit["id"], "task_id": task_id, "status": reply.get("status"),
                    "class": unit["class"]})
    return out


def card_status(dispatch: Dispatch, task_id: str) -> dict[str, Any]:
    raw = dispatch("kanban_show", {"task_id": task_id})
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {"status": "unknown"}
    task = data.get("task") if isinstance(data, dict) else None
    if not isinstance(task, dict):
        return {"status": "unknown"}
    out = {k: task.get(k) for k in ("status", "started_at", "completed_at")}
    if task.get("started_at") is not None and task.get("completed_at") is not None:
        out["elapsed_h"] = round((task["completed_at"] - task["started_at"]) / 3600, 2)
    return out

