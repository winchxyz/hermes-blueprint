"""The six phases and the exit gates that code (not the model) checks before a phase can end.

A gate is a list of artifact requirements. Each requirement names the artifact kind and the
producers allowed to write it. Kinds that carry the quality harness (research briefing, critic
verdict, plan) can only come from their dedicated tools, so the model cannot skip them by
recording a free-text note.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .store import Project, Store

PHASES: dict[int, str] = {
    1: "Understanding",
    2: "Context",
    3: "Generation",
    4: "Deep dive",
    5: "Critique",
    6: "Plan",
}
LAST_PHASE = max(PHASES)

# Producer name used when the model records an artifact through idea_phase(action="record").
RECORD = "idea_phase"


@dataclass(frozen=True)
class Requirement:
    kind: str
    producers: frozenset[str]
    label: str


def _req(kind: str, label: str, *producers: str) -> Requirement:
    return Requirement(kind, frozenset(producers), label)


GATES: dict[int, list[Requirement]] = {
    1: [_req("brief", "problem brief (who, what, why now, constraints)", RECORD),
        _req("profile_used", "builder profile confirmed for this project", "idea_profile")],
    2: [_req("briefing", "research briefing with source log, coverage and Not verified",
             "idea_research")],
    3: [_req("variants", "at least 3 distinct variants", RECORD)],
    4: [_req("choice", "chosen variant with the reason", RECORD)],
    5: [_req("verdict", "stored critic verdict (pre-committed)", "idea_verdict")],
    6: [_req("plan", "validated plan (A/H/W units, P10/P50/P90, effort vs calendar)",
             "idea_plan")],
}

# What idea_phase(action="record") may write, and in which phase.
RECORDABLE: dict[str, int] = {"brief": 1, "variants": 3, "deepdive": 4, "choice": 4}

MIN_VARIANTS = 3


def phase_name(phase: int) -> str:
    return f"{phase}. {PHASES[phase]}"


def missing(store: Store, project: Project, phase: int) -> list[str]:
    """Requirements of ``phase`` that the stored artifacts do not meet yet."""
    out = []
    for req in GATES[phase]:
        found = [a for a in store.artifacts(project.id, req.kind) if a.producer in req.producers]
        if not found:
            out.append(req.label)
    return out


class GateClosed(Exception):
    def __init__(self, phase: int, items: list[str]) -> None:
        super().__init__(f"phase {phase_name(phase)} is not done: missing " + "; ".join(items))
        self.phase = phase
        self.items = items


# Phases the user must take part in: the agent may not close them in the turn it entered them.
# Research (2) may run on its own. Skipping stays possible with /idea phase <n>.
USER_PHASES = {1, 3, 4, 5, 6}
USER_TURN_LABEL = ("a reply from the user in this phase (show the result, ask, and advance "
                   "after they answer; the user can skip with /idea phase <n>)")


def user_gap(store: Store, project: Project, phase: int) -> list[str]:
    if phase not in USER_PHASES:
        return []
    counts = store.turn_counts(project.id)
    if not counts:  # the state-card hook never ran (another host): nothing to check against
        return []
    return [] if counts.get(phase, 0) else [USER_TURN_LABEL]


def open_items(store: Store, project: Project) -> list[str]:
    """Everything the current phase still needs, artifacts and the user's turn."""
    return (missing(store, project, project.phase)
            + user_gap(store, project, project.phase))


def advance(store: Store, project: Project, reason: str = "advance") -> Project:
    """Move to the next phase if the current phase's gate is met and the user took part in it;
    finishing 6 marks the project planned."""
    if project.status != "active":
        raise ValueError(f"project is {project.status}, not active")
    gap = open_items(store, project)
    if gap:
        raise GateClosed(project.phase, gap)
    if project.phase == LAST_PHASE:
        return store.set_status(project.id, "planned")
    return store.set_phase(project.id, project.phase + 1, reason)


def go_to(store: Store, project: Project, target: int, reason: str) -> Project:
    """Jump to ``target``. Going back is always allowed (and logged); going forward needs every
    gate in between."""
    if target not in PHASES:
        raise ValueError(f"phase must be 1-{LAST_PHASE}")
    if target == project.phase:
        return project
    if target > project.phase:
        for phase in range(project.phase, target):
            gap = missing(store, project, phase)
            if gap:
                raise GateClosed(phase, gap)
    if project.status == "planned":
        store.set_status(project.id, "active")
    return store.set_phase(project.id, target, reason or "jump")


def validate_record(kind: str, content: Any, project: Project, store: Store) -> Any:
    """Check a free-form artifact before it is stored; return the normalized payload."""
    if kind not in RECORDABLE:
        allowed = ", ".join(sorted(RECORDABLE))
        raise ValueError(f"idea_phase can record only: {allowed}. Research briefings, critic "
                         "verdicts and plans come from their own tools.")
    if project.phase != RECORDABLE[kind]:
        raise ValueError(f"'{kind}' belongs to phase {phase_name(RECORDABLE[kind])}; the "
                         f"project is in {phase_name(project.phase)}")
    if kind == "variants":
        if not isinstance(content, list) or len(content) < MIN_VARIANTS:
            raise ValueError(f"variants must be a list of at least {MIN_VARIANTS} items")
        names = []
        for item in content:
            if not isinstance(item, dict) or not item.get("name") or not item.get("summary"):
                raise ValueError("each variant needs 'name' and 'summary'")
            names.append(str(item["name"]).strip().lower())
        if len(set(names)) != len(names):
            raise ValueError("variant names must be distinct")
        return content
    if kind == "choice":
        if not isinstance(content, dict) or not content.get("variant") or not content.get("reason"):
            raise ValueError("choice needs 'variant' (a recorded variant name) and 'reason'")
        latest = store.latest(project.id, "variants")
        names = {str(v["name"]).strip().lower() for v in (latest.payload if latest else [])}
        if str(content["variant"]).strip().lower() not in names:
            raise ValueError("choice must name one of the recorded variants")
        return content
    if isinstance(content, str):
        if not content.strip():
            raise ValueError(f"{kind} is empty")
        return {"text": content.strip()}
    if not content:
        raise ValueError(f"{kind} is empty")
    return content
