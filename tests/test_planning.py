"""Phase 6: plan rules S1-S7 and effort vs calendar computed in code."""
from __future__ import annotations

import json

import pytest

from hermes_blueprint import planning, profile
from hermes_blueprint.common import ToolError

PROFILE = {"hours_per_day": 5, "days_per_week": 5, "parallel_agents": 1}


def unit(uid, cls, p10, p50, p90, **kw):
    base = {"id": uid, "title": f"unit {uid}", "class": cls, "p10": p10, "p50": p50, "p90": p90}
    if cls == "A":
        base.update(ref_class="scaffold", acceptance=["works"])
    base.update(kw)
    return base


def plugin_plan(**over):
    plan = {
        "shape": "single_artifact",
        "units": [
            unit("U1", "A", 0.5, 1, 3),
            unit("U2", "A", 0.5, 1.5, 4, ref_class="api_integration", depends_on=["U1"]),
            unit("U3", "H", 0.5, 1, 2, depends_on=["U2"]),
            unit("U4", "W", 1, 3, 10, start_now=True),
        ],
        "gates": [{"after": "U2", "check": "a real call works", "kill_if": "API refuses"}],
    }
    plan.update(over)
    return plan


def check(plan, ledger=None, prof=PROFILE):
    rates = __import__("hermes_blueprint.base_rates", fromlist=["x"]).unit_class_table()
    return planning.validate_plan(plan, prof, rates, ledger or {})


def problems(plan, **kw):
    with pytest.raises(ToolError) as exc:
        check(plan, **kw)
    return " | ".join(exc.value.data["problems"])


def test_a_single_plugin_is_hours_and_the_wait_sets_the_calendar():
    clean, c = check(plugin_plan())
    assert c["effort_hours"]["p50"] == {"agent": 2.5, "human": 1.0, "total": 3.5}
    assert c["calendar_days"]["p50"] == 3.0
    assert c["calendar_drivers"][0].startswith("U4")
    assert "U4" in c["start_today"]
    assert [u["id"] for u in clean["units"]][-1] in ("U3", "U4")


def test_rules_catch_human_team_estimates():
    plan = plugin_plan(units=[unit("U1", "A", 40, 80, 160, ref_class="scaffold"),
                              unit("U2", "W", 1, 2, 3)])
    text = problems(plan)
    for needle in ("over 16 h; split it", "start_now: true", "need H units", "S1"):
        assert needle in text


def test_months_only_from_waits():
    units = [unit(f"U{i}", "A", 4, 10, 16, ref_class="core_engine") for i in range(1, 15)]
    units.append(unit("U99", "H", 1, 2, 4))
    plan = {"shape": "app", "units": units,
            "gates": [{"after": "U1", "check": "c", "kill_if": "k"}],
            "scope_reasons": ["many levels"]}
    assert "S3" in problems(plan, prof={"hours_per_day": 1, "days_per_week": 5})
    store_wait = unit("U50", "W", 30, 45, 60, start_now=True)
    plan["units"] = units[:3] + [units[-1], store_wait]
    _, c = check(plan)
    assert c["calendar_days"]["p50"] == 45 and c["wait_days_on_path"] == 45


def test_class_p90_needs_a_named_multiplier():
    plan = plugin_plan()
    plan["units"][0] = unit("U1", "A", 2, 5, 9)
    assert "above the scaffold P90" in problems(plan)
    plan["units"][0]["multipliers"] = [{"name": "unfamiliar_toolchain",
                                        "reason": "first Unity project"}]
    check(plan)


def test_ranges_novelty_cycles_and_gates():
    plan = plugin_plan(gates=[])
    plan["units"][0] = unit("U1", "A", 1, 1, 1)
    plan["units"][1] = unit("U2", "A", 1, 2, 2.5, novel=True, ref_class="api_integration",
                            depends_on=["U3"])
    text = problems(plan)
    for needle in ("p90 must exceed p10", "novel work", "cycle", "gates"):
        assert needle in text


def test_ledger_overrides_need_a_note(store):
    with store.tx() as conn:
        for v in (2.0, 2.5, 3.0):
            conn.execute("INSERT INTO actuals (project_id, unit_id, unit_class, ref_class,"
                         " estimate_p50, actual, source, at) VALUES (1, 'U', 'A', 'scaffold',"
                         " 1, ?, 'user', 0)", (v,))
    ledger = profile.ledger_stats(store)
    assert ledger["scaffold"] == {"n": 3, "p10_h": 2.1, "p50_h": 2.5, "p90_h": 2.9}
    rates = profile.class_rates(store)
    assert next(r for r in rates if r["class"] == "scaffold")["basis"] == "from your ledger: n = 3"
    plan = plugin_plan()
    with pytest.raises(ToolError) as exc:
        planning.validate_plan(plan, PROFILE, rates, ledger)
    assert "S7" in " ".join(exc.value.data["problems"])
    plan["units"][0]["note"] = "boilerplate exists already"
    plan["units"][0]["p90"] = 2.5
    planning.validate_plan(plan, PROFILE, rates, ledger)


def test_planner_subagent_draft_is_validated_and_stored(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    bp.ok("idea_phase", action="advance")
    bp.runner.replies["planner"] = "Here you go:\n```json\n" + json.dumps(plugin_plan()) + "\n```"
    res = bp.ok("idea_plan", action="draft")
    assert res["draft"] == "stored" and "| U1 unit U1 | A |" in res["markdown"]
    packet = bp.runner.jobs[-1].context
    assert "Builder profile" in packet and "Critic verdict" in packet and "S1." in packet
    done = bp.ok("idea_phase", action="advance")
    assert done["project"]["status"] == "planned"


def test_bad_draft_comes_back_for_fixing(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    bp.ok("idea_phase", action="advance")
    bp.runner.replies["planner"] = json.dumps(plugin_plan(gates=[]))
    res = bp.ok("idea_plan", action="draft")
    assert res["draft"] == "needs fixes" and any("gates" in p for p in res["problems"])
    assert not bp.call("idea_phase", action="advance")["ok"]
    assert bp.ok("idea_plan", action="submit", plan=plugin_plan())["plan_id"]


def test_plan_needs_a_verdict_first(bp):
    bp.to_phase5()
    bp.idea("phase 6 skip")
    assert "not done" in bp.idea("phase 6")


def test_lists_sent_as_json_strings_are_parsed_and_s1_names_the_unit_ids():
    plan = plugin_plan()
    clean, _ = check({**plan, "units": json.dumps(plan["units"])})
    assert [u["id"] for u in clean["units"]][0] == "U1"
    big = plugin_plan(units=[unit("U1", "A", 5, 12, 30, ref_class="core_engine"),
                             unit("U2", "H", 0.5, 1, 2, depends_on=["U1"])])
    assert "(an agent unit: U1)" in problems(big)
    clean, _ = check({**big, "effort_driver": "u1", "scope_reasons": ["one big unit"]})
    assert clean["effort_driver"] == "U1"
