# Build plan

Estimated with the plugin's own method (A = agent-bound active hours, H = human-bound,
W = external wait; P10/P50/P90). Base rates from `docs/research/estimation.md` 3.2.

| # | Unit | Class | P10 | P50 | P90 | Depends on |
|---|---|---|---|---|---|---|
| 1 | Hermes install + spike: `subagent_lifecycle` under default isolation, `dispatch_tool` for web_search/web_extract/kanban_create, slash output visibility | A | 0.5 h | 1 h | 3 h | — |
| 2 | Skeleton: manifest v2, `register()`, `/idea` state machine, `plugin_db` schema, FakeCtx tests, CI green | A | 0.5 h | 1 h | 2.5 h | 1 |
| 3 | Write methodology: coordinator skill + per-phase reference files with the H1-H8 rules | A | 1 h | 1.5 h | 3 h | 2 |
| 4 | Research ledger: `idea_research`, `idea_claim`, quote check, independence, coverage + Not verified output | A | 1 h | 2 h | 5 h | 2 |
| 5 | Verifier + Planner subagents with context packets; plan validator (A/H/W, ranges, S1-S7) | A | 1 h | 2 h | 5 h | 3, 4 |
| 6 | Critic tools: `idea_verdict` pre-commitment, pushback rule, predictions table | A | 0.5 h | 1.5 h | 3 h | 3 |
| 7 | Builder profile + velocity ledger (own timeline, opt-in SessionDB timestamps) | A | 0.5 h | 1.5 h | 3 h | 2 |
| 8 | Handoff: scaffold folder + kanban cards (idempotent), confirmations | A | 0.5 h | 1.5 h | 3 h | 5 |
| 9 | Recheck: blueprint, kanban progress, Brier, estimate vs actual, ledger update | A | 0.5 h | 1.5 h | 3 h | 6, 7, 8 |
| 10 | README with disclosure, catalog entry draft | A | 0.5 h | 1 h | 2 h | all |
| 11 | Owner runs 2 real brainstorms in Hermes, reviews research/critic/plan quality | H | 1.5 h | 3 h | 5 h | 9 |
| 12 | Demo recording and video | H | 1 h | 2 h | 4 h | 11 |
| 13 | Catalog PR review by Nous | W | 1 d | ? | ? | 10 |

**Effort:** A ≈ 14.5 h P50 (range ~7-32 h), H ≈ 5 h. **Calendar:** 2-3 working days at 5-7 active
hours per day, plus catalog review (W, not in our control). Top calendar drivers: owner review
rounds (11), demo (12), catalog review (13).

## Gates

- After 1: `subagent_lifecycle.launch` runs from a plugin tool, and web_extract returns page text we
  can quote-check. If either fails, switch to the fallbacks in ARCHITECTURE.md before building on it.
- After 4: a real research pass on a sample idea produces a source log where every ✅ claim has a
  verified quote.
- After 5: the planner, given "one Hermes plugin, solo with agents", estimates hours, not weeks
  (regression test with the owner's ghost-call case).
- After 11: the owner says the research and critique are not sloppy, and the estimates are believable.

## Status

- D3 settled (kinds only).
- Unit 1 done: every gate question answered by real runs, no fallback needed (DECISIONS D7).
- Unit 2 done: skeleton with `/idea`, `idea_phase`, code-checked phase gates, SQLite store, 40
  offline tests; CI green (tests on 3.11/3.12, `hermes plugins validate` and `doctor --ci` on
  v0.23.0 and main).
- Next: unit 3 (methodology) and unit 4 (research ledger) can start; both depend only on 2.
