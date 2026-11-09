# hermes-blueprint

Turn a raw idea into a plan you can build, inside the Hermes chat.

Most "brainstorm" prompts ask the model to be rigorous, and the model often is not: claims without
sources, a critic that folds when you push back, and estimates like "3-6 months" for something an
agent builds in an afternoon. hermes-blueprint keeps the method in prose (a bundled skill) but
**enforces the quality rules in code**: the tools refuse sloppy work and say exactly what is
missing.

```
/idea start a WhatsApp bot that books padel courts for small clubs
```

| Phase | What happens | Gate checked in code |
|---|---|---|
| 1. Understanding | short interview, your builder profile (who builds: agents, hours, accounts) | problem brief + profile confirmed |
| 2. Context | planned research: search, fetch, quote; disconfirmation and competitor sweep; independent verifier | briefing with source log, coverage, Not verified |
| 3. Generation | three really different variants | at least 3 variants |
| 4. Deep dive | the chosen variant, why | choice with a reason |
| 5. Critique | outside view first, pre-committed verdict, premortem, scoreable predictions | stored verdict |
| 6. Plan | units classed agent / human / wait, P10-P50-P90, effort vs calendar | validated plan |

Phases 1, 3, 4, 5 and 6 also need a reply from you before they close, so the agent cannot
run through them in one go; research (2) runs on its own. `/idea phase <n>` skips ahead.

Then `/idea handoff` writes a project folder and turns the plan into Hermes kanban cards, and a
weekly re-check scores the predictions and compares estimates with what really happened.

## What the code enforces

- **No source, no ✅.** A claim is ✅ only if its quote appears in a page the plugin fetched and
  stored (after folding case, whitespace, typographic quotes and dashes). Market size and traction
  need two independent sources (different domain and different content). A search snippet is a
  lead, never evidence. "Nothing like this exists" is never ✅: it needs three logged searches and
  stays 🔍.
- **Coverage you can audit.** Research tiers (quick / standard / deep) set the minimum claims,
  disconfirmation searches and competitor channels (GitHub, registries, marketplaces, app stores,
  Product Hunt, HN, Reddit, X, web). The briefing ends with the source log, coverage and a Not
  verified block, and it is refused until the gaps are closed.
- **A verifier in a fresh context.** A Hermes subagent re-fetches the sources and checks every
  claim with only the claims and the source log in hand. Unsupported claims are retracted, partial
  ones downgraded. It can run on another model.
- **A critic that does not cave.** The verdict starts from a named reference class with a sourced
  base rate, is stored before it is shown, and needs at least three scoreable predictions.
  Pushback without new evidence changes nothing; a revision must cite claims or red-team runs
  newer than the verdict and is logged as "changed because". If every probability leans your way,
  it asks why.
- **Estimates that match how you build.** Units are A (agent-bound active hours), H (your hours:
  decisions, taste, device tests, accounts) or W (outside waits: store review, API approval).
  Agent units must fit the base rates for their class or name a reason; a single plugin or bot
  is hours, and months only come from named waits. Effort and calendar are computed in code from
  your profile, with the critical path and the top calendar drivers.
- **Calibration over time.** Predictions get Brier scores (model vs you). Actual hours per unit go
  into your velocity ledger, which replaces the generic base rates once a class has 3 or more
  data points.

## Install

```bash
hermes plugins install winchxyz/hermes-blueprint
hermes plugins enable hermes-blueprint
```

The install asks whether to enable it; the second command is only needed if you said no.
Requires Hermes Agent 0.23.0 or newer. No extra Python dependencies. The web toolset must be
available for research (`web_search`, `web_extract`).

## Use

```
/idea start <your idea>     start a project and bind it to this chat
/idea status                phase, gate and what is missing
/idea phase [n] [reason]    show the phase, or move to phase n (forward only if gates are met)
/idea list | resume <id> | log | stop
/idea profile               your builder profile
/idea handoff               after the plan: what the handoff will create
/idea handoff folder <dir>  write README, PLAN, DECISIONS, RESEARCH, AGENTS into an empty folder
/idea handoff cards [--hold] create the plan's units as kanban cards
/idea recheck               progress, due predictions, estimate vs actual
/idea ledger                your velocity ledger vs the base rates
```

After `/idea start`, just talk. A short state card tells the agent the phase, its rules and the
next tool; the bundled skill `hermes-blueprint:blueprint` holds the method, one reference file per
phase.

Tools the agent uses: `idea_phase`, `idea_profile`, `idea_research`, `idea_verdict`, `idea_plan`,
`idea_recheck`.

The weekly re-check is an automation blueprint: create it from the Hermes automations catalog
(`hermes-blueprint:recheck`, Mondays 09:00 by default).

## Which model

The rules hold on any model that can call tools: no ✅ without a fetched quote, gates, the
pre-committed verdict, the plan checks. How deep the research goes and how good the judgment is
comes from the model, so the stronger the model, the better the result. In our dry runs on the
same idea:

- a small free model kept the gates but dropped the profile the user had typed and filled in
  defaults, and its research stayed shallow;
- a larger model (still on the free tier) ran all six phases in about an hour: 17 searches, 28
  pages read, 19 sourced claims, 2 overstated claims caught by the verifier and rewritten, a
  premortem tied to the evidence, and a plan of 8 agent hours and about 5 of yours over roughly
  two weeks of calendar, mostly the teammates' trial.

For a decision you care about, use a frontier model. A free model is fine for trying it out.
The verifier, planner and red team can run on a different model (see Settings).

## Settings

Under `plugins.entries.hermes-blueprint.settings` (all optional):

| Key | Default | What |
|---|---|---|
| `verifier_model`, `verifier_provider` | your main model | the fact verifier subagent |
| `planner_model`, `planner_provider` | your main model | the planner subagent |
| `redteam_model`, `redteam_provider` | your main model | the optional red-team critic; a different model gives a more independent view |
| `kanban_assignee` | `default` | Hermes profile that works the agent cards |
| `kanban_tenant` | `blueprint` | kanban tenant for the cards |

## What it touches

- **Network:** only through Hermes' own `web_search` and `web_extract`, when the agent researches.
- **Models:** the verifier, planner and red-team run as Hermes subagents (your main model unless
  you set another above). They get only the packet the plugin builds (claims, sources, profile,
  verdict), not your chat.
- **Files:** only `/idea handoff folder`, after you confirm, into a folder that is empty.
- **Kanban:** only `/idea handoff cards`, after you confirm. Re-running it does not duplicate
  cards. Human and wait units are created blocked, titled "(you)" / "(wait)".
- **Storage:** projects, sources, claims, predictions, plans and your profile live in the
  plugin's own SQLite database (`plugin_db`). It stores only what the agent records through the
  `idea_*` tools; the state card hook ignores your messages and only looks up which project is
  bound to the chat.

## Develop

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

Tests run offline against fakes of the Hermes plugin context, web tools, kanban and subagents.
`spike/smoke.py` drives the registered command and tools inside a real Hermes install (real web
tools, no model turn). Design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/PLAN.md](docs/PLAN.md), [docs/DECISIONS.md](docs/DECISIONS.md), evidence in
[docs/research/](docs/research/).

## License

MIT
