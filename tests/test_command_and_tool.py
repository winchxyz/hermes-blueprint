"""The /idea command and the idea_phase tool, driven through the registered handlers."""
from __future__ import annotations

import json

import pytest
from conftest import FakeCtx

from hermes_blueprint import register

VARIANTS = [{"name": "Bot", "summary": "a"}, {"name": "Web", "summary": "b"},
            {"name": "Sheet", "summary": "c"}]


@pytest.fixture
def app(store):
    ctx = FakeCtx()
    register(ctx, store_factory=lambda: store)
    cmd = ctx.commands["idea"]["handler"]

    def idea(text: str, session: str = "s1") -> str:
        return cmd(text, session_id=session, session_key="", platform="cli")

    def call(session: str = "s1", _tool: str = "idea_phase", **args) -> dict:
        return json.loads(ctx.tools[_tool]["handler"](args, session_id=session, task_id="t"))

    return idea, call, store


def brief_and_profile(call, session: str = "s1") -> None:
    """Satisfy the phase 1 gate the way the agent does: brief plus a confirmed profile."""
    assert call(session, action="record", kind="brief", content="who: club players")["ok"]
    assert call(session, _tool="idea_profile", action="set",
                profile={"team": "solo", "agents": ["hermes"], "hours_per_day": 5})["ok"]
    assert call(session, _tool="idea_profile", action="confirm")["ok"]


def test_help_and_unknown(app):
    idea, _, _ = app
    assert "/idea start" in idea("")
    assert "Unknown subcommand 'zap'" in idea("zap")


def test_start_binds_project_to_chat(app):
    idea, call, _ = app
    out = idea("start A bot that books padel courts")
    assert "Started #1" in out and "Send any message" in out
    status = call(action="status")
    assert status["ok"] and status["phase"] == {"number": 1, "name": "Understanding"}
    assert status["project"]["idea"] == "A bot that books padel courts"
    assert status["gate_missing"]


def test_start_needs_text(app):
    idea, _, _ = app
    assert idea("start").startswith("Usage")


def test_tool_without_project(app):
    _, call, _ = app
    res = call(action="status")
    assert not res["ok"] and "/idea start" in res["error"]


def test_full_walk_until_research_gate(app):
    idea, call, _ = app
    idea("start padel")
    assert not call(action="advance")["ok"]
    assert call(action="record", kind="brief", content="who: club players")["ok"]
    still = call(action="advance")
    assert not still["ok"] and "builder profile" in still["missing"][0]
    brief_and_profile(call)
    moved = call(action="advance")
    assert moved["ok"] and moved["phase"]["number"] == 2
    # Phase 2 needs a research briefing from idea_research; record cannot fake it.
    res = call(action="record", kind="brief", content="x")
    assert not res["ok"] and "belongs to phase" in res["error"]
    blocked = call(action="advance")
    assert not blocked["ok"] and "research briefing" in blocked["missing"][0]


def test_record_rejects_harness_kinds(app):
    idea, call, _ = app
    idea("start padel")
    res = call(action="record", kind="verdict", content="fine")
    assert not res["ok"] and "own tools" in res["error"]


def test_back_needs_reason_and_lower_phase(app):
    idea, call, store = app
    idea("start padel")
    brief_and_profile(call)
    call(action="advance")
    assert not call(action="back", phase=1)["ok"]
    assert not call(action="back", phase=3, reason="x")["ok"]
    res = call(action="back", phase=1, reason="scope changed")
    assert res["ok"] and res["phase"]["number"] == 1


def test_command_phase_jump_respects_gates(app):
    idea, call, _ = app
    idea("start padel")
    assert "not done" in idea("phase 3")
    brief_and_profile(call)
    assert "Phase 2. Context" in idea("phase 2 ready")
    assert "Phase 1. Understanding" in idea("phase 1")


def test_status_list_log_stop_resume(app):
    idea, call, _ = app
    assert "No project" in idea("status")
    idea("start first idea")
    idea("start second idea", session="s2")
    assert "#1 first idea" in idea("status")
    listing = idea("list")
    assert "* #1" in listing and "#2 second idea" in listing
    call(action="record", kind="brief", content="b")
    log = idea("log")
    assert "start at 1" in log and "brief (phase 1, by idea_phase)" in log
    assert "Unbound #1" in idea("stop")
    assert not call(action="status")["ok"]
    assert "Bound to this chat" in idea("resume second-idea")
    assert call(action="status")["project"]["id"] == 2
    assert "no project" in idea("resume 99")


def test_sessions_are_isolated(app):
    idea, call, _ = app
    idea("start one", session="a")
    idea("start two", session="b")
    assert call(session="a", action="status")["project"]["title"] == "one"
    assert call(session="b", action="status")["project"]["title"] == "two"


def test_variants_and_choice_through_tool(app):
    idea, call, store = app
    idea("start padel")
    p = store.bound_project("s1")
    # Skip the research gate the way idea_research will satisfy it.
    store.add_artifact(p.id, 2, "briefing", "idea_research", {"sources": []})
    brief_and_profile(call)
    call(action="advance")
    call(action="advance")
    assert not call(action="record", kind="variants", content=VARIANTS[:2])["ok"]
    assert call(action="record", kind="variants", content=VARIANTS)["ok"]
    assert call(action="advance")["phase"]["number"] == 4
    assert call(action="record", kind="choice",
                content={"variant": "Bot", "reason": "fastest"})["ok"]
    assert call(action="advance")["phase"]["number"] == 5
    res = call(action="advance")
    assert not res["ok"] and "critic verdict" in res["missing"][0]


def test_tool_never_raises(app):
    idea, _, _ = app
    idea("start padel")

    def boom():
        raise RuntimeError("disk gone")

    ctx = FakeCtx()
    register(ctx, store_factory=boom)
    res = json.loads(ctx.tools["idea_phase"]["handler"]({"action": "status"}, session_id="s1"))
    assert not res["ok"] and "disk gone" in res["error"]
