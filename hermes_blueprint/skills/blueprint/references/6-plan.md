# Phase 6: Plan

Goal: a plan estimated the way this builder actually builds: agent work in hours, the human's
work in hours, external waits in days, and the calendar computed from those, not guessed.

The failure this phase exists for: LLM plans estimate AI-built software in human-team weeks. A
single plugin planned as "several months" was built in about 5 active hours. Planning priors come
from pre-agent text; the base-rate table and the builder's own ledger replace them.

## Draft

`idea_plan(action=draft)` runs an isolated planner subagent. It gets only the stored project
(brief, choice, evidence, verdict, tripwires, profile, base rates, rules), not this conversation.
The plugin validates its plan.

- `stored`: show the returned markdown.
- `needs fixes`: fix the listed problems in the returned plan and `submit` it.
- `planner did not run`: call `idea_plan(action=rules)`, write the plan yourself and `submit`;
  tell the user the isolated planner was unavailable.

## Units

- **A** (agent-bound): code, tests, docs, assets. Active hours, each unit at most 16 h. Needs a
  `ref_class` from the table and acceptance criteria. A P50 above the class P90 needs a named
  multiplier with a reason (unfamiliar toolchain, unseen codebase, novel problem) or a split.
- **H** (human-bound): decisions, taste reviews, device and real-use tests, sign-ups, writing in
  the user's own voice, recording. Hours of the user's time. Every plan with A units has H review
  units.
- **W** (external wait): store or catalog review, API approval, tester windows, other people.
  Calendar days. A wait that depends on nothing starts on day 1.
- Every estimate is a range (P10 < P50 < P90); novel work gets a wide one.
- Gates: every green-light criterion from the critique becomes a gate with a kill threshold.

The tool computes effort (agent hours, the user's hours) and calendar days (critical path vs the
workload at the profile's hours per day) and names the top calendar drivers. Do not restate
different totals.

## Finish

Show the plan. `idea_phase(action=advance)` marks the project planned. Then tell the user:

- `/idea handoff folder <dir>` writes README, PLAN, DECISIONS, RESEARCH and AGENTS.md for the
  coding agent;
- `/idea handoff cards` turns the units into Hermes kanban cards (agent units go to the configured
  worker profile; the user's units and waits are held until they mark them done);
- a weekly re-check can be scheduled from the automation blueprint "Blueprint weekly re-check",
  or run any time with `/idea recheck`.
