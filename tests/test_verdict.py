"""Phase 5: outside view first, pre-commitment, no caving without new evidence."""
from __future__ import annotations


def test_commit_needs_the_outside_view_and_scoreable_predictions(bp):
    bp.to_phase5()
    res = bp.call("idea_verdict", **bp.verdict_args(
        reference_class={"name": "x", "base_rate": "y", "source": "my gut"},
        predictions=[{"statement": "s", "p": 1.0, "resolve_by": "2027-01-01", "how": "h"},
                     {"statement": "s", "p": 0.4, "resolve_by": "2026-01-01", "how": "h"}],
        premortem=[{"cause": "a", "p_given_failure": 0.9}]))
    problems = " | ".join(res["problems"])
    for needle in ("neither a claim id nor a base-rate key", "at least 3 ranked causes",
                   "between 0.02 and 0.98", "must be in the future",
                   "at least 3 scoreable predictions"):
        assert needle in problems


def test_unverified_claim_is_not_a_base_rate(bp):
    bp.to_phase5()
    bp.ok("idea_research", action="claim", text="90% of bots fail", type="other",
          unverified=True)
    res = bp.call("idea_verdict", **bp.verdict_args(
        reference_class={"name": "bots", "base_rate": "90% fail", "source": "C4"}))
    assert not res["ok"] and "not a verified claim" in res["problems"][0]


def test_acquiescence_check(bp):
    bp.to_phase5()
    args = bp.verdict_args(p_success=0.8)
    for p in args["predictions"]:
        p["p"] = 0.7
    res = bp.call("idea_verdict", **args)
    assert not res["ok"] and "acquiescence" in res["problems"][0]
    args["acquiescence_note"] = "the pilot clubs already asked for it"
    assert bp.ok("idea_verdict", **args)["verdict"]["acquiescence_note"]


def test_commit_stores_verdict_and_predictions_then_gate_opens(bp):
    bp.to_phase5()
    res = bp.ok("idea_verdict", **bp.verdict_args())
    assert res["verdict"]["prediction_ids"] == ["P1", "P2", "P3"]
    assert "chrome" in res["verdict"]["reference_class"]["source_detail"]
    again = bp.call("idea_verdict", **bp.verdict_args())
    assert not again["ok"] and "already committed" in again["error"]
    assert bp.ok("idea_phase", action="advance")["phase"]["number"] == 6


def test_pushback_without_evidence_changes_nothing(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    res = bp.ok("idea_verdict", action="pushback", argument="I just know clubs will pay")
    assert res["verdict"]["p_success"] == 0.3 and "Do not change" in res["rule"]
    no_ev = bp.call("idea_verdict", action="revise", changes={"p_success": 0.6},
                    reason="user is confident")
    assert not no_ev["ok"] and "new_evidence" in no_ev["error"]
    old = bp.call("idea_verdict", action="revise", changes={"p_success": 0.6},
                  new_evidence=["C1"], reason="growth")
    assert not old["ok"] and "existed before the verdict" in old["error"]


def test_revise_with_new_quote_checked_evidence(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    bp.web.page("https://club.example.es/news", "Our club signed a paid contract for an "
                "automated WhatsApp booking assistant this month.")
    bp.ok("idea_research", action="fetch", urls=["https://club.example.es/news"])
    claim = bp.ok("idea_research", action="claim", text="A club pays for a WhatsApp booking bot",
                  type="traction", evidence=[{
                      "source": "S4", "quote": "signed a paid contract for an automated "
                                               "WhatsApp booking assistant"}])
    res = bp.ok("idea_verdict", action="revise", new_evidence=[claim["claim"]],
                reason="a club already pays for this", changes={"p_success": 0.4})
    v = res["verdict"]
    assert v["version"] == 2 and v["p_success"] == 0.4
    assert v["changed_because"]["fields"] == ["p_success"]
    assert bp.ok("idea_verdict", action="show")["history"] == 2


def test_redteam_runs_isolated_and_can_justify_a_revision(bp):
    bp.to_phase5()
    bp.ok("idea_verdict", **bp.verdict_args())
    bp.runner.replies["redteam"] = ('{"verdict": "pivot", "p_success": 0.15, "reference_class":'
                                    ' "SaaS for clubs", "top_risks": ["a", "b", "c"]}')
    res = bp.ok("idea_verdict", action="redteam")
    job = bp.runner.jobs[-1]
    assert job.role == "redteam" and "Evidence log" in job.context
    assert "pushback" not in job.context
    rev = bp.ok("idea_verdict", action="revise", new_evidence=[res["redteam"]],
                reason="red team found the distribution gap", changes={"verdict": "pivot"})
    assert rev["verdict"]["verdict"] == "pivot"


def test_verdict_only_in_phase_5(bp):
    bp.phase1()
    res = bp.call("idea_verdict", **bp.verdict_args())
    assert not res["ok"] and "phase" in res["error"]
