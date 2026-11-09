"""Phase 2 through the idea_research tool, with fake web backends and a fake verifier."""
from __future__ import annotations

from conftest import FakeRunner, Harness


def test_full_research_pass_opens_the_gate(bp):
    bp.phase1()
    out = bp.research()
    md = out["markdown"]
    assert out["stats"]["claims"] == 3 and out["stats"]["verified"] == 3
    for section in ("## Claims", "## Source log", "## Coverage", "## Not verified"):
        assert section in md
    assert "C1 ✅ Padel club bookings rose 40% in 2025" in md
    assert "https://fep.es/report" in md
    assert "Independent verifier (fake/model)" in md
    assert bp.ok("idea_phase", action="advance")["phase"]["number"] == 3


def test_claim_needs_a_real_quote(bp):
    bp.phase1()
    bp.ok("idea_research", action="fetch", urls=["https://fep.es/report"])
    bad = bp.call("idea_research", action="claim", text="x", type="other",
                  evidence=[{"source": "S1", "quote": "Bookings fell sharply in 2025 everywhere"}])
    assert not bad["ok"] and bad["failures"][0]["problem"] == "not found in the page text"
    short = bp.call("idea_research", action="claim", text="x", type="other",
                    evidence=[{"source": "S1", "quote": "padel"}])
    assert "too short" in short["failures"][0]["problem"]
    none = bp.call("idea_research", action="claim", text="x", type="other")
    assert not none["ok"] and "unverified=true" in none["error"]
    lead = bp.ok("idea_research", action="claim", text="clubs hate apps", type="other",
                 unverified=True)
    assert lead["label"] == "🔍"


def test_copies_do_not_count_twice(bp):
    bp.phase1()
    bp.ok("idea_research", action="fetch", urls=["https://fep.es/report",
                                                 "https://mirror.example.net/report"])
    res = bp.ok("idea_research", action="claim", text="Bookings rose 40%", type="market_size",
                evidence=[{"source": "S1", "quote": "Club bookings rose 40% in 2025"},
                          {"source": "S2", "quote": "Club bookings rose 40% in 2025"}])
    assert res["label"] == "⚠️" and "independent" in res["note"]


def test_absence_needs_three_searches_and_is_never_verified(bp):
    bp.phase1()
    ids = [bp.ok("idea_research", action="search", query=f"padel bot hermes {i}",
                 purpose="competitor", channel="marketplaces")["search"] for i in range(3)]
    assert not bp.call("idea_research", action="absence", text="no padel plugin",
                       searches=ids[:2])["ok"]
    res = bp.ok("idea_research", action="absence", text="no padel plugin", searches=ids)
    assert res["label"].startswith("🔍")
    assert not bp.call("idea_research", action="claim", text="x",
                       type="competitor_absent", unverified=True)["ok"]


def test_briefing_lists_every_gap(bp):
    bp.phase1()
    res = bp.call("idea_research", action="briefing", summary="It is great [C9].")
    assert not res["ok"]
    problems = " | ".join(res["problems"])
    for needle in ("unknown claims", "needs 6", "no ✅", "disconfirmation", "competitor sweep",
                   "action=verify"):
        assert needle in problems


def test_briefing_requires_verify_after_the_last_claim(bp):
    bp.phase1()
    bp.research()
    bp.ok("idea_research", action="claim", text="late fact", type="other", unverified=True)
    res = bp.call("idea_research", action="briefing", summary="See [C1].")
    assert not res["ok"] and any("verify" in p for p in res["problems"])


def test_verifier_retracts_and_downgrades(store):
    h = Harness(store)
    h.phase1()
    reply = ('{"claims": [{"id": "C1", "verdict": "partial", "original": true, "note": "2025 '
             'only"}, {"id": "C2", "verdict": "supported", "original": false}, '
             '{"id": "C3", "verdict": "unsupported", "note": "about clubs in Spain only"}]}')
    verified = h.gather(verify_reply=reply)
    assert {c["claim"]: c["now"] for c in verified["changes"]} == {
        "C1": "⚠️", "C2": "⚠️", "C3": "retracted"}
    refused = h.call("idea_research", action="briefing", summary="[C1] [C2] [C3]")
    assert "cites retracted claims: C3" in refused["problems"][0]
    assert any("2 claims" in p for p in refused["problems"])
    h.ok("idea_research", action="claim", text="Federation reports 40% growth",
         type="other", evidence=[{"source": "S1", "quote": "according to the federation's"}])
    h.runner.replies["verifier"] = '{"claims": [{"id": "C4", "verdict": "supported"}]}'
    h.ok("idea_research", action="verify")
    md = h.ok("idea_research", action="briefing", summary="[C1] [C2] [C4]")["markdown"]
    assert "C3 retracted" in md and "C1 ⚠️" in md and "C2 ⚠️" in md
    assert "verifier: copy of another source" in md


def test_briefing_says_when_the_verifier_did_not_run(store):
    h = Harness(store, runner=FakeRunner(fail="no second provider"))
    h.phase1()
    md = h.research()["markdown"]
    assert "independent verifier did not run (no second provider)" in md


def test_read_finds_text_in_long_pages(bp):
    bp.phase1()
    bp.web.page("https://long.example.com", "intro " * 3000 + "THE NEEDLE SENTENCE here.")
    fetched = bp.ok("idea_research", action="fetch", urls=["https://long.example.com"])
    assert fetched["pages"][0]["more"] > 0
    found = bp.ok("idea_research", action="read", source="S1", find="needle sentence")
    assert "THE NEEDLE SENTENCE" in found["matches"][0]


def test_research_is_closed_in_phase_1(bp):
    bp.idea("start padel")
    res = bp.call("idea_research", action="search", query="x", purpose="support")
    assert not res["ok"] and "phase" in res["error"]


def test_fetch_errors_are_reported(bp):
    bp.phase1()
    res = bp.ok("idea_research", action="fetch", urls=["https://nowhere.example"])
    assert res["pages"][0]["error"] == "404"


def test_a_missing_web_backend_is_an_error_not_an_empty_success(bp):
    bp.phase1()
    bp.ctx.backend = lambda name, args: '{"error": "Unknown tool: web_extract"}'
    res = bp.call("idea_research", action="fetch", urls=["https://nowhere.example"])
    assert not res["ok"] and "Unknown tool: web_extract" in res["error"]


def test_source_log_lists_each_claim_once_and_absence_reads_cleanly(bp):
    bp.phase1()
    bp.gather()
    bp.ok("idea_research", action="claim", text="Playtomic covers many countries",
          type="competitor_exists", evidence=[
              {"source": "S3", "quote": "book padel courts online in 40 countries"},
              {"source": "S3", "quote": "book padel courts online in 40 countries"}])
    from hermes_blueprint import research
    project = bp.store.bound_project("s1")
    ids = [s["id"] for s in research.searches(bp.store, project.id)
           if s["purpose"] == "competitor"]
    bp.ok("idea_research", action="absence", text="No padel bot for Hermes exists.", searches=ids)
    bp.runner.replies["verifier"] = (
        '{"claims": [' + ", ".join(f'{{"id": "C{n}", "verdict": "supported", "original": true}}'
                                   for n in range(1, 5)) + "]}")
    bp.ok("idea_research", action="verify")
    md = bp.ok("idea_research", action="briefing",
               summary="Bookings grow [C1]; Playtomic exists [C2]; phones rule [C3].",
               unknowns=["club willingness to pay"])["markdown"]
    row = next(line for line in md.splitlines() if line.startswith("| S3 "))
    assert row.endswith("| C2, C4 |")
    assert "exists. Looked in:" in md and ".. Looked" not in md
