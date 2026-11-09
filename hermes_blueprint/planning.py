"""Phase 6 plan (H6): A/H/W units, ranges, effort vs calendar computed in code, rules S1-S7.

The planner (a fresh subagent with a plugin-assembled context packet, or the chat model as a
fallback) proposes units; this module validates them and computes the totals itself, so a plan
cannot say "several months" for a single plugin or hide the waits that set the calendar.

Units: A = agent-bound (active hours), H = human-bound (active hours of your time), W = external
wait (calendar days).
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from . import base_rates, profile, research, verdict
from .common import BoundTool, ToolError, extract_json, require_phase
from .store import Project, Store
from .subagents import Job, Runner

PRODUCER = "idea_plan"
SHAPES = {
    "single_artifact": "one plugin, CLI, bot, static site or one-screen tool",
    "app": "a polished app or game",
    "multi_component": "several components (backend, frontend, deploy, ...)",
    "money_or_security": "real money, contracts or security-critical code",
    "physical_or_taste": "physical prototypes, brand or taste loops",
    "research": "an open research question",
}
MAX_A_UNIT_H = 16.0
SINGLE_ARTIFACT_A_P50 = 8.0
S2_A_P50 = 50.0
MONTH_DAYS = 30.0

RULES = """S1. A single plugin, CLI, bot, static site or one-screen tool built by an agent is hours,
    not weeks: agent-bound P50 <= 8 h, or name the unit that causes more (effort_driver).
S2. Agent-bound effort over ~50 h needs scope_reasons (novel algorithm, unseen codebase, money or
    security, hardware, many platforms); otherwise re-scope.
S3. Months appear only in calendar time and only because of named W or H items.
S4. Every estimate is a range (P10 < P90); novel units need P90 >= 1.5 x P50.
S5. Done includes verification: plans with A units include H review/test units.
S6. W items that depend on nothing start on day 1 (start_now: true).
S7. Where your ledger has >= 3 actuals for a class, its numbers replace the base rate; a P50
    outside the ledger's P10-P90 needs a note.
Units: A agent-bound in active hours (<= 16 h each, split bigger ones) with ref_class and
acceptance criteria; H human-bound in active hours of the user's time; W external waits in
calendar days. Every green-light criterion becomes a gate with a kill threshold."""

PLAN_SCHEMA: dict[str, Any] = {
    "name": "idea_plan",
    "description": (
        "Blueprint build plan for the chosen idea (phase 6 Plan). Work units classed A "
        "(agent-bound hours), H (human-bound hours) or W (external wait days) with "
        "P10/P50/P90; code validates rules S1-S7 and computes effort vs calendar. Actions: "
        "draft (an isolated planner subagent writes it from the stored project), submit "
        "(validate and store a plan JSON), show, rules."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["draft", "submit", "show", "rules"]},
            "plan": {
                "type": "object",
                "description": "submit: {shape, units: [{id, title, class A|H|W, ref_class "
                               "(A), p10, p50, p90, depends_on, start_now, acceptance, "
                               "multipliers: [{name, reason}], novel, note}], gates: [{after, "
                               "check, kill_if}], effort_driver, scope_reasons}",
            },
        },
        "required": ["action"],
    },
}


def _num(value: Any, where: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{where} must be a number") from None
    if n <= 0:
        raise ToolError(f"{where} must be positive")
    return n


PLAN_KEYS = ("shape", "units", "gates", "effort_driver", "scope_reasons")


def _as_object(value: Any) -> Any:
    """Models sometimes send an object or list as a JSON string; parse it back."""
    if isinstance(value, str) and value.strip()[:1] in ("{", "["):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def plan_from_args(args: dict) -> Any:
    """The plan from tool args: ``plan`` (object or JSON string), a doubly wrapped
    ``{"plan": {"plan": ...}}``, or the plan's keys given at the top level."""
    plan = _as_object(args.get("plan"))
    if isinstance(plan, dict) and "units" not in plan and isinstance(plan.get("plan"), (dict, str)):
        plan = _as_object(plan["plan"])
    if plan is None and "units" in args:
        plan = {k: args[k] for k in PLAN_KEYS if k in args}
    return plan


def validate_plan(plan: Any, prof: dict[str, Any], rates: list[dict[str, Any]],
                  ledger: dict[str, dict[str, Any]]) -> tuple[dict, dict]:
    """Return ``(normalized plan, computed totals)`` or raise ToolError with every problem."""
    plan = _as_object(plan)
    if not isinstance(plan, dict):
        raise ToolError("plan must be an object: {shape, units, gates, effort_driver, "
                        "scope_reasons}")
    for key in ("units", "gates", "scope_reasons"):
        if isinstance(plan.get(key), str):  # a list sent as a JSON string
            plan = {**plan, key: _as_object(plan[key])}
    problems: list[str] = []
    shape = plan.get("shape")
    if shape not in SHAPES:
        problems.append(f"shape must be one of {', '.join(SHAPES)}")
    raw_units = plan.get("units") or []
    if not isinstance(raw_units, list) or not raw_units:
        raise ToolError("plan needs units", problems=["units: a list of work units"])
    rate_by = {r["class"]: r for r in rates}
    units: list[dict[str, Any]] = []
    ids: set[str] = set()
    for i, u in enumerate(raw_units):
        where = f"units[{i}]"
        try:
            if not isinstance(u, dict):
                raise ToolError(f"{where} must be an object")
            uid = str(u.get("id") or f"U{i + 1}").strip()
            if uid in ids:
                raise ToolError(f"{where}: duplicate id {uid}")
            ids.add(uid)
            cls = str(u.get("class") or "").upper()
            if cls not in ("A", "H", "W"):
                raise ToolError(f"{uid}: class must be A, H or W")
            p10, p50, p90 = (_num(u.get(k), f"{uid}.{k}") for k in ("p10", "p50", "p90"))
            if not p10 <= p50 <= p90:
                raise ToolError(f"{uid}: needs p10 <= p50 <= p90")
            if p90 <= p10:
                raise ToolError(f"{uid}: an estimate is a range (S4); p90 must exceed p10")
            unit = {"id": uid, "title": str(u.get("title") or "").strip(), "class": cls,
                    "p10": p10, "p50": p50, "p90": p90,
                    "depends_on": [str(d) for d in u.get("depends_on") or []],
                    "start_now": bool(u.get("start_now")),
                    "acceptance": [str(a) for a in u.get("acceptance") or [] if str(a).strip()],
                    "multipliers": list(u.get("multipliers") or []),
                    "novel": bool(u.get("novel")), "note": str(u.get("note") or "").strip(),
                    "ref_class": str(u.get("ref_class") or "")}
            units.append(unit)
            if not unit["title"]:
                raise ToolError(f"{uid}: title is required")
            if unit["novel"] and p90 < 1.5 * p50:
                raise ToolError(f"{uid}: novel work needs p90 >= 1.5 x p50 (S4)")
            if cls == "A":
                _check_a_unit(unit, rate_by, ledger)
        except ToolError as exc:
            problems.append(str(exc))
    by_id = {u["id"]: u for u in units}
    for u in units:
        bad = [d for d in u["depends_on"] if d not in by_id and d not in ids]
        if bad:
            problems.append(f"{u['id']}: depends on unknown units {bad}")
        if u["class"] == "W" and not u["depends_on"] and not u["start_now"]:
            problems.append(f"{u['id']}: a wait that depends on nothing starts on day 1 "
                            "(start_now: true) (S6)")
    order = _topo(units, problems)
    gates = [g for g in plan.get("gates") or [] if isinstance(g, dict)]
    if not gates or not all(g.get("check") and g.get("kill_if") for g in gates):
        problems.append("gates: at least one {after, check, kill_if}; every green-light "
                        "criterion becomes a gate with a kill threshold")
    a_units = [u for u in units if u["class"] == "A"]
    if a_units and not any(u["class"] == "H" for u in units):
        problems.append("plans with agent work need H units for review and real-use testing "
                        "(S5)")
    computed = compute(units, order, prof) if order is not None else {}
    a_p50 = sum(u["p50"] for u in a_units)
    driver = str(plan.get("effort_driver") or "").strip()
    if driver.upper() in by_id and driver not in by_id:
        driver = driver.upper()
    a_ids = [u["id"] for u in a_units]
    if shape == "single_artifact" and a_p50 > SINGLE_ARTIFACT_A_P50 and driver not in a_ids:
        problems.append(f"S1: a single artifact with {a_p50:g} agent hours (more than "
                        f"{SINGLE_ARTIFACT_A_P50:g}); set effort_driver to the id of the unit that "
                        f"causes it (an agent unit: {', '.join(a_ids)}), or split the scope")
    reasons = [str(r) for r in plan.get("scope_reasons") or [] if str(r).strip()]
    if a_p50 > S2_A_P50 and not reasons:
        problems.append(f"S2: {a_p50:g} agent hours needs scope_reasons, or re-scope")
    if computed and computed["calendar_days"]["p50"] > MONTH_DAYS:
        wait_share = computed["wait_days_on_path"] / computed["calendar_days"]["p50"]
        if wait_share < 0.5:
            problems.append("S3: the calendar runs past a month mainly on active work; months "
                            "come only from named waits. Re-check the A estimates or the "
                            "hours per day")
    if problems:
        raise ToolError("the plan does not pass the checks", problems=problems,
                        rules=RULES)
    clean = {"shape": shape, "units": [by_id[i] for i in order], "gates": gates,
             "effort_driver": driver, "scope_reasons": reasons}
    return clean, computed


def _check_a_unit(unit: dict, rate_by: dict, ledger: dict) -> None:
    uid = unit["id"]
    if unit["p50"] > MAX_A_UNIT_H:
        raise ToolError(f"{uid}: {unit['p50']:g} h is over {MAX_A_UNIT_H:g} h; split it")
    if unit["ref_class"] not in rate_by:
        raise ToolError(f"{uid}: ref_class must be one of {', '.join(rate_by)}")
    if not unit["acceptance"]:
        raise ToolError(f"{uid}: needs acceptance criteria")
    rate = rate_by[unit["ref_class"]]
    factor = 1.0
    for m in unit["multipliers"]:
        name = (m or {}).get("name")
        if name not in base_rates.MULTIPLIERS or not str((m or {}).get("reason") or "").strip():
            raise ToolError(f"{uid}: multipliers need a known name "
                            f"({', '.join(base_rates.MULTIPLIERS)}) and a reason")
        factor *= base_rates.MULTIPLIERS[name][1]
    if unit["p50"] > rate["p90_h"] * factor:
        raise ToolError(f"{uid}: P50 {unit['p50']:g} h is above the {unit['ref_class']} P90 "
                        f"({rate['p90_h']:g} h, {rate['basis']}); name a multiplier with a "
                        "reason, split the unit, or pick the right class")
    stats = ledger.get(unit["ref_class"])
    if stats and stats["n"] >= 3 and not (stats["p10_h"] <= unit["p50"] <= stats["p90_h"]):
        if not unit["note"]:
            raise ToolError(f"{uid}: your ledger says {unit['ref_class']} takes "
                            f"{stats['p10_h']:g}-{stats['p90_h']:g} h (n = {stats['n']}); a P50 "
                            "outside that needs a note (S7)")


def _topo(units: list[dict], problems: list[str]) -> list[str] | None:
    deps = {u["id"]: [d for d in u["depends_on"]] for u in units}
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(uid: str) -> bool:
        if state.get(uid) == 1:
            return False
        if state.get(uid) == 2 or uid not in deps:
            return True
        state[uid] = 1
        for d in deps[uid]:
            if not visit(d):
                return False
        state[uid] = 2
        order.append(uid)
        return True

    for uid in deps:
        if not visit(uid):
            problems.append(f"dependency cycle through {uid}")
            return None
    return order


def compute(units: list[dict], order: list[str], prof: dict[str, Any]) -> dict[str, Any]:
    hpd = float(prof.get("hours_per_day") or 5)
    dpw = float(prof.get("days_per_week") or 5)
    par = max(1.0, float(prof.get("parallel_agents") or 1))
    speedup = min(2.0, 1.0 + 0.3 * (par - 1))  # ~1.6x seen with 3 parallel worktrees
    week = 7.0 / dpw
    by_id = {u["id"]: u for u in units}

    def days(u: dict, key: str) -> float:
        if u["class"] == "W":
            return u[key]
        return u[key] / hpd * week

    out: dict[str, Any] = {"effort_hours": {}, "calendar_days": {}}
    for key in ("p10", "p50", "p90"):
        a = sum(u[key] for u in units if u["class"] == "A")
        h = sum(u[key] for u in units if u["class"] == "H")
        out["effort_hours"][key] = {"agent": round(a, 1), "human": round(h, 1),
                                    "total": round(a + h, 1)}
        finish: dict[str, float] = {}
        for uid in order:
            u = by_id[uid]
            start = max((finish[d] for d in u["depends_on"] if d in finish), default=0.0)
            finish[uid] = start + days(u, key)
        path = max(finish.values(), default=0.0)
        workload = (a / speedup + h) / hpd * week
        out["calendar_days"][key] = round(max(path, workload), 1)
        if key == "p50":
            out["critical_path_days"] = round(path, 1)
            out["workload_days"] = round(workload, 1)
            end = max(finish, key=finish.get) if finish else None
            chain, wait_days = [], 0.0
            while end:
                u = by_id[end]
                chain.append(end)
                if u["class"] == "W":
                    wait_days += u["p50"]
                preds = [d for d in u["depends_on"] if d in finish]
                end = max(preds, key=finish.get) if preds else None
            out["critical_path"] = list(reversed(chain))
            out["wait_days_on_path"] = round(wait_days, 1)
    drivers = sorted(units, key=lambda u: days(u, "p50"), reverse=True)[:3]
    out["calendar_drivers"] = [f"{u['id']} {u['title']} ({u['class']}, "
                               f"{days(u, 'p50'):.1f} d)" for u in drivers]
    out["start_today"] = [u["id"] for u in units if u["start_now"] or (
        not u["depends_on"] and u["class"] != "A")]
    out["assumptions"] = {"hours_per_day": hpd, "days_per_week": dpw,
                          "parallel_agents": par}
    return out


def render_plan(project: Project, plan: dict, computed: dict, drafted_by: str) -> str:
    unit_word = {"A": "h", "H": "h", "W": "d"}
    lines = [f"# Plan: {project.title}", "",
             f"Shape: {plan['shape']} ({SHAPES.get(plan['shape'], '')}). Drafted by "
             f"{drafted_by}; checked against rules S1-S7.", "",
             "| Unit | Class | P10 / P50 / P90 | Depends on | Start today | Acceptance |",
             "|---|---|---|---|---|---|"]
    for u in plan["units"]:
        w = unit_word[u["class"]]
        acc = "; ".join(u["acceptance"]).replace("|", "/") or "-"
        lines.append(f"| {u['id']} {u['title']} | {u['class']} | {u['p10']:g} / {u['p50']:g} "
                     f"/ {u['p90']:g} {w} | {', '.join(u['depends_on']) or '-'} | "
                     f"{'yes' if u['id'] in computed['start_today'] else '-'} | {acc} |")
    e = computed["effort_hours"]
    c = computed["calendar_days"]
    lines += ["",
              f"**Effort:** agent {e['p50']['agent']:g} h (P10-P90 {e['p10']['agent']:g}-"
              f"{e['p90']['agent']:g} h), your time {e['p50']['human']:g} h.",
              f"**Calendar:** {c['p50']:g} days (P10-P90 {c['p10']:g}-{c['p90']:g}), at "
              f"{computed['assumptions']['hours_per_day']:g} h/day.",
              "**Top calendar drivers:** " + "; ".join(computed["calendar_drivers"]) + ".",
              "", "## Gates", ""]
    for g in plan["gates"]:
        lines.append(f"- After {g.get('after') or 'start'}: {g['check']}. Kill or pivot if "
                     f"{g['kill_if']}.")
    if plan.get("scope_reasons"):
        lines += ["", "Why this is bigger than a quick build: "
                  + "; ".join(plan["scope_reasons"]) + "."]
    return "\n".join(lines) + "\n"


PLANNER_GOAL = """You are the planner for a solo builder who builds with AI coding agents. Turn
the chosen idea into work units and estimates. You get the stored project facts, the builder
profile, the base-rate table and the rules. Estimate agent work from the reference class, never
in human-team weeks. Put waits (store review, approvals, testers, other people) in W units and
start them on day 1. Include H units for decisions, review and real-use testing.

Reply with JSON only, matching:
{"shape": "...", "units": [{"id": "U1", "title": "...", "class": "A", "ref_class": "...",
  "p10": 0.5, "p50": 1, "p90": 3, "depends_on": [], "start_now": true,
  "acceptance": ["..."], "multipliers": [], "novel": false, "note": ""}],
 "gates": [{"after": "U3", "check": "...", "kill_if": "..."}],
 "effort_driver": "", "scope_reasons": []}"""


def planner_packet(store: Store, project: Project, prof: dict, rates: list[dict]) -> str:
    parts = [f"Idea: {project.idea}"]
    for kind in ("brief", "choice", "deepdive"):
        art = store.latest(project.id, kind)
        if art:
            parts.append(f"{kind}: " + json.dumps(art.payload, ensure_ascii=False)[:2500])
    v = verdict.current(store, project)
    if v:
        parts.append("Critic verdict: " + json.dumps(
            {k: v.get(k) for k in ("verdict", "thesis", "tripwires", "must_be_true",
                                   "estimate_realism", "builder_fit")},
            ensure_ascii=False)[:2500])
    facts = [f"- C{c['id']} {research.claim_tag(c)} {c['text']}"
             for c in research.claims(store, project.id, active_only=True)]
    if facts:
        parts.append("Evidence:\n" + "\n".join(facts[:40]))
    parts.append("Builder profile: " + json.dumps(prof, ensure_ascii=False))
    parts.append("Shapes: " + json.dumps(SHAPES))
    parts.append("Unit classes (active hours): " + json.dumps(rates, ensure_ascii=False))
    parts.append("Multipliers: " + json.dumps(base_rates.MULTIPLIERS))
    parts.append("Known waits: " + json.dumps(base_rates.WAIT_CATALOG))
    parts.append("Rules:\n" + RULES)
    return "\n\n".join(parts)


class PlanTool(BoundTool):
    def __init__(self, store_factory: Callable[[], Store], runner: Runner) -> None:
        super().__init__(store_factory)
        self._runner = runner

    def _inputs(self, store: Store, project: Project) -> tuple[dict, list, dict]:
        return (profile.effective(store, project), profile.class_rates(store),
                profile.ledger_stats(store))

    def _store_plan(self, store: Store, project: Project, plan: dict, drafted_by: str) -> dict:
        prof, rates, ledger = self._inputs(store, project)
        clean, computed = validate_plan(plan, prof, rates, ledger)
        markdown = render_plan(project, clean, computed, drafted_by)
        art = store.add_artifact(project.id, project.phase, "plan", PRODUCER,
                                 {"plan": clean, "computed": computed, "drafted_by": drafted_by,
                                  "markdown": markdown})
        return {"plan_id": art.id, "computed": computed, "markdown": markdown,
                "next": "Show the plan. Then idea_phase(action=advance) to finish, and tell "
                        "the user about /idea handoff (kanban cards and a project folder)."}

    def act_rules(self, store: Store, project: Project, args: dict) -> dict:
        prof, rates, ledger = self._inputs(store, project)
        return {"rules": RULES, "shapes": SHAPES, "unit_classes": rates,
                "multipliers": base_rates.MULTIPLIERS, "waits": base_rates.WAIT_CATALOG,
                "profile": prof}

    def act_draft(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 6, what="the plan")
        if verdict.current(store, project) is None:
            raise ToolError("no critic verdict stored; phase 5 comes first")
        prof, rates, _ = self._inputs(store, project)
        job = Job(role="planner", project_id=project.id, goal=PLANNER_GOAL,
                  context=planner_packet(store, project, prof, rates), toolsets=("web",))
        outcome = self._runner(job)
        if not outcome.ok:
            return {"draft": "planner did not run", "reason": outcome.error,
                    "next": "Write the plan yourself from action=rules and submit it; say "
                            "that the isolated planner was unavailable."}
        try:
            draft = extract_json(outcome.text)
        except ValueError as exc:
            return {"draft": "unreadable", "reason": str(exc), "raw": outcome.text[:3000],
                    "next": "Fix it into the plan JSON and submit."}
        try:
            return {"draft": "stored",
                    **self._store_plan(store, project, draft, f"planner ({outcome.model})")}
        except ToolError as exc:
            return {"draft": "needs fixes", "problems": exc.data.get("problems", [str(exc)]),
                    "plan": draft, "next": "Fix the problems and submit the plan."}

    def act_submit(self, store: Store, project: Project, args: dict) -> dict:
        require_phase(project, 6, what="the plan")
        if verdict.current(store, project) is None:
            raise ToolError("no critic verdict stored; phase 5 comes first")
        return self._store_plan(store, project, plan_from_args(args), "the chat model")

    def act_show(self, store: Store, project: Project, args: dict) -> dict:
        art = store.latest(project.id, "plan")
        if art is None:
            raise ToolError("no plan yet")
        return {"plan_id": art.id, **art.payload}
