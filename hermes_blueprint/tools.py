"""``idea_phase``: the project's phase state, free-form artifacts and gated transitions."""
from __future__ import annotations

from typing import Any

from . import guide, phases
from .common import BoundTool, ToolError
from .store import Project, Store

IDEA_PHASE_SCHEMA: dict[str, Any] = {
    "name": "idea_phase",
    "description": (
        "Blueprint brainstorm: turns a raw idea into a buildable plan. Project phase state "
        "for this chat (Understanding, Context, Generation, Deep dive, Critique, Plan). "
        "action=status shows the phase, what its gate still needs and the next step; "
        "action=record stores a phase artifact (brief in phase 1, variants in 3, deepdive and "
        "choice in 4); action=advance moves on only when the gate is met; action=back returns "
        "to an earlier phase with a reason."
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


def project_view(store: Store, project: Project) -> dict[str, Any]:
    view: dict[str, Any] = {
        "project": {"id": project.id, "slug": project.slug, "title": project.title,
                    "idea": project.idea, "status": project.status},
        "phase": {"number": project.phase, "name": phases.PHASES[project.phase]},
    }
    if project.status == "active":
        view["gate_missing"] = phases.missing(store, project, project.phase)
    view["guide"] = guide.next_step(store, project)
    return view


class IdeaPhaseTool(BoundTool):
    def act_status(self, store: Store, project: Project, args: dict) -> dict:
        return project_view(store, project)

    def act_record(self, store: Store, project: Project, args: dict) -> dict:
        kind = args.get("kind") or ""
        try:
            payload = phases.validate_record(kind, args.get("content"), project, store)
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        art = store.add_artifact(project.id, project.phase, kind, phases.RECORD, payload)
        return {"recorded": {"id": art.id, "kind": kind}, **project_view(store, project)}

    def act_advance(self, store: Store, project: Project, args: dict) -> dict:
        try:
            project = phases.advance(store, project, args.get("reason") or "advance")
        except phases.GateClosed as exc:
            raise ToolError(str(exc), missing=exc.items, **project_view(store, project)) from None
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        return project_view(store, project)

    def act_back(self, store: Store, project: Project, args: dict) -> dict:
        target, reason = args.get("phase"), (args.get("reason") or "").strip()
        if not isinstance(target, int) or target >= project.phase:
            raise ToolError("back needs a phase number lower than the current one")
        if not reason:
            raise ToolError("back needs a reason (it is logged)")
        project = phases.go_to(store, project, target, f"back: {reason}")
        return project_view(store, project)
