# Architecture (draft for day 1)

**hermes-blueprint** (package `hermes_blueprint`, command `/idea`). Evidence for every design
choice: `docs/research/` (estimation, research-and-judgment, hermes-platform; hermes-agent v0.23.0
and main 856e7580).

## What it does

In the Hermes chat, a raw idea goes through six phases (Understanding, Context, Generation, Deep
dive, Critique, Plan), then:

- **Build handoff**: a scaffold folder (AGENTS.md/CLAUDE.md, README, DECISIONS, PLAN) and the plan's
  units as **Hermes kanban cards** with acceptance criteria and dependencies, so Hermes workers can
  start building.
- **Re-checks**: a weekly Hermes cron job reads kanban progress, compares it with the plan's gates,
  scores the predictions made during the brainstorm, and asks the Critic: thesis or tuning?

A methodology written only as prompts asks the model to be rigorous, and the model often is not
(`research-and-judgment.md`, "Baseline"). Here quality rules are **enforced by tools and data**,
not only asked for in prose. That is the "harness" below.

## The harness: what stops sloppy work

### H1. Research ledger (no source, no ✅)

- Research goes through `idea_research`, which calls Hermes `web_search` / `web_extract` via
  `dispatch_tool` and stores every search (query, time) and every fetched page (URL, fetched text,
  hash, date) in `plugin_db`.
- A claim is recorded with `idea_claim(text, type, sources=[S#], quote)`. Code checks that the quote
  appears in the stored page text (after folding case, whitespace, typographic dashes and quotes;
  `web_extract` returns the page body as text, D7). Only then can the claim be ✅.
- ✅ is mechanical: fetched page + exact quote + as-of date; numeric or contested claims need two
  **independent** sources (not the same origin republished). A search snippet is a lead, never
  evidence. "Nothing exists" claims are never ✅; they list where we looked.
- Minimum evidence per claim type (market size, competitor exists, price, technical feasibility,
  policy/regulation) and budget tiers (quick / standard / deep) with a saturation stopping rule
  (stop when new searches stop adding new claims), from `research-and-judgment.md` A3.
- Every Context briefing ends with **coverage** (what was searched, how many sources) and a
  **Not verified** block.

### H2. Competitor sweep checklist

For software ideas the research pass must cover, and log, each channel: GitHub, package registries,
plugin marketplaces and catalogs (Hermes catalog + its PRs, Claude Code / OpenClaw / MCP registries),
app stores, Product Hunt, Hacker News, Reddit, X, and the web. Today's manual check of 1204 Hermes
catalog entries plus ~1000 PRs is the reference example. Personal projects run the
"reuse before build" subset (GitHub, registries, marketplaces).

### H3. Disconfirmation and a fresh-context verifier

- Required disconfirmation queries ("X failed", "why not X", "X alternatives", "X criticism").
- After Phase 2 (and before any recommendation resting on Tier 3 facts) a **verifier** runs in a
  fresh subagent (`ctx.subagent_lifecycle.launch`, a different model when configured) with only the
  claims and the source log: re-fetch, quote check, URL liveness, retract or downgrade. Reason:
  models favour their own earlier steps; citation error rates in generative search are high
  (research-and-judgment A1).

### H4. Critic that does not cave

- **Outside view first**: name the reference class and a sourced base rate before the premortem.
- **Pre-commitment**: `idea_verdict` stores the verdict and probabilities before they are shown.
  Changing them needs named new evidence, logged as "changed because …". Pushback without evidence:
  restate once, keep the verdict. (Models flip under pushback about half the time.)
- Acquiescence check: if every probability leans the user's way, re-examine.
- Optional independent red-team on a second model for one-way-door decisions; in-context critic
  stays the default: context makes the critique specific (research-and-judgment B4).
- Calibrated to the **builder**, not only the project kind (H5).

### H5. Builder profile

Stored once per user (`ctx.state`), confirmed at the start of each brainstorm, editable with
`/idea profile`:

```yaml
team: solo | pair | team(n)
agents: [hermes, claude-code, codex]
parallel_agents: 1-4
hours_per_day: 4-7
skills: [...]            # where the human can verify fast
weak_spots: [...]        # where verification is slow
accounts_ready: [github, app-store, play-console, steam, twilio, ...]
distribution: [x-account, telegram-channel, ...]
budget_usd: {one_time, monthly}
```

Phase 1 asks at most three questions for missing fields; defaults are labelled assumptions.
Ideation, Deep dive, Critic and Planner all receive it.

### H6. Estimates that match how the builder works

Planner output is validated (`ctx.llm.complete_structured` + code checks) and regenerated if it fails:

1. Work units of ~0.5-6 h, each classed **A** (agent-bound), **H** (human-bound: decisions, taste,
   device tests, accounts, writing in your voice) or **W** (external wait: store review, API
   approval, tester windows, other people).
2. A units: P10/P50/P90 **active hours** from the builder's velocity ledger (≥3 past projects of the
   class) or the base-rate table (`estimation.md` 3.2, e.g. plugin skeleton P50 1 h, one API
   integration with tests P50 1.5 h). Multipliers only with a named reason.
3. H and W in calendar days; W items that can start now are put on day 1.
4. **Effort** and **calendar** shown separately; top three calendar drivers named.
5. Sanity rules S1-S7 (`estimation.md` 3.3), e.g. a single plugin / bot / CLI is hours; "months"
   only in calendar time and only with a named W item. The Critic checks "estimate realism".

Owner's own numbers (velocity ledger over 311 Claude Code sessions, 80 projects): median 7.3 active
hours per project, 57% under 10 h, median 3.1 calendar days; ghost-call v1 release ≈ 5 active hours
(plugin build 2.4 h); an LLM plan for it had said "several months", ~100x off.

### H7. Velocity ledger (opt-in)

- Sources: our own project timeline (phase times, handoff, kanban run durations via `kanban_show`),
  Hermes `SessionDB` metadata (read-only, timestamps only, never message text), and an optional
  import of Claude Code / Codex session timestamps (`estimation.md` Part 2 method: active hours =
  sum of gaps < 20 min).
- Disclosed (catalog rule 13), off until the user turns it on.

### H8. Predictions and calibration

Every recommendation and verdict emits scoreable predictions (statement, probability, due date,
how to resolve) into `plugin_db`. `/idea recheck` resolves the due ones, computes Brier scores
(model vs user), compares estimates with actuals per unit class, and updates the ledger (smoothing
α≈0.3, aim for ~80% of actuals inside P10-P90). Small-N warning below ~20 resolved predictions.

## Hermes surfaces

- **`/idea`**: `start <idea>`, `status`, `phase`, `profile`, `research`, `critique`, `plan`,
  `handoff`, `recheck`, `log`, `ledger`, `reset`. State lives in code, costs no tokens. Its output
  goes to the user only, never to the model (spike, D7), so `start`/`resume` end with "send a
  message to begin"; `ctx.inject_message` is an optional upgrade behind `allow_gateway_injection`.
- **State key**: tool handlers receive `session_id` (no `conversation_id`); projects are bound to
  `session_id`, with a `parent_session_id` walk after compression (later unit).
- **Tool discovery**: with Tool Search on (the default once many tools are attached), plugin
  tools are deferred and found through `tool_search`. Tool descriptions carry searchable words
  and the state card names the exact next tool.
- **Coordinator skill** (bundled) with per-phase reference files, loaded on demand.
- **`pre_llm_call` state card** only while a project is active in the conversation (phase, rules
  for that phase, open items), ≤ a few hundred tokens.
- **Tools** (`idea_*`): `phase` (advance only when the phase's artifacts exist), `research`,
  `claim`, `verify`, `variants`, `verdict`, `predict`, `plan`, `scaffold`, `handoff`, `recheck`,
  `profile`.
- **Isolation**: Planner, verifier and optional red-team run via `ctx.subagent_lifecycle.launch`
  with plugin-assembled context packets and an optional model/provider from `config_schema`.
  Confirmed in the spike (D7): fresh context, per-launch model and provider, narrowed toolsets,
  fail-closed on an unknown provider. Every launch uses a unique `correlation_id`
  (`idea:<project>:<role>:<n>`). Fallbacks stay for hosts without a second provider: `ctx.llm`
  aux task, then same-model `delegate_task`. Record which model judged what.
- **Kanban handoff**: `dispatch_tool("kanban_create")` per unit with acceptance criteria in `body`,
  `parents` for dependencies, assignee from the user's existing profiles, idempotency key
  `idea:<project>:<unit>` (spike: same key returns the same card; `parents` gates the child;
  `initial_status: "blocked"` holds a card back from workers until the user releases it). Board creation only on request (`hermes kanban boards create`; no tool
  exists for it).
- **Recheck schedule**: automation blueprint `hermes-blueprint:recheck` (weekly) creating a Hermes
  cron job; reads `kanban_list`/`kanban_show` for the project's cards.
- **Storage**: `plugin_db` (projects, phases, decisions append-only, claims, sources, predictions,
  estimates, actuals). Markdown export of the project log on request.
- **Approvals**: `dispatch_tool` skips `pre_tool_call` hooks and middleware, so our tools ask for
  confirmation themselves (`ask_choice`) before writing files, creating cards or running commands.

## Demo (in the Hermes chat, no Telegram)

`/idea start ...` → builder profile confirmed → Context briefing with source log, coverage and
"Not verified" → three variants → Critic: base rate, verdict stored, pushback handled → Plan with
A/H/W units, P10/P50/P90 and effort vs calendar ("agent work ~4 h, calendar 2 days because of
catalog review") → handoff to kanban cards → a worker picks up card 1 → `/idea recheck` shows
estimate vs actual.

## Relation to other Hermes pieces

- Reuse, don't duplicate: `creative-ideation` (methods for Generation), `grill-me` (optional deep
  dive interrogation), kanban and its workers for building, `crew` for verified execution.
- Overlap to explain in the README: elephant-goldfish (PR #147267, isolated spec review) and
  hermes-council (multi-advisor answers). We are the whole idea → plan → build → recheck arc with
  enforced evidence and calibrated estimates.
