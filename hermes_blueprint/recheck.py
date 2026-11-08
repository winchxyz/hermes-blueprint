"""Re-checks after the handoff (H8): kanban progress, predictions scored, estimates vs actuals.

The recheck gives the critic real data for the thesis-vs-tuning question: which predictions came
true (Brier score, model vs user), which units ran over and whether a wait or the work itself set
the calendar. Actuals feed the velocity ledger, so the next plan starts from this builder's own
numbers.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from . import handoff, profile, verdict
from .common import BoundTool, ToolError, parse_ref
from .store import Project, Store

Dispatch = Callable[[str, dict], str]
SMALL_N = 20

RECHECK_SCHEMA: dict[str, Any] = {
    "name": "idea_recheck",
    "description": (
        "Blueprint re-check of a planned idea after building started: kanban card progress, "
        "due predictions, Brier scores (model vs user), estimate vs actual per unit, verdict "
        "tripwires. Actions: overview (all planned projects), report, resolve (prediction P# "
        "outcome 1/0/void), actual (unit U# "
        "actual active hours, or days for waits). Then judge: does the data disconfirm the "
        "thesis or only the tuning?"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["overview", "report", "resolve", "actual"]},
            "project": {"type": "string",
                        "description": "project id or slug; default: the one bound to this chat"},
            "prediction": {"type": "string", "description": "resolve: P# id"},
            "outcome": {"type": "string", "enum": ["1", "0", "void"]},
            "unit": {"type": "string", "description": "actual: unit id from the plan"},
            "value": {"type": "number",
                      "description": "actual: active hours (A/H) or calendar days (W)"},
            "source": {"type": "string", "enum": ["user", "kanban"]},
        },
        "required": ["action"],
    },
}


def brier(rows: list[tuple[float, int]]) -> float | None:
    if not rows:
        return None
    return round(sum((p - o) ** 2 for p, o in rows) / len(rows), 3)


def scores(preds: list[dict[str, Any]]) -> dict[str, Any]:
    done = [p for p in preds if p["outcome"] in (0, 1)]
    model = [(p["p_model"], p["outcome"]) for p in done]
    user = [(p["p_user"], p["outcome"]) for p in done if p["p_user"] is not None]
    out = {"resolved": len(done), "brier_model": brier(model), "brier_user": brier(user),
           "always_50pct_baseline": 0.25 if done else None,
           "hits": sum((p >= 0.5) == bool(o) for p, o in model)}
    if len(done) < SMALL_N:
        out["warning"] = (f"only {len(done)} resolved predictions; below ~{SMALL_N} show hits "
                          "and misses, not calibration conclusions")
    return out


class RecheckTool(BoundTool):
    needs_project = False

    def __init__(self, store_factory: Callable[[], Store], dispatch: Dispatch,
                 today: Callable[[], dt.date] = dt.date.today) -> None:
        super().__init__(store_factory)
        self._dispatch = dispatch
        self._today = today

    @staticmethod
    def _target(store: Store, project: Project | None, args: dict) -> Project:
        ref = str(args.get("project") or "").strip().lstrip("#")
        if ref:
            try:
                return store.get_project(ref)
            except KeyError:
                raise ToolError(f"no project {ref!r}") from None
        if project is None:
            raise ToolError("no project bound to this chat; pass project (see action=overview)")
        return project

    def act_overview(self, store: Store, project: Project | None, args: dict) -> dict:
        today = self._today().isoformat()
        rows = []
        for p in store.list_projects():
            if p.status != "planned":
                continue
            preds = handoff.predictions(store, p.id)
            rows.append({"id": p.id, "slug": p.slug, "title": p.title,
                         "cards": len(handoff.cards(store, p.id)),
                         "predictions_due": sum(x["outcome"] is None and x["resolve_by"] <= today
                                                for x in preds)})
        return {"planned_projects": rows,
                "next": "Call action=report with project=<id> for each one that has work due."}

    @staticmethod
    def _plan(store: Store, project: Project) -> dict:
        plan = handoff.plan_payload(store, project)
        if plan is None:
            raise ToolError("no plan stored; rechecks start after phase 6")
        return plan

    def act_report(self, store: Store, project: Project | None, args: dict) -> dict:
        project = self._target(store, project, args)
        plan = self._plan(store, project)
        today = self._today().isoformat()
        card_ids = handoff.cards(store, project.id)
        recorded = {a["unit_id"]: a for a in profile.actuals(store)
                    if a["project_id"] == project.id}
        units = []
        for u in plan["plan"]["units"]:
            row: dict[str, Any] = {"unit": u["id"], "title": u["title"], "class": u["class"],
                                   "p50": u["p50"], "p90": u["p90"]}
            if u["id"] in card_ids:
                row["card"] = card_ids[u["id"]]
                row.update(handoff.card_status(self._dispatch, card_ids[u["id"]]))
            if u["id"] in recorded:
                actual = recorded[u["id"]]["actual"]
                row["actual"] = actual
                row["ratio"] = round(actual / u["p50"], 2)
                row["inside_p10_p90"] = u["p10"] <= actual <= u["p90"]
            units.append(row)
        preds = handoff.predictions(store, project.id)
        due = [{"id": f"P{p['id']}", "statement": p["statement"], "p": p["p_model"],
                "by": p["resolve_by"], "how": p["how"]}
               for p in preds if p["outcome"] is None and p["resolve_by"] <= today]
        v = verdict.current(store, project) or {}
        trips = [t for t in v.get("tripwires") or [] if str(t.get("by") or "9999") <= today]
        with_actual = [r for r in units if "actual" in r]
        return {
            "project": {"id": project.id, "title": project.title, "status": project.status},
            "units": units,
            "progress": {"cards": len(card_ids),
                         "done": sum(r.get("status") == "done" for r in units)},
            "estimates": {"with_actuals": len(with_actual),
                          "inside_range": sum(bool(r["inside_p10_p90"]) for r in with_actual),
                          "target": "about 80% inside P10-P90"},
            "predictions_due": due, "scores": scores(preds), "tripwires_due": trips,
            "verdict": {k: v.get(k) for k in ("verdict", "thesis", "p_success")},
            "next": "Ask the user for due outcomes (resolve) and actual hours (actual). Then "
                    "judge thesis vs tuning: an A-unit miss is tuning; an unforeseen wait or a "
                    "failed thesis test is planning or thesis.",
        }

    def act_resolve(self, store: Store, project: Project | None, args: dict) -> dict:
        project = self._target(store, project, args)
        pid = parse_ref(args.get("prediction"), "P")
        outcome = str(args.get("outcome") or "")
        if outcome not in ("1", "0", "void"):
            raise ToolError("outcome must be 1 (happened), 0 (did not) or void")
        with store.tx() as conn:
            row = conn.execute("SELECT outcome FROM predictions WHERE id = ? AND project_id = ?",
                               (pid, project.id)).fetchone()
            if row is None:
                raise ToolError(f"no prediction P{pid} in this project")
            if row[0] is not None:
                raise ToolError(f"P{pid} is already resolved")
            value = -1 if outcome == "void" else int(outcome)
            conn.execute("UPDATE predictions SET outcome = ?, resolved_at = ? WHERE id = ?",
                         (value, store.now(), pid))
        return {"prediction": f"P{pid}", "outcome": outcome,
                "scores": scores(handoff.predictions(store, project.id))}

    def act_actual(self, store: Store, project: Project | None, args: dict) -> dict:
        project = self._target(store, project, args)
        plan = self._plan(store, project)
        units = {u["id"]: u for u in plan["plan"]["units"]}
        uid = str(args.get("unit") or "").strip()
        if uid not in units:
            raise ToolError(f"unknown unit {uid!r}", units=sorted(units))
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            raise ToolError("value: actual active hours (A/H) or days (W)") from None
        if value <= 0:
            raise ToolError("value must be positive")
        u = units[uid]
        with store.tx() as conn:
            conn.execute("DELETE FROM actuals WHERE project_id = ? AND unit_id = ?",
                         (project.id, uid))
            conn.execute("INSERT INTO actuals (project_id, unit_id, unit_class, ref_class,"
                         " estimate_p50, actual, source, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (project.id, uid, u["class"], u.get("ref_class") or "", u["p50"], value,
                          args.get("source") or "user", store.now()))
        return {"unit": uid, "estimate_p50": u["p50"], "actual": value,
                "ratio": round(value / u["p50"], 2),
                "inside_p10_p90": u["p10"] <= value <= u["p90"],
                "ledger": profile.ledger_stats(store).get(u.get("ref_class") or "", {})}
