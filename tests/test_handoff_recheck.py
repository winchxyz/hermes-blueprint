"""After the plan: project folder, kanban cards, re-checks, the state card and registration."""
from __future__ import annotations

import json

import pytest
from conftest import TODAY
from test_planning import plugin_plan

from hermes_blueprint import register
from hermes_blueprint.recheck import brier


@pytest.fixture
def planned(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    bp.ok("idea_phase", action="advance")
    bp.ok("idea_plan", action="submit", plan=plugin_plan())
    bp.ok("idea_phase", action="advance")
    return bp


def test_handoff_waits_for_a_plan(bp):
    bp.idea("start padel")
    assert "No validated plan" in bp.idea("handoff")


def test_folder_needs_confirmation_and_an_empty_target(planned, tmp_path):
    target = tmp_path / "padel"
    assert "--yes" in planned.idea(f'handoff folder "{target}"')
    assert not target.exists()
    planned.ctx.choice = "write"
    assert "Wrote README.md, PLAN.md" in planned.idea(f'handoff folder "{target}"')
    plan_md = (target / "PLAN.md").read_text(encoding="utf-8")
    assert "**Effort:** agent 2.5 h" in plan_md
    research_md = (target / "RESEARCH.md").read_text(encoding="utf-8")
    assert "## Source log" in research_md
    decisions = (target / "DECISIONS.md").read_text(encoding="utf-8")
    assert "Chrome extensions" in decisions and "P1 (0.35)" in decisions
    assert "exists and is not empty" in planned.idea(f'handoff folder "{target}" --yes')


def test_cards_are_idempotent_with_dependencies_and_held_human_units(planned, tmp_path):
    planned.idea(f'handoff folder "{tmp_path / "p"}" --yes')
    out = planned.idea("handoff cards --yes")
    assert "U1: t_0001 (ready)" in out and "U4: t_0004 (blocked)" in out
    tasks = planned.web.tasks
    assert tasks["t_0002"]["parents"] == ["t_0001"]
    assert tasks["t_0001"]["workspace_kind"] == "dir"
    assert tasks["t_0003"]["title"].endswith("(you)")
    assert tasks["t_0003"]["initial_status"] == "blocked"
    assert "## Acceptance" in tasks["t_0001"]["body"]
    planned.idea("handoff cards --yes")
    assert len(tasks) == 4


def test_cards_can_be_held_or_cancelled(planned):
    planned.ctx.choice = "cancel"
    assert planned.idea("handoff cards") == "Cancelled."
    assert planned.web.tasks == {}
    planned.ctx.choice = "hold"
    planned.idea("handoff cards")
    assert all(t["status"] == "blocked" for t in planned.web.tasks.values())


def test_recheck_scores_predictions_and_feeds_the_ledger(planned):
    planned.idea("handoff cards --yes")
    planned.web.tasks["t_0001"].update(status="done", started_at=0, completed_at=5400)
    planned.set_today(TODAY.replace(year=2027, month=3))
    report = planned.ok("idea_recheck", action="report")
    u1 = report["units"][0]
    assert u1["status"] == "done" and u1["elapsed_h"] == 1.5
    assert len(report["predictions_due"]) == 3 and report["tripwires_due"]
    planned.ok("idea_recheck", action="resolve", prediction="P1", outcome="0")
    planned.ok("idea_recheck", action="resolve", prediction="P2", outcome="1")
    res = planned.ok("idea_recheck", action="resolve", prediction="P3", outcome="void")
    assert res["scores"]["resolved"] == 2
    assert res["scores"]["brier_model"] == brier([(0.35, 0), (0.6, 1)])
    assert "warning" in res["scores"]
    assert not planned.call("idea_recheck", action="resolve", prediction="P1", outcome="1")["ok"]
    act = planned.ok("idea_recheck", action="actual", unit="U1", value=1.5, source="kanban")
    assert act["ratio"] == 1.5 and act["inside_p10_p90"]
    assert act["ledger"] == {"n": 1, "p10_h": 1.5, "p50_h": 1.5, "p90_h": 1.5}
    text = planned.idea("recheck")
    assert "actual 1.5 vs P50 1" in text and "Brier: model" in text


def test_recheck_overview_works_without_a_bound_chat(planned):
    other = planned.call("idea_recheck", session="cron", action="overview")
    assert other["planned_projects"][0]["cards"] == 0
    rep = planned.call("idea_recheck", session="cron", action="report", project="1")
    assert rep["ok"] and rep["project"]["id"] == 1
    assert not planned.call("idea_recheck", session="cron", action="report")["ok"]


def test_state_card_only_for_bound_active_projects(bp):
    hook = dict(bp.ctx.hooks)["pre_llm_call"]
    assert hook(session_id="s1", user_message="hi") is None
    bp.idea("start padel")
    card = hook(session_id="s1", user_message="hi")["context"]
    assert card.startswith("[Blueprint] (plugin note, not written by the user) Project #1")
    assert "phase 1. Understanding" in card and "user's own words" in card
    assert "references/1-understanding.md" in card and len(card) < 900
    assert hook(session_id="other") is None
    assert hook() is None


def test_state_card_survives_a_broken_store(bp):
    from hermes_blueprint import make_state_hook

    def boom():
        raise RuntimeError("db locked")

    assert make_state_hook(boom)(session_id="s1") is None


def test_skill_and_blueprint_are_registered(bp):
    skill = bp.ctx.skills[0]
    assert skill["name"] == "blueprint" and skill["path"].exists()
    refs = skill["path"].parent / "references"
    for name in ("1-understanding", "2-context", "3-generation", "4-deep-dive", "5-critique",
                 "6-plan", "recheck"):
        assert (refs / f"{name}.md").exists()
    from hermes_blueprint.guide import PHASE_GUIDE

    for g in PHASE_GUIDE.values():
        assert (skill["path"].parent / g["reference"]).exists()
    assert bp.ctx.blueprints[0]["key"] == "recheck"
    assert "hermes-blueprint:blueprint" in bp.ctx.blueprints[0]["skills"]


def test_every_tool_never_raises(store):
    from conftest import FakeCtx

    def boom():
        raise RuntimeError("disk gone")

    ctx = FakeCtx()
    register(ctx, store_factory=boom)
    for name, entry in ctx.tools.items():
        res = json.loads(entry["handler"]({"action": "status"}, session_id="s1"))
        assert not res["ok"] and "disk gone" in res["error"], name
