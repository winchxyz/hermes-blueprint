"""Builder profile (H5) and velocity ledger (H7).

The profile says who will build the thing: team, agents, hours, skills, accounts, audience,
budget. It is stored once per user, shown and confirmed at the start of each brainstorm (the
confirmation is snapshotted into the project, so phase 1 cannot end without it), and every later
phase reads it. The velocity ledger holds actual hours per finished unit; once a unit class has
3 or more actuals, its numbers replace the base rate (sanity rule S7).
"""
from __future__ import annotations

import statistics
from typing import Any

from . import base_rates
from .common import BoundTool, ToolError
from .store import Project, Store

PRODUCER = "idea_profile"
KEY = "builder_profile"

FIELDS: dict[str, tuple[type | tuple[type, ...], str]] = {
    "team": (str, "solo | pair | team(n)"),
    "agents": (list, "coding agents used, e.g. [hermes, claude-code, codex]"),
    "parallel_agents": ((int, float), "typical concurrent agent sessions"),
    "hours_per_day": ((int, float), "engaged hours on an active day"),
    "days_per_week": ((int, float), "active days per week"),
    "skills": (list, "where the human can verify fast"),
    "weak_spots": (list, "where verification is slow"),
    "hated_tasks": (list, "tasks that predict abandonment (marketing, support, ...)"),
    "accounts_ready": (list, "github, app-store, play-console, steam, stripe, ..."),
    "distribution": (list, "audience assets with sizes, past launches"),
    "budget_usd": (dict, "{one_time, monthly}"),
    "goal": (str, "fun | learning | portfolio | income"),
    "jurisdiction": (str, "country, for payments, tax and regulation"),
}
REQUIRED = ("team", "agents", "hours_per_day")
DEFAULTS = {"parallel_agents": 1, "days_per_week": 5}

PROFILE_SCHEMA: dict[str, Any] = {
    "name": "idea_profile",
    "description": (
        "Blueprint builder profile and velocity ledger: who builds the idea (team, coding "
        "agents, hours per day, skills, accounts, audience, budget). Actions: get, set "
        "(merge fields), confirm (snapshot into this project after the user agreed; needed to "
        "finish phase 1), ledger (actual hours per unit class vs base rates)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["get", "set", "confirm", "ledger"]},
            "profile": {"type": "object", "description": "set: fields to merge. "
                        + "; ".join(f"{k}: {v[1]}" for k, v in FIELDS.items())},
            "assumed": {"type": "array", "items": {"type": "string"},
                        "description": "confirm: fields filled by default, labelled assumptions."},
        },
        "required": ["action"],
    },
}


def load(store: Store) -> dict[str, Any]:
    return store.kv_get(KEY, {"version": 0, "fields": {}})


def validate(fields: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in FIELDS:
            raise ToolError(f"unknown profile field {key!r}", fields=list(FIELDS))
        kind = FIELDS[key][0]
        if isinstance(value, str) and kind is list:
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, kind) or isinstance(value, bool):
            raise ToolError(f"{key} should be {FIELDS[key][1]}")
        if key in ("hours_per_day", "parallel_agents", "days_per_week") and value <= 0:
            raise ToolError(f"{key} must be positive")
        if key == "hours_per_day" and value > 16:
            raise ToolError("hours_per_day above 16 is not a sustainable plan")
        clean[key] = value
    return clean


def used_profile(store: Store, project: Project) -> dict[str, Any] | None:
    art = store.latest(project.id, "profile_used")
    return art.payload if art else None


def effective(store: Store, project: Project | None) -> dict[str, Any]:
    """The profile the project confirmed, else the user's current one, with defaults."""
    snap = used_profile(store, project) if project else None
    fields = dict(snap["fields"]) if snap else dict(load(store)["fields"])
    for key, value in DEFAULTS.items():
        fields.setdefault(key, value)
    return fields


# velocity ledger ------------------------------------------------------------------------------

def actuals(store: Store) -> list[dict[str, Any]]:
    with store.tx() as conn:
        rows = conn.execute("SELECT project_id, unit_id, unit_class, ref_class, estimate_p50,"
                            " actual, source, at FROM actuals ORDER BY id").fetchall()
    return [{"project_id": r[0], "unit_id": r[1], "unit_class": r[2], "ref_class": r[3],
             "estimate_p50": r[4], "actual": r[5], "source": r[6], "at": r[7]} for r in rows]


def _quantile(values: list[float], q: float) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo), 2)


def ledger_stats(store: Store) -> dict[str, dict[str, Any]]:
    """Per reference class: n, P10/P50/P90 of actual active hours (A units only)."""
    groups: dict[str, list[float]] = {}
    for row in actuals(store):
        if row["unit_class"] == "A" and row["ref_class"]:
            groups.setdefault(row["ref_class"], []).append(float(row["actual"]))
    return {k: {"n": len(v), "p10_h": _quantile(v, 0.1), "p50_h": round(statistics.median(v), 2),
                "p90_h": _quantile(v, 0.9)} for k, v in groups.items()}


def class_rates(store: Store) -> list[dict[str, Any]]:
    """Base-rate table with ledger overrides where n >= 3 (S7)."""
    stats = ledger_stats(store)
    rows = []
    for row in base_rates.unit_class_table():
        s = stats.get(row["class"])
        if s and s["n"] >= 3:
            row = {**row, "p10_h": s["p10_h"], "p50_h": s["p50_h"], "p90_h": s["p90_h"],
                   "basis": f"from your ledger: n = {s['n']}"}
        rows.append(row)
    return rows


class ProfileTool(BoundTool):
    needs_project = False

    def act_get(self, store: Store, project: Project | None, args: dict) -> dict:
        prof = load(store)
        missing = [k for k in REQUIRED if k not in prof["fields"]]
        reply = {"profile": prof["fields"], "version": prof["version"],
                 "missing_required": missing,
                 "fields": {k: v[1] for k, v in FIELDS.items()}}
        if project is not None:
            reply["confirmed_for_project"] = bool(used_profile(store, project))
        return reply

    def act_set(self, store: Store, project: Project | None, args: dict) -> dict:
        fields = args.get("profile")
        if not isinstance(fields, dict) or not fields:
            raise ToolError("set needs profile: {field: value}")
        prof = load(store)
        merged = {**prof["fields"], **validate(fields)}
        prof = {"version": prof["version"] + 1, "fields": merged}
        store.kv_set(KEY, prof)
        return {"profile": merged, "version": prof["version"],
                "missing_required": [k for k in REQUIRED if k not in merged]}

    def act_confirm(self, store: Store, project: Project | None, args: dict) -> dict:
        if project is None:
            raise ToolError("no project in this chat to confirm the profile for")
        prof = load(store)
        missing = [k for k in REQUIRED if k not in prof["fields"]]
        if missing:
            raise ToolError("ask the user for the missing fields first (at most three "
                            "questions), then set them", missing=missing)
        assumed = [str(a) for a in args.get("assumed") or []]
        snap = {"version": prof["version"], "fields": prof["fields"], "assumed": assumed}
        store.add_artifact(project.id, project.phase, "profile_used", PRODUCER, snap)
        return {"confirmed": snap}

    def act_ledger(self, store: Store, project: Project | None, args: dict) -> dict:
        rows = actuals(store)
        return {"unit_classes": class_rates(store), "ledger": ledger_stats(store),
                "actuals_recorded": len(rows),
                "note": "Classes with n >= 3 use your own numbers (rule S7)."}
