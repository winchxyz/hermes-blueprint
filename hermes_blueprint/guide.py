"""Per-phase guidance: the reference file to load, the few rules that matter, the next tool.

Used by the per-turn state card (``pre_llm_call``) and by ``idea_phase(action=status)``. The full
method lives in the bundled skill ``hermes-blueprint:blueprint`` and its reference files.
"""
from __future__ import annotations

from typing import Any

from . import phases
from .store import Project, Store

SKILL = "hermes-blueprint:blueprint"

PHASE_GUIDE: dict[int, dict[str, Any]] = {
    1: {"reference": "references/1-understanding.md",
        "rules": ["Interview first: one or two questions per turn, no solutions yet.",
                  "Pin down who it is for, the problem, why now, constraints, what done means.",
                  "Show the builder profile (idea_profile get); ask only for missing fields; "
                  "confirm it after the user agrees."],
        "next": "idea_phase(record brief) and idea_profile(confirm), then advance"},
    2: {"reference": "references/2-context.md",
        "rules": ["Plan the research (idea_research plan), then search, fetch, quote.",
                  "Snippets are leads: no claim without a fetched page and an exact quote.",
                  "Run disconfirmation searches and the competitor sweep per channel.",
                  "Absence is never ✅: log it with action=absence.",
                  "verify, then briefing; show the briefing as returned."],
        "next": "idea_research(plan/search/fetch/claim/verify/briefing), then advance"},
    3: {"reference": "references/3-generation.md",
        "rules": ["At least 3 really different variants (different user, mechanism or "
                  "business model), not one idea in three sizes.",
                  "Each variant: name, summary, who for, why it could win, biggest risk.",
                  "Ground variants in the briefing's claims [C#]."],
        "next": "idea_phase(record variants), then advance"},
    4: {"reference": "references/4-deep-dive.md",
        "rules": ["Score variants one at a time against a fixed rubric, evidence before score.",
                  "Work out what must be true for the leading variant.",
                  "The user chooses; record the choice with the reason."],
        "next": "idea_phase(record deepdive, record choice), then advance"},
    5: {"reference": "references/5-critique.md",
        "rules": ["Outside view first: reference class and a sourced base rate.",
                  "Premortem shares are conditional on failure; calibrate to the builder.",
                  "Commit the verdict (idea_verdict commit) before you show it.",
                  "Pushback without new evidence: idea_verdict pushback, restate once, keep it."],
        "next": "idea_verdict(commit), then advance"},
    6: {"reference": "references/6-plan.md",
        "rules": ["idea_plan draft runs an isolated planner; fix and submit if needed.",
                  "A/H/W units with P10/P50/P90; code computes effort vs calendar.",
                  "Months only from named waits; agent work is hours."],
        "next": "idea_plan(draft or submit), then advance; then /idea handoff"},
}


def next_step(store: Store, project: Project) -> dict[str, Any]:
    if project.status == "planned":
        return {"next": "Planned. The user can run /idea handoff (kanban cards, project "
                        "folder); later idea_recheck(report).",
                "reference": "references/recheck.md"}
    g = PHASE_GUIDE[project.phase]
    return {"missing": phases.open_items(store, project), "rules": g["rules"],
            "next": g["next"], "reference": g["reference"]}


LANGUAGE_RULE = ("Reply in the language of the user's own words above this note; if they "
                 "wrote too little to tell, use the language of the project title.")


def state_card(store: Store, project: Project) -> str:
    """A compact per-turn reminder (kept well under ~900 characters)."""
    head = (f"[Blueprint] (plugin note, not written by the user) Project #{project.id} "
            f"\"{project.title}\"")
    if project.status == "planned":
        return (f"{head}: plan done. Re-checks: idea_recheck(report). Handoff: the user runs "
                f"/idea handoff. Method: skill_view('{SKILL}', file_path='references/"
                "recheck.md').")
    g = PHASE_GUIDE[project.phase]
    gap = phases.open_items(store, project)
    lines = [f"{head}, phase {phases.phase_name(project.phase)}."]
    lines.append("Gate still needs: " + ("; ".join(gap) if gap else "nothing (advance when "
                                         "the user is ready)") + ".")
    lines += [f"- {r}" for r in g["rules"]]
    lines.append(f"Next: {g['next']} (if the idea_* tools are not loaded: tool_search "
                 f"'blueprint'). Method: skill_view('{SKILL}') once, then "
                 f"file_path='{g['reference']}'. {LANGUAGE_RULE}")
    return "\n".join(lines)
