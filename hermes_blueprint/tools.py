"""Model-facing tools. Each handler returns a JSON string and never raises (Hermes contract)."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from . import phases
from .store import Project, Store

IDEA_PHASE_SCHEMA: dict[str, Any] = {
    "name": "idea_phase",
    "description": (
        "Blueprint brainstorm: turns a raw idea into a buildable plan. Project phase state "
        "for this chat (Understanding, Context, Generation, Deep dive, Critique, Plan). "
        "action=status shows the phase and what its gate still needs; action=record stores "
        "a phase artifact (brief in phase 1, variants in "
        "3, deepdive and choice in 4); action=advance moves on only when the gate is met; "
        "action=back returns to an earlier phase with a reason."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "record", "advance", "back"]},
            "kind": {"type": "string", "enum": sorted(phases.RECORDABLE),
                     "description": "Artifact kind for action=record."},
            "content": {
                "description": (
                    "For record. brief/deepdive: text or object. variants: list of at least 3 "
                    "objects with name and summary. choice: {variant, reason}."),
            },
            "phase": {"type": "integer", "minimum": 1, "maximum": 6,
                      "description": "Target phase for action=back."},
            "reason": {"type": "string", "description": "Why (required for back)."},
        },
        "required": ["action"],
    },
}


def _ok(**data: Any) -> str:
    return json.dumps({"ok": True, **data}, ensure_ascii=False)


def _err(message: str, **data: Any) -> str:
    return json.dumps({"ok": False, "error": message, **data}, ensure_ascii=False)


def project_view(store: Store, project: Project) -> dict[str, Any]:
    view: dict[str, Any] = {
        "project": {"id": project.id, "slug": project.slug, "title": project.title,
                    "idea": project.idea, "status": project.status},
        "phase": {"number": project.phase, "name": phases.PHASES[project.phase]},
    }
    if project.status == "active":
        view["gate_missing"] = phases.missing(store, project, project.phase)
    return view


class IdeaPhaseTool:
    def __init__(self, store_factory: Callable[[], Store]) -> None:
        self._store_factory = store_factory

    def __call__(self, args: dict, **kwargs: Any) -> str:
        try:
            return self._run(args or {}, kwargs)
        except Exception as exc:  # never raise into the agent loop
            return _err(f"{type(exc).__name__}: {exc}")

    def _run(self, args: dict, kwargs: dict) -> str:
        store = self._store_factory()
        session = kwargs.get("session_id") or kwargs.get("session_key") or ""
        project = store.bound_project(session)
        if project is None:
            return _err("No blueprint project in this chat. Ask the user to run "
                        "/idea start <idea> or /idea resume <id>.")
        action = args.get("action")
        if action == "status":
            return _ok(**project_view(store, project))
        if action == "record":
            kind = args.get("kind") or ""
            try:
                payload = phases.validate_record(kind, args.get("content"), project, store)
            except ValueError as exc:
                return _err(str(exc))
            art = store.add_artifact(project.id, project.phase, kind, phases.RECORD, payload)
            return _ok(recorded={"id": art.id, "kind": kind}, **project_view(store, project))
        if action == "advance":
            try:
                project = phases.advance(store, project, args.get("reason") or "advance")
            except phases.GateClosed as exc:
                return _err(str(exc), missing=exc.items, **project_view(store, project))
            except ValueError as exc:
                return _err(str(exc))
            return _ok(**project_view(store, project))
        if action == "back":
            target, reason = args.get("phase"), (args.get("reason") or "").strip()
            if not isinstance(target, int) or target >= project.phase:
                return _err("back needs a phase number lower than the current one")
            if not reason:
                return _err("back needs a reason (it is logged)")
            project = phases.go_to(store, project, target, f"back: {reason}")
            return _ok(**project_view(store, project))
        return _err(f"unknown action {action!r}")
