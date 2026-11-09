# Decisions

## Open (need the owner)

**D6. Velocity ledger import (split from D3).** Hermes SessionDB metadata (opt-in) and our own
project timeline for sure. Importing Claude Code / Codex session timestamps is useful for the owner
but touches another tool's files; keep it a separate, local, opt-in script, not part of the catalog
plugin?

**D4. Second model for verifier / red-team.** Same model by default; optional second provider in
config. Which one does the owner want for the demo?

**D5. Hackathon.** Whether a second entry is allowed and the deadline: still unchecked. Pick one
entry among hermes-x-bookmarks, this plugin and the game-master idea.

## Made

- D1 (2026-11-08, owner): name **hermes-blueprint** (package `hermes_blueprint`, command `/idea`),
  standalone repo `winchxyz/hermes-blueprint`. The methodology (coordinator skill and per-phase
  reference files) is written for this plugin and ships with its own Python, tools and tests.
- D3 (2026-11-08, owner): "kinds only". `docs/research/estimation.md` lists the owner's past
  projects by kind (e.g. "3D browser sandbox game"), never by folder or project name; every number
  is kept. ghost-call keeps its name because it is a public plugin. The ledger-import question that
  was part of D3 stays open as D6.
- D7 (2026-11-08, unit 1 spike, real runs on Hermes v0.23.0 `2bd378ed`, Windows, Nous free
  tier). Method: the throwaway plugin `spike/` was loaded into a real `AIAgent` turn
  (`spike/harness.py`; why: see `spike/RUN.md`) and the model called its tool. Raw JSON stays
  local in `spike/results/` (gitignored). The spike scripts were later removed from the published
  repo: to load a plugin in process they patch Hermes internals, which a listed plugin must not
  ship (catalog rule 9). Results:
  - **`ctx.subagent_lifecycle.launch` works from a plugin tool handler** during a turn. The child
    gets only `goal` + `context`: asked to echo a codeword from `context` and any word from the
    parent chat, it returned the codeword and `PARENT=NONE`. Per-launch `model` works
    (`meituan/longcat-2.5:free`) and `provider` + `model` works (`nous` +
    `stepfun/step-3.7-flash:free`). A model the provider lacks fails as `FAILED` with the
    provider's 404 in `summary` (so the override really reaches the provider). An unknown or
    keyless provider raises `SubagentLifecycleError` before launch. `allowed_toolsets=("web",)`
    leaves the child exactly `web_search` and `web_extract`. `correlation_id` must be unique per
    parent session. The tool handler may block on `wait()`: one child took 98 s (provider retry)
    inside a single tool call without problems. No fallback needed.
  - **`dispatch_tool("web_search")` / `("web_extract")` work** (backend `parallel`, free tier).
    `web_extract` returns the page body as text (`{"results": [{url, title, content, error}]}`),
    12.5k chars for a docs page, not truncated at `char_limit=20000`; a 12-word span from the
    middle is found after whitespace/case normalization. Quote checks can run on stored text.
    Normalization must also fold typographic dashes and quotes.
  - **`dispatch_tool("kanban_create")` works** without the kanban toolset: `initial_status:
    "blocked"` keeps a card away from workers; the same `idempotency_key` returns the same task
    id; `parents` gates the child (`status: todo`, `gated: true`). Cards are created with
    `created_by: "default"` (the profile). Archiving needs the CLI (`hermes kanban archive`).
  - **Slash-command output never reaches the model** (code, not a live run: the CLI prints it,
    `cli.py:1275-1294`; the gateway returns a handled command's text as the reply before any
    agent turn, `gateway/run_inbound.py:813-858`). So `/idea start` tells the user to send a
    message; `ctx.inject_message` (needs `allow_gateway_injection`) is the optional upgrade.
  - **Tool handlers get `session_id`, `task_id`, `user_task`** (no `conversation_id`);
    `ctx.session_cwd()` and `ctx.session_surface()` were empty in a tool call. State is keyed by
    `session_id` (done in the skeleton); compression rotation is handled later via
    `parent_session_id`.
  - **Plugin tools are deferred behind Tool Search** in a default config: the model reached
    `idea_spike` through `tool_search` → `tool_describe` → `tool_call`. Our tool descriptions must
    contain the words a model would search ("blueprint", "idea", "brainstorm", "phase", "research",
    "verdict", "plan"), and the per-turn state card names the exact tool to call next.
  - Windows note: inside the Claude desktop app (MSIX) `hermes plugins enable` and the CLI's
    gateway start fail because `%LOCALAPPDATA%` writes are virtualized; run Hermes from a normal
    terminal, or use the harness.
- Six phases with fixed gates; quality comes from enforcement, not from more phases.
- Quality rules are enforced by tools and stored data (research ledger, quote check, stored verdicts,
  validated plans), not prose alone.
- Critic stays in-context by default (research-and-judgment B4); Planner and verifier run in fresh
  subagents.
- Estimates: A/H/W units, P10/P50/P90, effort vs calendar, sanity rules S1-S7, ledger over base rates.
- Discuss in the user's language, persist files in English.
- Demo in the Hermes chat itself, no Telegram.
- No message text is ever read from session history; timestamps only.
- `dispatch_tool` bypasses hooks, so every side effect asks for confirmation inside our own tool.
