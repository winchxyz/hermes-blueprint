"""Phase gates are enforced in code; harness artifacts only come from their own tools."""
from __future__ import annotations

import pytest

from hermes_blueprint import phases
from hermes_blueprint.store import Store

VARIANTS = [{"name": "Bot", "summary": "a"}, {"name": "Web", "summary": "b"},
            {"name": "Sheet", "summary": "c"}]


def _project_in(store: Store, phase: int):
    """Walk a project to ``phase`` by writing each gate's artifacts as their producers would."""
    p = store.create_project("padel booking")
    for n in range(1, phase):
        for req in phases.GATES[n]:
            payload = VARIANTS if req.kind == "variants" else {"variant": "Bot", "reason": "r"}
            store.add_artifact(p.id, n, req.kind, sorted(req.producers)[0], payload)
        p = phases.advance(store, store.get_project(p.id))
    return p


def test_cannot_advance_without_brief(store: Store):
    p = store.create_project("x")
    with pytest.raises(phases.GateClosed) as exc:
        phases.advance(store, p)
    assert exc.value.phase == 1
    assert "brief" in exc.value.items[0]


def test_brief_opens_phase_1(store: Store):
    p = store.create_project("x")
    store.add_artifact(p.id, 1, "brief", phases.RECORD, {"text": "who/what/why"})
    with pytest.raises(phases.GateClosed, match="builder profile"):
        phases.advance(store, p)
    store.add_artifact(p.id, 1, "profile_used", "idea_profile", {"fields": {}})
    assert phases.advance(store, p).phase == 2


@pytest.mark.parametrize("phase,kind", [(2, "briefing"), (5, "verdict"), (6, "plan")])
def test_harness_gates_ignore_recorded_notes(store: Store, phase, kind):
    p = _project_in(store, phase)
    store.add_artifact(p.id, phase, kind, phases.RECORD, {"text": "trust me"})
    with pytest.raises(phases.GateClosed):
        phases.advance(store, p)


def test_finishing_phase_6_marks_planned(store: Store):
    p = _project_in(store, 6)
    store.add_artifact(p.id, 6, "plan", "idea_plan", {"units": []})
    done = phases.advance(store, p)
    assert (done.phase, done.status) == (6, "planned")
    with pytest.raises(ValueError, match="planned"):
        phases.advance(store, done)


def test_go_back_is_free_and_logged(store: Store):
    p = _project_in(store, 4)
    back = phases.go_to(store, p, 2, "new competitor found")
    assert back.phase == 2
    assert store.phase_events(p.id)[-1][:3] == (4, 2, "new competitor found")


def test_jump_forward_checks_every_gate(store: Store):
    p = store.create_project("x")
    store.add_artifact(p.id, 1, "brief", phases.RECORD, {"text": "b"})
    store.add_artifact(p.id, 1, "profile_used", "idea_profile", {"fields": {}})
    with pytest.raises(phases.GateClosed) as exc:
        phases.go_to(store, p, 4, "skip")
    assert exc.value.phase == 2


def test_go_to_rejects_bad_phase(store: Store):
    with pytest.raises(ValueError):
        phases.go_to(store, store.create_project("x"), 7, "")


def test_reopening_a_planned_project(store: Store):
    p = _project_in(store, 6)
    store.add_artifact(p.id, 6, "plan", "idea_plan", {"units": []})
    planned = phases.advance(store, p)
    again = phases.go_to(store, planned, 5, "recheck")
    assert (again.phase, again.status) == (5, "active")


class TestValidateRecord:
    def test_only_recordable_kinds(self, store: Store):
        p = store.create_project("x")
        with pytest.raises(ValueError, match="own tools"):
            phases.validate_record("verdict", "ok", p, store)

    def test_kind_must_match_phase(self, store: Store):
        p = store.create_project("x")
        with pytest.raises(ValueError, match="belongs to phase"):
            phases.validate_record("variants", VARIANTS, p, store)

    def test_brief_text_normalized(self, store: Store):
        p = store.create_project("x")
        assert phases.validate_record("brief", "  hi ", p, store) == {"text": "hi"}
        with pytest.raises(ValueError):
            phases.validate_record("brief", "  ", p, store)

    def test_variants_need_three_distinct(self, store: Store):
        p = _project_in(store, 3)
        with pytest.raises(ValueError, match="at least 3"):
            phases.validate_record("variants", VARIANTS[:2], p, store)
        with pytest.raises(ValueError, match="distinct"):
            phases.validate_record("variants", VARIANTS[:2] + [VARIANTS[0]], p, store)
        with pytest.raises(ValueError, match="name"):
            phases.validate_record("variants", VARIANTS[:2] + [{"name": "x"}], p, store)
        assert phases.validate_record("variants", VARIANTS, p, store) == VARIANTS

    def test_choice_must_name_a_recorded_variant(self, store: Store):
        p = _project_in(store, 4)
        with pytest.raises(ValueError, match="recorded variants"):
            phases.validate_record("choice", {"variant": "Nope", "reason": "r"}, p, store)
        ok = {"variant": "web", "reason": "cheapest to test"}
        assert phases.validate_record("choice", ok, p, store) == ok


def test_slugs_keep_whole_words():
    from hermes_blueprint.store import slugify

    s = slugify("a Chrome extension that turns long GitHub PR threads into a 5-line summary")
    assert s == "chrome-extension-that-turns-long-github"
    assert slugify("Ünïcode only ☃") == "n-code-only"
    assert slugify("!!!") == "idea"
    assert slugify("x" * 60) == "x" * 40


def _ready(store: Store, p, phase: int):
    for req in phases.GATES[phase]:
        payload = VARIANTS if req.kind == "variants" else {"variant": "Bot", "reason": "r"}
        store.add_artifact(p.id, phase, req.kind, sorted(req.producers)[0], payload)


def test_user_phases_need_a_user_turn_once_the_hook_runs(store: Store):
    p = store.create_project("padel booking")
    store.record_turn(p.id, 1, "t1")              # the user's first message, in phase 1
    _ready(store, p, 1)
    p = phases.advance(store, p)                  # phase 1 had a user turn
    _ready(store, p, 2)
    p = phases.advance(store, p)                  # research (2) runs on its own
    assert p.phase == 3
    _ready(store, p, 3)
    with pytest.raises(phases.GateClosed, match="a reply from the user"):
        phases.advance(store, p)                  # same turn: the user has not seen phase 3
    assert phases.open_items(store, p) == [phases.USER_TURN_LABEL]
    store.record_turn(p.id, 3, "t2")
    assert phases.advance(store, p).phase == 4


def test_no_turns_recorded_means_no_user_check(store: Store):
    p = _project_in(store, 4)                     # the hook never ran (tests, other hosts)
    assert phases.user_gap(store, p, 4) == []


def test_the_user_can_still_skip_ahead(store: Store):
    p = store.create_project("padel booking")
    store.record_turn(p.id, 1, "t1")
    for n in (1, 2, 3):
        _ready(store, p, n)
    p = phases.go_to(store, p, 4, "user skipped")  # /idea phase 4: artifacts only
    assert p.phase == 4


def test_the_user_sees_the_verdict_before_the_plan(store: Store):
    p = _project_in(store, 5)
    store.record_turn(p.id, 5, "t1")              # "run the critique"
    _ready(store, p, 5)                           # the verdict is committed in that turn
    with pytest.raises(phases.GateClosed, match="after they saw the verdict"):
        phases.advance(store, p)
    store.record_turn(p.id, 5, "t2")              # the user read it and answered
    assert phases.advance(store, p).phase == 6
