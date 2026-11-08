"""Phase 5 critic (H4, H8): outside view first, a pre-committed verdict, no caving to pushback.

``commit`` stores the verdict, its probabilities and scoreable predictions before they are shown
to the user, and refuses a verdict without a sourced base rate. ``revise`` is the only way to
change it and needs named new evidence recorded after the commit: a verified claim (the user's
citation, fetched and quote-checked) or an independent red-team run. Pushback without evidence
changes nothing; the tool says so and logs it.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

from . import base_rates, profile, research
from .common import BoundTool, ToolError, extract_json, parse_ref, require_phase
from .store import Project, Store
from .subagents import Job, Runner

PRODUCER = "idea_verdict"
VERDICTS = ("go", "go_with_conditions", "pivot", "kill")
MIN_PREDICTIONS = 3
P_MIN, P_MAX = 0.02, 0.98

VERDICT_SCHEMA: dict[str, Any] = {
    "name": "idea_verdict",
    "description": (
        "Blueprint critic verdict for the chosen idea (phase 5 Critique). Outside view first: "
        "commit needs a reference class with a sourced base rate (a verified C# claim or a "
        "base-rate key), a premortem conditional on failure, tripwires and >=3 scoreable "
        "predictions; it is stored before you show it. Actions: commit, show, pushback (user "
        "disagrees: returns the stored verdict and what evidence could change it), revise "
        "(needs new_evidence recorded after the commit), redteam (independent fresh-context "
        "critic), base_rates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": [
                "commit", "show", "pushback", "revise", "redteam", "base_rates"]},
            "verdict": {"type": "string", "enum": list(VERDICTS)},
            "thesis": {"type": "string", "description": "the bet in one sentence"},
            "reference_class": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "base_rate": {"type": "string"},
                               "source": {"type": "string",
                                          "description": "C# (verified claim) or base-rate key"}},
                "required": ["name", "base_rate", "source"]},
            "p_success": {"type": "number", "description": "P(the thesis holds within the "
                                                           "fair-shot budget), 0.02-0.98"},
            "premortem": {"type": "array", "items": {"type": "object", "properties": {
                "cause": {"type": "string"},
                "p_given_failure": {"type": "number"}}}},
            "must_be_true": {"type": "array", "items": {"type": "object", "properties": {
                "assumption": {"type": "string"}, "test": {"type": "string"},
                "cost": {"type": "string"}, "deadline": {"type": "string"},
                "kill_threshold": {"type": "string"}}}},
            "tripwires": {"type": "array", "items": {"type": "object", "properties": {
                "metric": {"type": "string"}, "threshold": {"type": "string"},
                "by": {"type": "string", "description": "YYYY-MM-DD"}}}},
            "builder_fit": {"type": "string",
                            "description": "how this builder's profile changes the risks"},
            "estimate_realism": {"type": "string",
                                 "description": "hours vs calendar; which waits set the pace"},
            "predictions": {"type": "array", "items": {"type": "object", "properties": {
                "statement": {"type": "string", "description": "binary, observable"},
                "p": {"type": "number"}, "p_user": {"type": "number"},
                "resolve_by": {"type": "string", "description": "YYYY-MM-DD"},
                "how": {"type": "string", "description": "how the user will check it"}}}},
            "acquiescence_note": {"type": "string",
                                  "description": "required when every probability is >= 0.5"},
            "argument": {"type": "string", "description": "pushback: the user's argument"},
            "changes": {"type": "object", "description": "revise: fields to change"},
            "new_evidence": {"type": "array", "items": {"type": "string"},
                             "description": "revise: C# claims or R# red-team runs"},
            "reason": {"type": "string"},
        },
        "required": ["action"],
    },
}


def _date(value: Any, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ToolError(f"{field} must be a date YYYY-MM-DD, got {value!r}") from None


def _prob(value: Any, field: str) -> float:
    try:
        p = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{field} must be a probability") from None
    if not P_MIN <= p <= P_MAX:
        raise ToolError(f"{field} must be between {P_MIN} and {P_MAX}; certainty is not "
                        "calibrated")
    return round(p, 3)


def validate_verdict(store: Store, project: Project, data: dict, today: dt.date,
                     check_predictions: bool = True) -> dict:
    out: dict[str, Any] = {}
    problems: list[str] = []
    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        problems.append(f"verdict must be one of {', '.join(VERDICTS)}")
    out["verdict"] = verdict
    out["thesis"] = str(data.get("thesis") or "").strip()
    if not out["thesis"]:
        problems.append("thesis: the bet in one sentence")
    rc = data.get("reference_class") or {}
    src = str(rc.get("source") or "").strip()
    if not (rc.get("name") and rc.get("base_rate") and src):
        problems.append("reference_class needs name, base_rate and source (outside view "
                        "first: name the class and its sourced base rate before the premortem)")
    elif src in base_rates.REFERENCE_CLASSES:
        rc = {**rc, "source_detail": base_rates.REFERENCE_CLASSES[src]["source"]}
    else:
        try:
            claim = research.get_claim(store, project.id, src)
        except ToolError:
            problems.append(f"reference_class.source {src!r} is neither a claim id nor a "
                            "base-rate key (see action=base_rates)")
        else:
            if claim["status"] != "active" or claim["label"] not in ("verified", "partial"):
                problems.append(f"reference_class.source C{claim['id']} is not a verified "
                                "claim; fetch and quote a source for the base rate")
            else:
                rc = {**rc, "source_detail": f"C{claim['id']}: {claim['text']}"}
    out["reference_class"] = rc
    try:
        out["p_success"] = _prob(data.get("p_success"), "p_success")
    except ToolError as exc:
        problems.append(str(exc))
    pre = data.get("premortem") or []
    if len(pre) < 3:
        problems.append("premortem: at least 3 ranked causes of failure")
    total = 0.0
    for i, item in enumerate(pre):
        if not str(item.get("cause") or "").strip():
            problems.append(f"premortem[{i}] needs a cause")
        try:
            total += float(item.get("p_given_failure"))
        except (TypeError, ValueError):
            problems.append(f"premortem[{i}].p_given_failure: share of failures (0-1)")
    if total > 1.05:
        problems.append("premortem shares are conditional on failure and must sum to <= 1")
    out["premortem"] = pre
    out["must_be_true"] = list(data.get("must_be_true") or [])
    if not out["must_be_true"]:
        problems.append("must_be_true: at least one assumption with test, cost, deadline, "
                        "kill_threshold")
    trip = list(data.get("tripwires") or [])
    if not trip:
        problems.append("tripwires: at least one dated kill/pivot threshold")
    out["tripwires"] = trip
    for key in ("builder_fit", "estimate_realism"):
        out[key] = str(data.get(key) or "").strip()
        if not out[key]:
            problems.append(f"{key} is required")
    preds = []
    items = (data.get("predictions") or []) if check_predictions else []
    for i, item in enumerate(items):
        try:
            when = _date(item.get("resolve_by"), f"predictions[{i}].resolve_by")
            if when <= today:
                raise ToolError(f"predictions[{i}].resolve_by must be in the future")
            pred = {"statement": str(item.get("statement") or "").strip(),
                    "p": _prob(item.get("p"), f"predictions[{i}].p"),
                    "resolve_by": when.isoformat(),
                    "how": str(item.get("how") or "").strip()}
            if item.get("p_user") is not None:
                pred["p_user"] = _prob(item.get("p_user"), f"predictions[{i}].p_user")
            if not pred["statement"] or not pred["how"]:
                raise ToolError(f"predictions[{i}] needs statement and how")
            preds.append(pred)
        except ToolError as exc:
            problems.append(str(exc))
    if not check_predictions:
        preds = list(data.get("predictions") or [])
    elif len(preds) < MIN_PREDICTIONS:
        problems.append(f"at least {MIN_PREDICTIONS} scoreable predictions (thesis test, top "
                        "premortem cause, time to first release, first traction threshold)")
    out["predictions"] = preds
    probs = [out.get("p_success", 0.0)] + [p["p"] for p in preds]
    if probs and min(probs) >= 0.5:
        note = str(data.get("acquiescence_note") or "").strip()
        if not note:
            problems.append("every probability is >= 0.5: re-examine for acquiescence, then "
                            "explain in acquiescence_note why that is right")
        out["acquiescence_note"] = note
    if problems:
        raise ToolError("the verdict is not ready", problems=problems)
    return out


def current(store: Store, project: Project) -> dict | None:
    art = store.latest(project.id, "verdict")
    return {"id": art.id, "at": art.created_at, **art.payload} if art else None


def add_predictions(store: Store, project: Project, preds: list[dict], origin: str) -> list[str]:
    ids = []
    now = store.now()
    with store.tx() as conn:
        for p in preds:
            ids.append("P" + str(conn.execute(
                "INSERT INTO predictions (project_id, statement, p_model, p_user, resolve_by,"
                " how, origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project.id, p["statement"], p["p"], p.get("p_user"), p["resolve_by"],
                 p["how"], origin, now)).lastrowid))
    return ids


class VerdictTool(BoundTool):
    def __init__(self, store_factory: Callable[[], Store], runner: Runner,
                 today: Callable[[], dt.date] = dt.date.today) -> None:
        super().__init__(store_factory)
        self._runner = runner
        self._today = today

    def act_base_rates(self, store: Store, project: Project, args: dict) -> dict:
        return {"reference_classes": base_rates.reference_class_table(),
                "note": "Cite a key as reference_class.source, or a verified C# claim for a "
                        "class that fits better. Reviewed " + base_rates.REVIEWED}

    def act_commit(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 5, what="the verdict")
        if current(store, project):
            raise ToolError("a verdict is already committed; use revise with new evidence")
        data = validate_verdict(store, project, args, self._today())
        data["version"] = 1
        ids = add_predictions(store, project, data["predictions"], "verdict v1")
        data["prediction_ids"] = ids
        art = store.add_artifact(project.id, project.phase, "verdict", PRODUCER, data)
        return {"verdict": data, "id": art.id,
                "rule": "Stored. Present it as is. If the user pushes back, call "
                        "action=pushback; only revise with new evidence."}

    def act_show(self, store: Store, project: Project, args: dict) -> dict:
        v = current(store, project)
        if v is None:
            raise ToolError("no verdict committed yet")
        return {"verdict": v, "history": len(store.artifacts(project.id, "verdict"))}

    def act_pushback(self, store: Store, project: Project, args: dict) -> dict:
        v = current(store, project)
        if v is None:
            raise ToolError("no verdict committed yet")
        argument = str(args.get("argument") or "").strip()
        store.add_artifact(project.id, project.phase, "pushback", PRODUCER,
                           {"argument": argument, "verdict_version": v["version"]})
        return {"verdict": {k: v[k] for k in ("verdict", "thesis", "p_success",
                                              "reference_class")},
                "rule": ("Restate the verdict once, with its strongest reason. Do not change "
                         "it for an argument alone: models flip under pushback about half the "
                         "time, often to a wrong answer. If the user cites a source, fetch it "
                         "and record it with idea_research(action=claim); a claim that passes "
                         "the quote check is new evidence for action=revise.")}

    def act_revise(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 5, what="revising the verdict")
        v = current(store, project)
        if v is None:
            raise ToolError("no verdict committed yet")
        refs = [str(r).strip() for r in args.get("new_evidence") or [] if str(r).strip()]
        reason = str(args.get("reason") or "").strip()
        if not refs or not reason:
            raise ToolError("revise needs new_evidence (C# claims or R# red-team runs recorded "
                            "after the verdict) and a reason")
        used = []
        for ref in refs:
            if ref.upper().startswith("R"):
                rid = parse_ref(ref, "R")
                runs = {a.id: a for a in store.artifacts(project.id, "redteam")}
                run = runs.get(rid)
                if run is None or run.created_at <= v["at"]:
                    raise ToolError(f"{ref} is not a red-team run made after the verdict")
                used.append(f"R{rid}: {run.payload.get('verdict')}")
                continue
            claim = research.get_claim(store, project.id, ref)
            if claim["created_at"] <= v["at"]:
                raise ToolError(f"C{claim['id']} existed before the verdict; it is not new "
                                "evidence")
            if claim["status"] != "active" or claim["label"] not in ("verified", "partial"):
                raise ToolError(f"C{claim['id']} is not a quote-checked claim")
            used.append(f"C{claim['id']}: {claim['text']}")
        changes = args.get("changes") or {}
        if not isinstance(changes, dict) or not changes:
            raise ToolError("revise needs changes: the fields that change")
        merged = {k: v[k] for k in v if k not in ("id", "at", "version", "prediction_ids",
                                                   "changed_because")}
        merged.update(changes)
        replaced = bool(changes.get("predictions"))
        data = validate_verdict(store, project, merged, self._today(),
                                check_predictions=replaced)
        new_preds = data["predictions"] if replaced else []
        data["version"] = v["version"] + 1
        data["changed_because"] = {"evidence": used, "reason": reason,
                                   "fields": sorted(changes)}
        data["prediction_ids"] = list(v.get("prediction_ids") or []) + add_predictions(
            store, project, new_preds, f"verdict v{data['version']}")
        art = store.add_artifact(project.id, project.phase, "verdict", PRODUCER, data)
        return {"verdict": data, "id": art.id}

    def act_redteam(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 5, what="the red team")
        job = Job(role="redteam", project_id=project.id, goal=REDTEAM_GOAL,
                  context=redteam_packet(store, project), toolsets=("web",))
        outcome = self._runner(job)
        if not outcome.ok:
            return {"redteam": "did not run", "reason": outcome.error,
                    "note": "The in-context verdict stands alone; say so to the user."}
        try:
            data = extract_json(outcome.text)
            if not isinstance(data, dict) or data.get("verdict") not in VERDICTS:
                raise ValueError("missing verdict")
        except ValueError as exc:
            return {"redteam": "unreadable", "reason": str(exc), "raw": outcome.text[:1500]}
        data["model"] = outcome.model
        art = store.add_artifact(project.id, project.phase, "redteam", PRODUCER, data)
        return {"redteam": f"R{art.id}", "result": data,
                "note": "Reconcile: if it changes your view, revise citing R#; otherwise say "
                        "why it does not."}


REDTEAM_GOAL = """You are an independent red-team critic. You see a one-page summary of an idea
and its evidence log, nothing of the conversation that produced it. Start from the outside view:
name a reference class and its base rate, then list the strongest reasons this will fail for
THIS builder. Be specific, not polite.

Reply with JSON only:
{"verdict": "go" | "go_with_conditions" | "pivot" | "kill", "p_success": 0.0-1.0,
 "reference_class": "...", "top_risks": ["...", "...", "..."], "note": "one paragraph"}"""


def redteam_packet(store: Store, project: Project) -> str:
    brief = store.latest(project.id, "brief")
    choice = store.latest(project.id, "choice")
    lines = [f"Idea: {project.idea}"]
    if brief:
        lines.append("Brief: " + json.dumps(brief.payload, ensure_ascii=False)[:2000])
    if choice:
        lines.append("Chosen variant: " + json.dumps(choice.payload, ensure_ascii=False)[:1500])
    lines.append("Builder profile: " + json.dumps(profile.effective(store, project),
                                                   ensure_ascii=False))
    lines.append("Evidence log:")
    for c in research.claims(store, project.id, active_only=True):
        lines.append(f"- C{c['id']} {research.claim_tag(c)} {c['text']}")
    return "\n".join(lines)
