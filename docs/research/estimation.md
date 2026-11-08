# Realistic build-time estimates for AI-agent builders

Research note for hermes-blueprint. Date: 2026-11-08.

**The problem.** An LLM-generated plan said a single Hermes plugin would take "several months solo with Claude Code". The plugin (ghost-call) was built, tested, documented and published with a launch video in about **5 active hours inside one calendar day**. The coding part took **about 2.4 active hours**. That is an overestimate of roughly two orders of magnitude.

**Root cause.** A typical planning prompt asks for a "time estimate" per step and a 30/60/90-day plan, but gives the model no unit of effort, no reference class and no rule that separates agent work from human work. The model falls back on its prior, which is how long software took human teams before coding agents. Scope framings such as "weekend vs. long build" or "eng / design / data weeks" make it worse. And nothing ever compares an estimate with what actually happened, so the error never gets corrected.

Confidence labels used below:
- **primary**: the number was read on the publisher's own page during this research.
- **secondary**: the number comes from coverage or a search summary of the primary source.
- **unverified**: a single secondary source, or my own reasoning.

---

## Part 1 — External evidence

### 1.1 Controlled studies: the speed-up depends on the setting

| Study | Setting | Result | Source | Confidence |
|---|---|---|---|---|
| METR RCT, early 2025 | 16 experienced maintainers, 246 real issues (about 2 h each) in their own large, mature repos; Cursor with Claude 3.5/3.7 Sonnet | **19% slower** with AI (95% CI +2% to +39%). Developers had expected a 24% speed-up, and afterwards still believed AI had sped them up by about 20%. | https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ , https://arxiv.org/abs/2507.09089 | primary (the figures are restated on the 2026 update page) |
| METR follow-up, late 2025 (published 2026-02-24) | 57 developers, 143 repos, 800+ tasks | Newly recruited developers: -4% (CI -15% to +9%). Returning developers: 18% speed-up, with a wide CI. METR calls the data "an unreliable signal" because 30–50% of developers withheld tasks they would not do without AI, and many people refused to join a study that sometimes forbids AI. METR thinks the true speed-up "could be much higher" and is redesigning the study. | https://metr.org/blog/2026-02-24-uplift-update/ | primary |
| METR, algorithmic vs. holistic scoring (Aug 2025) | Agent pull requests on real repos | PRs that passed the tests still needed about 26 min of human fixing on average before they could be merged. "Tests pass" is not the same as "done". | https://metr.org/blog/2025-08-12-research-update-towards-reconciling-slowdown-with-time-horizons | secondary |
| GitHub Copilot RCT (Peng et al., 2023) | 95 freelancers; implement an HTTP server in JavaScript (greenfield, small, well specified) | **55.8% faster** | https://arxiv.org/abs/2302.06590 | secondary |
| Google internal RCT (Paradis et al., 2024) | 96 engineers, one enterprise C++ task | About 21% faster, wide CI | https://arxiv.org/abs/2410.12944 | secondary |
| Field experiments at Microsoft, Accenture and a Fortune 100 firm (Cui et al.) | 4,867 developers | +26% tasks completed (SE 10%) | https://papers.ssrn.com/abstract=4945566 | secondary |

**What follows from these studies.** Measured speed-ups are small or negative when an expert works in a large codebase they already know and the quality bar is high. The speed-ups are large for greenfield, small, well-specified work on standard stacks. All of these studies use chat or IDE assistants, or early agents, in which a human does the work and the AI helps. None of them measures today's setup, where a solo builder hands whole features to Claude Code or Codex. The METR 2026 update says directly that its RCT design now misses the highest-uplift tasks.

### 1.2 Time horizons: how long a task an agent can finish on its own

- METR Time Horizon 1.1 (2026-01-29) gives 50% task-completion horizons of **Claude Opus 4.5 ≈ 320 min** (CI 170–729) and **GPT-5 ≈ 214 min**. Over the full history the horizon doubles about every **196 days**. Since 2024 it doubles about every **89 days**. The suite is close to saturated: few tasks remain that the newest models cannot do, and only 5 of the 31 tasks of 8 h or more have measured human baselines. — https://metr.org/blog/2026-1-29-time-horizon-1-1 — primary.
- Later models are reported at about 14.5 h (Claude Opus 4.6). METR warns that estimates above about 16 h are unreliable. — https://officechai.com/ai/exponential-progress-claude-opus-4-6-has-50-time-horizon-of-14-5-hours-on-metr-time-horizons-benchmark — secondary.
- The 80% horizon is several times shorter than the 50% horizon (original METR paper, https://arxiv.org/abs/2503.14499). — secondary; not re-checked here.

**Planning reading.** A horizon is measured in *human-expert hours of work* that an agent completes autonomously at 50% reliability. By late 2026, a unit of work that would take a skilled human 1–8 hours is routinely within one agent run. The human cost of that unit then collapses to prompting, reviewing and steering. The planning unit should therefore be the **agent session** (minutes to a few hours), not the developer-day.

### 1.3 What companies report about their own use (self-reported, so treat as an upper bound)

- **Anthropic, internal survey (Aug 2025, 132 engineers) plus about 200k Claude Code transcripts.** Claude is used in about 59% of work, up from 28%. Self-reported productivity gain is +50%, up from +20%, and 14% of respondents report more than +100%. 27% of Claude-assisted work "wouldn't have been done otherwise". Most respondents can fully delegate only 0–20% of their work. Between Feb and Aug 2025, the longest run of consecutive tool calls per transcript rose from 9.8 to 21.2 and human turns fell from 6.2 to 4.1. Engineers delegate work that is easy to verify, well defined, decoupled or repetitive. They keep design that needs "taste" and organisational context. — https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic — primary.
- **Anthropic, "Estimating AI productivity gains from Claude conversations".** Across 100k conversations, Claude estimates the typical task at about 90 min without AI and about 80% faster with it. — https://www.anthropic.com/research/estimating-productivity-gains — primary. A later reliability adjustment reportedly cut the macro estimate roughly in half. — https://the-decoder.com/anthropic-cuts-ai-productivity-forecasts-in-half-after-analyzing-claudes-real-world-failure-rates/ — secondary.
- **OpenAI, DevDay (Oct 2025).** 92% of technical staff use Codex daily. Engineers who use it merge about 70% more PRs per week. — https://venturebeat.com/ai/the-most-important-openai-announcement-you-probably-missed-at-devday-2025 — secondary, self-reported.

### 1.4 Where the speed-up is large, and where it is small or negative

| Large speed-up (estimate agent units in hours) | Small or negative speed-up (keep human-scale estimates, or add a multiplier) |
|---|---|
| Greenfield repo, small scope, clear spec | Large legacy codebase the agent has not seen, with strict review norms (METR RCT) |
| Standard, well-documented stacks (web, Python, Node, Three.js, plugin SDKs with examples) | Novel algorithms or research where the answer is unknown (e.g. cipher solving) |
| Work that is easy to verify: tests, screenshots, a CLI exit code | Work where "done" is a matter of taste: brand, art direction, game feel (needs rounds of human review) |
| Glue code, integrations with documented APIs, scaffolding, docs, tests | Physical-world feedback loops: 3D prints, devices, hardware |
| Throwaway prototypes and demos | Security- or money-critical code (contracts, custody): agent time is short but audit and review time is long |
|  | Unfamiliar or brittle toolchains (game engines, modloaders, native mobile builds) |

### 1.5 Why LLMs overestimate durations for AI-assisted work

1. **Training-data prior (hypothesis, unverified but consistent with the evidence).** Almost all duration statements in pre-2025 text describe human teams: "an MVP takes 3–6 months", sprint estimates, agency quotes. Ask a model "how long to build X" and it reproduces that distribution. Nothing in the prompt tells it that the builder is an agent working at about 10–100x human typing and lookup speed on greenfield work.
2. **Compression toward a typical value (primary).** Anthropic's validation on about 1,000 JIRA tickets found Claude's time estimates more compressed than human ones. Claude **overestimates short tasks and underestimates long ones**, and is "more prone to overestimates" overall. Its rank correlation with actual times (Spearman 0.44) is close to developers' own estimates (0.50). A small task, such as one plugin, gets pulled up toward a "typical project" length. — https://www.anthropic.com/research/estimating-productivity-gains
3. **Effort mixed up with calendar time (unverified).** Pre-AI estimates fold meetings, hand-offs, QA cycles and part-time availability into one "weeks" number. Without an explicit split, the model reports calendar-like spans as effort.
4. **Caution bias (unverified).** Overestimating feels safe, so a model prefers it. The planning-fallacy literature warns about the opposite error, which pushes models further toward long estimates.
5. **Humans miscalibrate too, in both directions.** In the METR RCT, developers predicted a speed-up and actually got a slow-down. In a GPT-4o study with 836 participants, people estimated their unaided times well but **underestimated** AI-assisted times (https://www.themoonlight.io/en/review/cognitive-offloading-and-the-speedup-illusion-in-human-ai-interaction — secondary). Neither the model nor the builder should be trusted without a reference class. That is the core argument for a personal velocity ledger.

### 1.6 Estimation methods that work

- **Reference class forecasting** (Kahneman and Tversky's "outside view", put into practice by Flyvbjerg). Do not build the estimate up from the plan's own story. Start from the actual outcomes of similar past projects, then adjust. Flyvbjerg and Budzier (HBR 2011, "Why Your IT Project May Be Riskier Than You Think") show that IT-project overruns are fat-tailed. — secondary (well-established literature; not re-fetched).
- **Planning fallacy.** People underestimate their own task times even when they know about past overruns (Buehler, Griffin and Ross, 1994). The fix is the same outside view. Note that with agents, the *model's* bias runs the other way: it overestimates agent work and underestimates human waits.
- **Decomposition into small units.** Errors partly cancel across units, and small units are easier to match to a reference class. Jørgensen's review of expert estimation (J. Systems and Software, 2004) finds that decomposition plus historical data beats unaided judgement. — secondary.
- **Three-point estimates** (PERT): optimistic, most likely, pessimistic, with mean ≈ (O + 4M + P) / 6. Report a P10/P50/P90 range rather than a single number. Check calibration afterwards: about 80% of actuals should fall inside P10–P90.
- **Separate agent-bound work from human-bound work and external waits.** This is the most important change. In practice these waits dominate calendar time for an agent builder. Examples:

| Human-bound or external-wait item | Typical duration | Source / confidence |
|---|---|---|
| Google Play, new personal developer account (created after 2023-11-13): 12 testers opted in for 14 continuous days before production access | **≥ 14 days, plan about 3 weeks** | https://support.google.com/googleplay/android-developer/answer/14151465 — secondary (official page via search) |
| Apple App Store review | Usually 24–48 h; Apple promises no timeline, and first submissions can wait days | https://developer.apple.com/forums/thread/839107 — secondary |
| Steam Direct | $100 per product; 30-day wait between payment and release | https://oceanviewgames.co.uk/resources/platform-readiness-checklist — secondary |
| US SMS via Twilio (A2P 10DLC brand plus campaign) | Days to about 4 weeks; AT&T manual review alone can take 2–4 weeks. Since 2026-06-30, new campaigns need privacy-policy and terms URLs | https://www.twilio.com/en-us/changelog/a2p-10dlc-campaign-registration-will-require-privacy-policy-and- (primary for the policy) ; https://www.telphiconsulting.com/blog/twilio-a2p-registration-timeline (secondary for the timing) |
| API access, billing and rate-limit tiers, OAuth app review, marketplace or catalog review | Hours to weeks, depending on the provider | Varies; check per provider (unverified) |
| Accounts, KYC, payments onboarding, company formation, legal and terms text | Hours to weeks | unverified |
| Design and taste rounds (brand, art direction, game feel) | One human review cycle per round; usually 2–4 rounds | Owner's history (Part 2): several rounds were rejected before a pick |
| Physical iterations (3D prints, devices) | Print time plus a test per round | Owner's history |
| Waiting on other people: testers, judges, partners, support tickets | Unbounded; put a deadline on it and plan around it | Owner's history (one project stalled on a platform support ticket) |
| Marketing and distribution: posts, video, outreach | Agent-assisted, but needs human approval and scheduling | Owner's history: a 30 s promo reel took 1.3–1.5 active h |

---

## Part 2 — The owner's own reference class (velocity ledger)

### Method

The script is `velocity/velocity.py` in the session scratchpad. It is not in the repo. It reads every `~/.claude/projects/<folder>/*.jsonl` session transcript plus that session's `subagents/*.jsonl`, and only uses timestamps, `cwd`, and the paths and commands inside tool calls. It writes no message text.

- **Project.** Worktree folders (`--claude-worktrees-*`) are merged into their base project. Four umbrella folders (mixed web toys, two video folders, scratch tests) are split by the sub-directory each session mostly touched.
- **Active hours.** Take the union of all event timestamps for the project, from main and subagent transcripts, so parallel agents are not double-counted. Sum the gaps between consecutive events, counting a gap only if it is shorter than 20 minutes. This is roughly "time the builder and agent were engaged".
- **Agent-busy hours.** Same union, but excluding gaps that end in a new human prompt, and capped at 60 min. This is roughly "time the agent was working".
- **Calendar days.** Time from first to last event. **Days with activity** counts distinct UTC dates.
- **Commits.** Number of `git commit` commands the agents issued, including subagents. This is a proxy, not verified commits.

Coverage: 311 sessions across 80 projects. After excluding scratch, temp, automated-pipeline and non-build folders, 63 projects have at least 1 active hour.

**Headline distribution (63 build projects):**

| Metric | Value |
|---|---|
| Median active hours per project | **7.3 h** |
| P25 / P75 / P90 | 2.9 h / 19.3 h / 42.3 h |
| Largest project | 170 h (Telegram mini-app launchpad with contracts, 28 calendar days) |
| Share of projects under 10 active h | **57%** |
| Share under 25 active h | **81%** |
| Median calendar span | **3.1 days** |
| Active hours per active day on the big projects | about 4.5–7 h/day (e.g. 170 h / 26 days, 86 h / 14 days, 119 h / 26 days, 48.5 h / 7 days) |
| Total active hours in the ledger | about 1,126 h (May–Nov 2026) |

### Representative projects

Kinds and scopes are summarised from the memory index and repo READMEs. Hours are lower bounds wherever work also happened in other tools (Codex, Hermes, chat, Blender, slicers) or in other folders.

Projects are listed by kind only; private project names are left out. The one exception is
ghost-call, which is a public plugin.

| Project (kind) | Scope (one line) | Sessions | Active h | Agent-busy h | Calendar days (days active) |
|---|---|---|---|---|---|
| **ghost-call** (public Hermes plugin) | Call copilot plugin: telephony + realtime voice integration, tests, dev demo, docs, launch video, catalog assets | 1 | **5.0** (see split below) | 3.8 | 0.6 to v1 (1) |
| Seeded drawing website | 5 styles, public with Pages | 1 | 1.6 | 1.3 | 0.07 (1) |
| Voxel sandbox browser game | Single-file build | 1 | 1.8 | 1.8 | 0.07 (1) |
| 3D typewriter web app | Cozy 3D typewriter, live on Pages | 1 | 2.4 | 2.0 | 0.9 (2) |
| Browser puzzle game with level generator | 100 generated levels plus verifier | 1 | 2.9 | 2.3 | 0.8 (2) |
| Isometric voxel 3D demo | Three.js voxel scene | 1 | 3.5 | 2.7 | 0.2 (1) |
| Picture-cube website | Picture cube, dataset, promo shots | 1 | 3.8 | 3.6 | 0.8 (2) |
| Photo-to-text-art web app | Output for 7 platforms plus film | 3 | 6.3 | 3.5 | 1.4 (2) |
| Schematic-to-3D-print desktop app | Converter (PySide6, GL, tests) | 1 | 7.3 | 5.8 | 0.9 (2) |
| 3D browser sandbox game | 25 tools, 4 test suites, public | 1 | 9.0 | 7.9 | 7.9 (3) |
| Cipher solver (research) | Cipher attack with solvers (novel problem) | 1 | 8.4 | 2.1 | 2.1 (2) |
| Procedural 3D scene | Procedural 3D environment | 1 | 10.7 | 9.4 | 1.2 (2) |
| Photo-to-one-line-art web app | Several path modes, film | 1 | 14.2 | 6.3 | 2.2 (3) |
| WebGL ocean game | Ocean, ephemeris sky, buoyancy solver | 2 | 15.8 | 14.7 | 1.7 (3) |
| Narrative browser game | Several briefs in parallel worktrees | 3 | 20.3 | 14.3 | 3.1 (4) |
| Minecraft modpack | 1.3k quests, ported mods, test client (brittle toolchain) | 2 | 21.3 | 17.6 | 31 (11) |
| Larger single-player browser game | Single-player browser game | 1 | 29.6 | 24.0 | 8.3 (9) |
| 3D-print design families | Planter and storage families; physical test prints and taste rounds | 6 | 42.3 | 32.7 | 45 (17) |
| Hand-tracking game | Built with many parallel worktree agents | 26 | 48.5 | 40.2 | 5.8 (7) |
| Multi-part product | Taken to a pre-release audit | 10 | 67.3 | 54.3 | 14.9 (10) |
| Hackathon DeFi app with contracts | Deployed contracts and live-funds testing | 4 | 86.4 | 72.4 | 17.9 (14) |
| Electron design-studio desktop app | Electron + Agent SDK design studio | 32 | 118.7 | 82.1 | 43.8 (26) |
| Telegram mini-app launchpad with contracts | Smart contracts and docker stack | 12 | 169.7 | 132.7 | 28.5 (26) |
| Two brand promo videos | 30 s each, built on a shared motion pipeline | 1 each | 1.3 / 1.5 | 1.2 / 1.4 | same day |
| Finance-shorts video series | Pipeline and research | 3 | 24.5 | 20.8 | 13.3 (5) |

### The ghost-call case, split by phase

The session transcript also includes video production, catalog work, and later unrelated work (excluded). The split below is by human turn, classified by the paths and commands the agent touched:

| Phase | Turns | Active h | Agent-busy h | Elapsed window (UTC) |
|---|---|---|---|---|
| Plugin build: scaffold, integrations, tests, README, dev demo | 1–11 | **2.37** | 1.64 | 11-06 18:26 → 11-07 02:36. 8.2 h elapsed, including a break of about 5 h |
| Launch video and README media | 12–22 | 1.48 | 1.76 (renders ran past the 20-min cut-off) | 11-07 02:36 → 07:28 |
| Catalog assets, docs, Q&A | 23–34 | 1.19 | 0.44 | 11-07 07:28 → 09:01 |
| **Total to the v1 public release** | 1–34 | **≈ 5.0** | ≈ 3.8 | **14.6 h elapsed, 1 calendar day** |

Not in the ledger:
- The design and planning work that happened before the first prompt. The session starts from a prepared brief.
- The human-bound remainder, which is still open: a live run against the real voice API, a phone number and real-call testing. These are exactly the units a plan should list separately as external or human-bound. They will probably dominate calendar time from here.

**What the ledger says for planning:**

1. A single plugin, web tool or static site is **1–8 active hours**: P50 about 3 h, P90 about 10 h. It fits in a day.
2. A polished game or app with custom rendering is **10–30 h**: 2–9 calendar days at the owner's pace.
3. Multi-component products with contracts, money or many surfaces are **50–170 h**: 2–6 calendar weeks. In these, calendar time is driven by review rounds, live-funds testing, audits and other people.
4. Projects with physical or taste loops (3D prints, brand, video series) have **calendar/active ratios of 10–45x**: the 3D-print design families took 42 h over 45 days, and the modpack took 21 h over 31 days. The waits, not the agent, set the pace.
5. Parallel worktree agents raise throughput per active hour: the hand-tracking game logged 48.5 union hours against 75.6 summed session-hours. That is about 1.6x concurrency.

Caveats: active hours include short human reading and typing gaps. They miss long unattended runs, which the agent-busy figure partly recovers, and they miss work outside Claude Code. Human-prompt counts are missing for sessions before about late July, when the transcript field did not exist. Umbrella-folder splits are heuristic.

---

## Part 3 — Design: builder profile and estimation procedure

### 3.1 Builder profile (stored once per user, reused across projects)

```yaml
builder:
  team: solo            # solo | pair | team(n)
  agents: [claude-code, codex, hermes]   # what does the building
  parallel_agents: 1-4  # typical concurrent agent sessions / worktrees
  hours_per_day: 4-7    # realistic engaged hours on an active day
  active_days_per_week: 5
  skills: [web, python, three.js, smart-contracts, video, 3d-print]  # where the human can judge/verify quickly
  weak_spots: [native-mobile, game-engines]                          # where verification is slow
  accounts_ready: [github, pages, openai-api, twilio, app-store?, play-console?, steam?]
  distribution: [x-account, telegram-channel, github-stars]          # existing audience
  budget_usd: {one_time: 0-500, monthly: 0-100}
  velocity_ledger: on   # optional; actuals per past project, stored by the plugin
```

The coordinator asks for missing fields in Phase 1, using at most three questions. Anything not answered gets a default, and the default is labelled as an assumption.

### 3.2 Estimation procedure (the Planner must follow it)

1. **Decompose into work units.** Each unit is about 0.5–6 h of agent-bound work, or one discrete human or external step. If an agent-bound unit is over 16 active hours, split it.
2. **Classify each unit:**
   - **A — agent-bound.** Code, tests, docs, assets the agent can generate and verify.
   - **H — human-bound.** Decisions, taste reviews, device or physical tests, sign-ups, writing a post in your own voice, recording.
   - **W — external wait.** App or marketplace review, API approval, A2P registration, tester windows, payouts, other people.
3. **Estimate the A units from the reference class.** Use the builder's own ledger if it exists; otherwise use the base rates below. Give P10/P50/P90 in **active hours**. Apply multipliers only with a named reason:

| Unit class (A) | P10 | P50 | P90 | Basis |
|---|---|---|---|---|
| Scaffold, single-file tool, static page, plugin skeleton | 0.3 h | 1 h | 3 h | Ledger (seeded drawing website, voxel sandbox game, ghost-call plugin build) |
| Integration with one documented external API, with tests | 0.5 h | 1.5 h | 4 h | Ledger (ghost-call build) |
| Polished web toy or app feature with custom rendering | 1 h | 3 h | 8 h | Ledger (3D typewriter app, photo-to-text-art app, puzzle game with level generator) |
| Game or app with physics, rendering or a solver core | 5 h | 12 h | 30 h | Ledger (WebGL ocean game, photo-to-one-line-art app, larger browser game) |
| Multi-component product slice (backend + frontend + deploy) | 10 h | 30 h | 80 h | Ledger (multi-part product, Electron design studio) |
| Contracts or real-money code (excluding audits) | 10 h | 40 h | 100 h | Ledger (hackathon DeFi app, Telegram mini-app launchpad) |
| Promo video / reel (with an existing pipeline) | 1 h | 2 h | 6 h | Ledger (brand promo videos, ghost-call launch video) |

   Multipliers (each needs a stated reason):
   - ×1.5–3: unfamiliar or brittle toolchain (game engines, modloaders, native mobile).
   - ×2–4: large existing codebase the agent has not seen.
   - ×2–5 and a wider P90: a novel algorithm or research question.
   - ×1 for code, but add H review units: security or money-critical code.

4. **Estimate H and W units separately**, in **calendar days**, from Part 1.6 or from provider documentation. Mark each with "start now: yes/no", because most W items can run in parallel with A work.
5. **Compute effort and calendar time separately:**
   - Effort = Σ A (P50, with the P10–P90 range) + Σ H.
   - Calendar = max(critical path of W items, (Σ A + Σ H) / (hours_per_day × parallel factor)), plus taste rounds.
   - Show both. Never put a single "it will take X weeks" without the split.
6. **Output table:** unit · class (A/H/W) · P10/P50/P90 · depends on · can start today? Then two total lines, effort and calendar, and the top three calendar drivers.

### 3.3 Sanity rules (checked by the Planner, enforced by the Critic)

- **S1.** A single plugin, CLI, bot, static site or one-screen web tool built by an AI agent is **hours, not weeks**. Agent-bound P50 is ≤ 8 active h. If the plan says more than 2 days of agent-bound effort for it, the plan must name the unit that causes it.
- **S2.** Any single-builder MVP whose agent-bound effort exceeds **10 working days** (about 50 active h) must list the specific reason: novel algorithm, unseen codebase, money or security, hardware, many platforms. Otherwise, re-scope.
- **S3.** **"Months" may appear only in calendar time**, and only when a named W or H item causes it (store review, tester windows, audits, audience growth). It never describes agent-bound effort.
- **S4.** Every estimate is a range. If P90/P50 is below 1.5 on a novel unit, widen it.
- **S5.** The definition of done includes verification: tests pass **and** the result is checked for real use (METR's mergeability gap). Budget one H review unit per A milestone.
- **S6.** Start long W items on day 1: tester windows, API approvals, A2P, store accounts.
- **S7.** If the ledger has at least 3 projects in the same class, its P50 overrides the base rate. State "from your ledger: n = k".

### 3.4 Recheck recalibration loop

1. At plan time, append an **Estimate Log** entry to the project record listing each unit's class, P10/P50/P90 and the planned calendar date.
2. At recheck, collect actuals. Either run the optional velocity script on the project's transcript folder, or ask the user for active hours and dates per unit.
3. Report per unit class:
   - the ratio actual/P50,
   - whether the actual fell inside P10–P90 (the target is about 80% of units),
   - which W items set the calendar.
4. Update the velocity ledger with the actuals. Shift the class P50 toward the observed median using exponential smoothing (α ≈ 0.3), and widen or narrow the range until about 80% of past actuals fall inside P10–P90.
5. **Critic angle.** A large miss in an A estimate is a **tuning** problem. A miss caused by an unforeseen W item, or by a thesis change mid-build, is a planning or **thesis** problem and goes into the re-critique verdict.

---

## Design consequences for the plugin

1. **Planner** (fresh subagent, output checked by the plan validator):
   - A required section **"Effort and calendar estimate"** that implements 3.2: units, A/H/W classes, P10/P50/P90, and effort vs. calendar totals.
   - The step table has "Class · P10/P50/P90 · start today?" instead of a free-text time estimate.
   - A pilot or mini-MVP is triggered by **calendar** time with W items named, not by agent effort.
   - Anti-pattern in the prompt: "Do not estimate agent-built software in human-team weeks or months; use the reference class."
2. **Critic.** A check named "Estimate realism" applies S1–S7 and flags both over-estimates of agent work and under-estimates of human and external waits.
3. **Variant framing.** Scope axes are expressed as "an afternoon / a day / a week of agent sessions" or "agent-hours + human review days + external waits", never in human-team weeks. Each project kind gets its W-item catalogue (stores, payments, platform approvals, audience time).
4. **Project record.** Stores the builder profile as used and an **Estimate Log** (estimate, then actual, then ratio).
5. **Phase 1.** Read the builder profile; ask only for missing fields (agents used, hours per day, accounts ready).
6. **Optional velocity import** (opt-in, local only). Builds the ledger from coding-agent session timestamps (Claude Code first; adapters for Codex and Hermes later). It never reads or stores message text.
7. **Recheck.** Runs 3.4: compare estimate with actual and update the ledger.
8. **Base-rate table.** Ship the table in 3.2 as a dated reference file with sources, and review it every quarter, because time horizons double about every 3–6 months.

## Open questions

1. Should the plugin ship the transcript-reading script, or only document it? It reads private local files. It needs a cross-platform path, worktree merging, and an explicit opt-in.
2. Which unit to plan in: *active hours*, which includes human attention, or *agent-busy hours*? The proposal is active hours for effort and agent-busy hours for throughput. Is that too complex for users?
3. How should parallel agents count? Union time understates total compute; summed time overstates human effort. Should the profile's `parallel_agents` be a declared value or measured from the ledger?
4. Codex and Hermes transcripts have different formats. Is there a common minimal schema (timestamps plus tool calls) worth defining?
5. How to treat pre-build planning, such as the brief that started ghost-call. Should brainstorm sessions themselves be logged as an H unit?
6. Base rates will go stale quickly. Should each table carry a "valid until" date and a model-generation tag (e.g. "Opus 4.x / GPT-5.x era")?
7. For money or security work, where should agent effort stop and the audit or review W item start? What fixed review budget is right (e.g. a % of A hours)?
8. The ghost-call live run (real voice API, phone number, carrier registration) is still outstanding. Its actual duration would be the first measured W item in the ledger, and worth recording at the first recheck.
