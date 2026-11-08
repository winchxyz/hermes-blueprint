# Hermes platform research for hermes-blueprint

Researched 2026-11-08 against `NousResearch/hermes-agent` `main` at `856e7580` (2026-11-08 19:55 UTC),
with spot checks against `v0.23.0` (`2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`). References are
`path:line` at `856e7580` unless a tag is named.

This report extends the x-bookmarks platform report
([winchxyz/hermes-x-bookmarks `docs/research/hermes-platform.md`](https://github.com/winchxyz/hermes-x-bookmarks/blob/main/docs/research/hermes-platform.md), "XB" below). It does not
repeat `register()`, tools, slash commands, `ctx.llm`, cron blueprints, skills via `skill_manage`,
secrets/OAuth, manifest v2, validate/doctor or the CI pin; see XB sections 1-8 for those.

Short names: `kanban.md` = `website/docs/user-guide/features/kanban.md`, `deleg.md` =
`website/docs/user-guide/features/delegation.md`, `hooks.md` = `website/docs/user-guide/features/hooks.md`,
`index.md` = `website/docs/developer-guide/plugins/index.md`, `ctx` = `hermes_cli/plugins_context.py`,
`sdk.md` = `website/docs/developer-guide/desktop-plugin-sdk.md`, `public-api.md` =
`website/docs/developer-guide/plugins/public-api.md`, `catalog README` = `plugin-catalog/README.md`.

## Corrections and additions to XB

1. **`ctx.dispatch_tool` bypasses plugin hooks and toolset gating.** XB said it "goes through the normal
   approval/redaction pipeline". In code it calls `registry.dispatch()` directly (`ctx:483-492`,
   `tools/registry.py:972-1000`). That path does **not** run `check_fn` (so a tool works even when its
   toolset is not enabled for the profile), does **not** fire `pre_tool_call` hooks or tool middleware
   (those live in `model_tools.py:789-809`, `handle_function_call` at `model_tools.py:897`). Guards that
   live **inside** a tool handler still apply: terminal dangerous-command approval, the `write_file`
   denylist and `HERMES_WRITE_SAFE_ROOT` (`website/docs/user-guide/security.md:369-424`).
   Consequence: other plugins' gates (for example plan-mode's write block) do not see our dispatched
   writes; we must do our own confirmation.
2. **Plugin skills ARE listed in `<available_skills>`** (XB open question 5). `agent/prompt_builder.py:1189-1218`
   builds rows for every skill of an enabled plugin and adds them at line 1376. `index.md:1216` ("not
   listed") is stale. Each row is the qualified name plus a description clipped to 60 characters
   (`agent/skill_utils.py:846-861`), roughly 15-25 tokens per skill per session.
3. **Plugin skills become slash commands** `/<plugin>:<skill>` on interactive surfaces only (CLI, TUI,
   Desktop), not on messaging platforms (`agent/skill_commands.py:675-705`). So `/hermes-blueprint:start`
   works in Desktop/CLI; Telegram/Discord need a `ctx.register_command`.
4. **`hermes_state` is a public module** (`public-api.md:57`), so `SessionDB` is a supported read
   path for session history (section 5).
5. **`ctx.subagent_lifecycle`** (public, `agent.subagent_lifecycle`, `public-api.md:37`) launches fresh
   subagents **with a per-launch `model` and `provider`** from plugin code (section 2). Exists at `v0.23.0`
   (`hermes_cli/plugins.py:387` at the tag).
6. Built-in slash commands `/plan`, `/review` and `/goal` exist (`hermes_cli/commands.py:151,160,166`);
   a plugin command with the same name is silently dropped (`ctx:466-472`). `/idea` is free; no catalog
   entry registers it.

## 1. Kanban

### What it is

A durable SQLite board per profile home, shared across profiles: `~/.hermes/kanban.db` for `default`,
`~/.hermes/kanban/boards/<slug>/kanban.db` for named boards (`kanban.md:141-158`). Task statuses:
`triage | todo | ready | running | blocked | review | done | archived`; parent -> child links gate
`todo -> ready` (`kanban.md:124-136`). A dispatcher inside the gateway ticks every 60 s, claims ready
tasks and spawns `hermes -p <assignee> chat -q <prompt>` in the task's workspace
(`kanban.md:136`, `website/docs/user-guide/features/kanban-worker-lanes.md:39-55`). Kanban vs
`delegate_task`: kanban is the durable, resumable, human-in-the-loop queue; `delegate_task` is a
fork/join function call (`kanban.md:97-120`).

### How a plugin creates a board

There is **no tool and no public Python API to create a board.** Options:

| Route | Status | Notes |
|---|---|---|
| `ctx.dispatch_tool("terminal", {"command": "hermes kanban boards create <slug> --name ... --description ... --default-workdir <abs path>"})` | Supported (public tool) | Terminal approval rules apply; slug rules `kanban.md:197-200`; flags `hermes_cli/kanban_parser.py:109`. Shell command must be disclosed (catalog rule 13). |
| User runs `/kanban boards create ...` or uses Desktop/dashboard "New board" | Supported | `/kanban` reuses the CLI argparse tree (`kanban.md:1072-1087`); dashboard modal fields slug, name, description, icon, project dir, Project (`kanban.md:206-243`). |
| `from hermes_cli.kanban_db import create_board` | Private | Not in `public-api.md`; validate warns (rule 9). Crew does this kind of thing (it imports `hermes_cli.kanban_db_connect` / `kanban_db_notify`, `Crew/__init__.py:1138-1139`). Avoid. |
| `kanban_create(board="<new-slug>")` | **Refused** | `connect()` refuses to create a board DB without its metadata (`hermes_cli/kanban_db_connect.py:667-681,715-735`). |
| Use the `default` board (or the user's current one) with a `tenant` per project | Supported | Tenants are a soft namespace inside a board (`kanban.md:136`); boards are the hard isolation. |

Recommendation: default to the user's current board with `tenant: "idea-<project-slug>"`; offer
"create a dedicated board" as an explicit step that runs `hermes kanban boards create` through
`dispatch_tool("terminal")` after the user confirms (or tells them the `/kanban boards create` line).

### How a plugin creates cards

Use `ctx.dispatch_tool("kanban_create", {...})` (documented for plugins: `index.md:1938-1958`). It works
without the `kanban` toolset being enabled for the chat profile because dispatch skips `check_fn`
(correction 1). Handler: `tools/kanban_tools.py:1095-1154`; schema `tools/kanban_tools_schemas.py:386-520`.

| Plan field | `kanban_create` arg | Ref |
|---|---|---|
| Title | `title` (required) | schema 396 |
| Description + acceptance criteria | `body` (markdown; worker reads it via `kanban_show`) | schema 403 |
| Dependencies | `parents: [task_id, ...]` (child waits in `todo` until all parents `done`; returns `gated: true`) | schema 408, `kanban.md:497-511` |
| Who builds it | `assignee` (required, must be an existing profile name) | schema 397 |
| Priority | `priority` (int) | handler 1136 |
| Where it works | `workspace_kind: scratch|dir|worktree`, `workspace_path` (absolute), or `project` (Hermes Project id/slug -> per-task git worktree) | schema 427-445 |
| Extra know-how | `skills: [...]` (must be installed on the assignee profile) | schema 471, `kanban.md:632-667` |
| Model per card | `model` + `provider` | schema 505-515, `kanban.md:669-683` |
| "Keep going until the acceptance criteria hold" | `goal_mode: true`, `goal_max_turns` (aux judge checks title+body as acceptance criteria) | schema 484, `kanban.md:716-736` |
| Idempotent re-runs of the handoff | `idempotency_key` (returns the existing id) | schema 451, `kanban.md:391-400` |
| Hard time cap | `max_runtime_seconds` | handler 1144 |
| PR gate | `completion_contract: OWNER/REPO` or `local-only` | `kanban.md:48-56` |
| Namespace | `tenant`, `board` (existing slug) | schema 34-41 |

Do **not** set `triage: true`: with `kanban.auto_decompose: true` (default) the dispatcher rewrites and
fans out triage cards with its own decomposer (`kanban.md:782,804-816`). Our plan is already decomposed;
cards should land in `todo`/`ready`. If we ever want Hermes to flesh out a one-liner, `kanban specify`
(`hermes_cli/kanban_specify.py:1-40`) is the built-in single-card spec rewriter (title + body with
goal/approach/acceptance criteria), reachable only via CLI, `/kanban specify`, or the dashboard REST.

Dependencies after the fact: `ctx.dispatch_tool("kanban_link", {"parent_id", "child_id"})`; refused if
the child is already running; never link a support card to the card it unblocks (`kanban.md:114-118`).

### What a worker needs

- **A profile per assignee** that exists on the machine (`hermes profile create <name> --description "..."`,
  `kanban.md:822`). Unknown assignees stay in `ready` with a `skipped_nonspawnable` event and show as
  `stranded_in_ready` in `hermes kanban diagnostics` (`kanban-worker-lanes.md:35-37,135`).
- **A model and credentials in that profile**: workers read their own `~/.hermes/profiles/<name>/config.yaml`
  and `.env`; recommended split is frontier orchestrator, inexpensive workers (`kanban.md:685-703`).
  Per-card `model`/`provider` overrides it. A revoked key or missing model parks the card `blocked`
  after one attempt (`kanban.md:585-600`).
- **Toolsets**: the lifecycle tools (`kanban_show/complete/block/heartbeat/comment/...`) are injected
  automatically with the `KANBAN_GUIDANCE` prompt block; everything else (terminal, file, web) comes from
  the worker profile's own toolsets (`kanban.md:457-475,561-575`). The orchestrator convention is a
  profile limited to `kanban`, `gateway`, `memory` (`kanban.md:765`).
- **A gateway running** (`hermes gateway start`) because the dispatcher is embedded
  (`kanban.dispatch_in_gateway: true`, `kanban.md:314-321`), or `hermes kanban dispatch` from cron.
- **A workspace**: `scratch` (deleted on completion; only declared `artifacts` survive), `dir:<abs path>`
  (preserved), `worktree` (git, preserved) (`kanban.md:131-134`). A board's `default_workdir` or a bound
  Hermes Project gives every new card the project folder (`kanban.md:221-237`). For this plugin the
  scaffold folder is the natural `dir:` / Project root.
- **Skills on the assignee profile** if cards carry `skills:` (no runtime install, `kanban.md:665-667`).
- Our plugin enabled in the worker profiles only if we want our hooks to fire there (lifecycle hooks
  `kanban_task_completed/blocked` fire in the **worker** process, `kanban_task_claimed` in the
  dispatcher; `kanban.md:705-714`).

### Reading status back (progress re-checks)

- `ctx.dispatch_tool("kanban_list", {"board", "tenant", "status", "assignee", "include_archived", "limit"})`
  (schema `kanban_tools_schemas.py:64-90`) and `ctx.dispatch_tool("kanban_show", {"task_id"})` (title,
  body, status, runs/attempts, parent handoffs, comments, recent events; schema 47-62). `kanban_list` is
  orchestrator-only: refused inside a dispatcher-spawned worker (`kanban_tools.py:301-309`), fine from a
  chat session or cron.
- Runs table: one row per attempt with outcome, profile, elapsed, summary (`kanban.md:1342-1420`) -> real
  per-card durations for the velocity ledger.
- Push-style: register hooks `kanban_task_completed` (payload `task_id, profile_name, board, assignee,
  run_id, summary`), `kanban_task_blocked`, `on_kanban_task_updated`, `on_kanban_dispatch_tick`
  (`hooks.md:495-501`, valid names `hermes_cli/plugins.py:164,179`). Store a card-id -> project-id map
  in plugin data so the hook can update our ledger.
- Comments: `ctx.dispatch_tool("kanban_comment", {"task_id", "body"})` to leave re-check notes on cards.

### What the board looks like (Desktop and dashboard)

- Dashboard: bundled plugin `plugins/kanban/dashboard/` (`manifest.json`: tab `/kanban` after Skills,
  `plugin_api.py` with 40+ REST routes including `/boards`, `/tasks`, `/links`, `/tasks/{id}/estimate`).
  Columns triage / todo / ready / running (optionally lanes per profile) / blocked / done; cards show id,
  title, priority, tenant, assignee, comment/link counts, a progress pill `N/M` children done; click opens
  a drawer with editable description (markdown), dependency chip editor, status actions, Decompose /
  Specify for triage cards, result, comments, last 20 events; live via a websocket on `task_events`
  (`kanban.md:767-800`).
- Screenshots at the pinned commit:
  [board overview](https://raw.githubusercontent.com/NousResearch/hermes-agent/856e75808d1d6d985b06e9e882f2814ab4e4aa5d/website/static/img/kanban-tutorial/01-board-overview.png),
  [pipeline with dependencies](https://raw.githubusercontent.com/NousResearch/hermes-agent/856e75808d1d6d985b06e9e882f2814ab4e4aa5d/website/static/img/kanban-tutorial/08-pipeline-auth.png),
  [card drawer](https://raw.githubusercontent.com/NousResearch/hermes-agent/856e75808d1d6d985b06e9e882f2814ab4e4aa5d/website/static/img/kanban-tutorial/03-drawer-schema-task.png)
  (`website/docs/user-guide/features/kanban-tutorial.md:21-40,93,150`).
- Desktop: a native Kanban page (`apps/desktop/src/plugins/kanban/board.tsx`, `drawer.tsx`,
  `orchestration.tsx`, `model-override.tsx`) with a **Board** switcher in the header (rename, configure,
  export, import, create, archive) that keeps its own selection and does not move the CLI's `current`
  board (`kanban.md:244-253`).
- Plugins can decorate Desktop kanban cards with text chips via `KANBAN_CARD_AREAS.badges`
  (`decorate(card)` gets `id, status, tenant, assignee`; `sdk.md:857-946`). That is where our time
  estimate per card ("est 3h, p80 6h") can appear on the native board.

## 2. Sub-agents

### Three ways to get a fresh context

| Mechanism | From where | Model/provider override | Tools | Result |
|---|---|---|---|---|
| Agent calls `delegate_task` (instructed by our skill or by our tool's return text) | Model | **No per-task model** with the default backend; global `delegation.model/provider` only (`deleg.md:264-294`). With the official `advanced-delegation` plugin, `delegation.backend: model_map` or `profile_routes` adds a per-task option the model picks (`deleg.md:296-336`). | Inherits the parent's toolsets; no `toolsets` parameter (`deleg.md:375-386`; the `index.md:1906-1914` example passing `toolsets` is stale, schema `tools/delegate_tool.py:793-878`). | Child summary, optional `output_schema` with one correction retry (`deleg.md:55-79`). Runs in the background and posts back. |
| `ctx.dispatch_tool("delegate_task", {"tasks": [...]})` | Slash command handler or hook | Same as above | Same | Same; documented for plugins (`index.md:1899-1935`). |
| **`ctx.subagent_lifecycle.launch(SubagentLaunchRequest(...))`** | Plugin **tool handler or hook during an active agent turn** (fails closed outside a turn) | **Yes**: `model=` and `provider=` per launch; precedence request > `delegation` config > parent; the provider must be configured, else `SubagentLifecycleError` before launch. Not exposed to the model; the plugin chooses. Ignores `delegation.backend`. | `allowed_toolsets` narrows (cannot widen); `blocked_tools`, `working_directory`, per-launch timeout are rejected | Serializable handle; `wait`, `status`, `steer`, `cancel`, `result`; terminal result capped at 32k characters, no transcript; kept in process for 1 hour; not resumed after restart (`website/docs/developer-guide/subagent-lifecycle-api.md:1-90`, `agent/subagent_lifecycle.py:297-315,463-472`). |

A fourth, single-call option needs no subagent: `ctx.llm.complete_structured(..., task="critic")` with
`ctx.register_auxiliary_task("critic", ...)` (XB section 2). The user picks the critic's model in
`hermes model` -> auxiliary; no trust-gate override needed. One bounded call, no tools, no web.

### Mapping to plugin roles

- **Planner (Phase 6, isolated)**: our tool `idea_plan_dispatch` gathers the chosen variant, critique
  verdicts, constraints and decision log from plugin data and calls `ctx.subagent_lifecycle.launch`
  with `allowed_toolsets=("file",)` (or none) and a JSON `output_schema`-like contract in the goal; or the
  skill tells the agent to call `delegate_task` with `output_schema`. The lifecycle route is better: the
  plugin, not the model, assembles the context packet (no leakage of brainstorm chatter), and it can
  route the planner to a configured stronger model.
- **Critic (Phase 5, forced adversarial, cross-model)**: `ctx.subagent_lifecycle.launch(model=..., provider=...)`
  from a plugin tool, with the model taken from our `config_schema` (`critic_provider`,
  `critic_model`). With `allowed_toolsets=("web",)` it can fetch counter-evidence. Fallback when no
  second provider is configured: aux task `critic` via `ctx.llm` (no tools), then same-model
  `delegate_task`.
- **Fact-checker**: lifecycle launch with `allowed_toolsets=("web",)`, a list of claims and the source
  ledger (section 4); returns per-claim verdicts with URLs. Or deterministic quote-check in plugin code
  (no LLM) against stored page text.

### Limits and cost

- Children cannot call `delegate_task` (leaf default), `clarify`, `memory`, `send_message`, `cronjob`
  (`deleg.md:375-386,700-708`). So the Critic cannot ask the user; it returns to the parent.
- Default 10 concurrent children per batch, `max_iterations` 250 per child, flat depth
  (`max_spawn_depth: 1`), no wall-clock timeout but a stale-progress monitor (450 s idle, 1200 s inside a
  tool) (`deleg.md:43-53,388-428,578-598,760-772`). One-shot runs (`hermes chat -q`) cap total children
  at 2 (`deleg.md:598`).
- Cost: each child re-pays a cold system prompt plus a full tool loop; children usually burn most tokens
  of a run (`deleg.md:279-282`). Child cost rolls up into the parent session's totals
  (`subagent-lifecycle-api.md:56-60`). Subagents inherit the parent's credentials and pool
  (`deleg.md:707`). A critic on a different provider bills that provider.
- Background completion is not durable execution: a restart marks running children `unknown`
  (`deleg.md:682-698`). Long or must-survive work belongs on the kanban board.
- `/review` (built-in) already spawns an independent reviewer on the last 10 messages, model pinnable via
  `auxiliary.review` (`deleg.md:340-373`); usable as a manual "second opinion" on the plan.
- The `subagent_lifecycle` model/provider override has **no documented consent capability** (unlike
  `ctx.llm`'s `llm.model_override`); disclose it in the catalog entry.

## 3. Driving a long 6-phase conversation

### Building blocks and their token cost

| Surface | When it costs | Approx. tokens | Ref |
|---|---|---|---|
| Bundled skill index row (`ctx.register_skill`) | Every session's system prompt, cached | 15-25 per skill (60-char clipped description) | `prompt_builder.py:1189-1218`, `skill_utils.py:846` |
| Skill body via `skill_view` | Once per conversation when loaded; stays in history until compaction | size of SKILL.md (a 12 KB file is ~3k) | `tools/skills_tool.py:735-745` (`file_path` loads one reference file at a time) |
| `register_system_prompt_section` | Every **new** session of the profile, frozen, cached | up to 4,000 chars (~1k) per section; 8,000 chars total for all plugins | `hooks.md:402-447`, `ctx:771-797` |
| `pre_llm_call` context | Every turn where we return text; appended to the user message and persisted (`api_content`), so it accumulates in history | e.g. 600-1,200 chars (150-300 tokens) per turn; >10,000 chars spills to disk | `hooks.md:683-723`, `agent/turn_context.py:917-960`, `tools/hook_output_spill.py:24` |
| Slash command (`ctx.register_command`) | Zero model tokens; its return text goes to the user, not the model | 0 | `index.md:1787-1830` |
| Plugin tool calls | Schema in every session where the toolset is on (~100-300 tokens per tool), plus results | per call | XB section 6 |

Notes: `pre_llm_call` fires once per user turn, not per API call; it must return `None` fast for every
session that has no active idea project (it fires for all sessions while the plugin is enabled), and it
must catch its own errors (a raising or slow callback is skipped; `hooks.md:396,711`). It can veto a turn
with `{"action": "block", "message"}` before inference (`hooks.md:707-709`). Its kwargs include
`session_id` and `parent_session_id` but **not** `conversation_id` (`agent/turn_context.py:917-928`);
tool handlers and tool hooks do get `conversation_id` (`index.md:889-897`). Key state on
`conversation_id`, and record `session_id -> conversation_id` from our tools so the hook can resolve it
(fall back to walking `parent_session_id` after a compression rotation).

### How catalog plugins do it

- **plan-mode** (`100yenadmin/hermes-plan-mode@ee4a245`): per-session state in `ctx.state` keyed by a
  derived session identity (`plan_mode/plugin.py:605-750`), a `pre_llm_call` turn note while planning or
  executing (`plugin.py:2423-2470`), a ≤200-character system prompt section (`plugin.py:589-595`),
  `pre_tool_call` blocks mutating tools until the plan is approved, an approval card via clarify, and
  `/planmode` subcommands. The closest model for phase enforcement.
- **disciplined-vibe-coding** (`bmtrnavsky/disciplined-vibe-coding@ac4de52`): skills only. `register()`
  calls `ctx.register_skill` for each `skills/*/SKILL.md` plus an orchestrator skill
  (`__init__.py:11-26`); phases are prose in skills. No tools, no hooks.
- **storm-fusion-research** (`bmtrnavsky/storm-fusion-research-pipeline@b1a492e`): one skill + one tool
  `storm_run_panel` that fans out seats through `ctx.llm` (`__init__.py:8-21`); "the human gates are skill
  instructions to the agent, not enforced by the tool" (catalog entry).
- **hermes-council**: a tool `council_deliberate`, `/council`, CLI and a Desktop panel; up to 2N+1 billed
  calls per turn (catalog entry `plugin-catalog/hermes-council.yaml`).
- **crew** (`macd2/Crew@ffb0e0c`): `/crew` intake, `pre_llm_call` lesson injection, `pre_tool_call` gate on
  `kanban_create`, role briefs, a coordinator process, an installer that clones four profiles; uses
  private kanban modules and `hermes kanban` subprocesses (`__init__.py:1062-1207,1138-1139`).

### Can a plugin keep per-session state and gate phases?

Yes. State: `ctx.state` (profile-scoped JSON, 10 MiB, `index.md:978-994`) for the small "current
conversation -> project id + phase" index; `plugin_db("hermes-blueprint")` for projects, decisions,
variants, sources, estimates. Gating options, strongest first:
1. **Our own tools are the only way to advance**: `idea_phase(action="advance", evidence={...})` checks
   exit criteria in code (for example Phase 5 requires a stored critic verdict produced by our critic
   tool; Phase 6 requires Phase 5 done) and refuses otherwise.
2. `pre_tool_call` on our own tools (block `idea_plan` before critique) and, optionally, on
   `write_file`/`terminal` while a brainstorm is active (plan-mode style "no building during ideation").
   Remember dispatch_tool calls bypass these hooks (correction 1).
3. `pre_llm_call` injects the current phase rules each turn so the model does not drift.
4. `pre_llm_call` `block` for hard stops (rarely appropriate in a conversation).

### Recommended combination

- `/idea` slash command (works on every surface incl. Telegram): `start`, `status`, `phase`, `critique`,
  `plan`, `scaffold`, `board`, `recheck`, `list`, `resume <id>`, `stop`. Pure state changes and status
  output, no model tokens; uses `ctx.ask_choice` for pickers. To kick off a model turn from a command,
  either tell the user to reply, or use `ctx.inject_message` behind `allow_gateway_injection` (plan-mode
  precedent).
- One small bundled **coordinator skill** (`hermes-blueprint:idea`, the methodology spine, ~2-3k tokens) plus
  per-phase reference files loaded with `skill_view(file_path=...)` only when that phase starts
  (Understanding, Research, Generation, Deep dive, Critique, Plan, Recheck). Plugin skills also appear as
  `/hermes-blueprint:<skill>` on CLI/TUI/Desktop.
- A `pre_llm_call` hook that returns `None` unless the conversation has an active project, and otherwise
  a compact state card (phase, 3-5 phase rules, open questions, decisions so far, next exit criterion),
  capped near 800 chars. Re-inject the fuller card after `post_compaction` (`hooks.md:1130-1153`).
- Skip `register_system_prompt_section`, or keep it ≤200 chars ("Blueprint: use /idea or the idea_*
  tools"), because it costs every new session of the profile.
- Tools for the deterministic parts (phase transitions, research ledger, critic/planner launches,
  estimates, scaffold, board handoff, recheck).

Rough budget for a 30-turn brainstorm: skill spine 2.5k once + four phase references 4 x 1k + hook cards
30 x 200 = ~12.5k tokens of guidance in history (mostly cache reads after first use), versus ~30k+ if the
whole methodology were injected every turn.

## 4. Research tools

| Tool | Provider/config | Returns | Ref |
|---|---|---|---|
| `web_search(query, limit≤100)` | `web.search_backend` / `web.backend`: firecrawl (default), searxng, brave-free, ddgs, tavily, perplexity, keenable, exa, parallel, xai, openai-native, `nous` Tool Gateway; keyless ring fallback (Exa, Parallel, Firecrawl, Keenable) when nothing is configured | `{"success", "data": {"web": [{title, url, description, position}]}}` | `website/docs/user-guide/features/web-search.md:21-50,403-432`, `tools/web_tools.py:302-306,513-571` |
| `web_extract(urls≤5, char_limit≥2000)` | `web.extract_backend`; search-only backends cannot extract | `{"results": [{url, title, content, error}]}`; pages over budget (default 15,000 chars, configurable to 500,000) are head+tail truncated with a `[TRUNCATED]` footer naming the full-text file | `web-search.md:53-71`, `web_tools.py:533-571`, `tools/web_tools_extract.py:66,199-253` |
| `x_search(query, allowed_x_handles, excluded_x_handles, from_date, to_date)` | `XAI_API_KEY` or xai-oauth | answer plus `citations` and `inline_citations`; `degraded: true` when filters returned no citations; OAuth bearer may return no citations (`x_search_tool.py:1-10`) | `tools/x_search_tool.py:252-262,278-341` |
| `browser_exec` (and `browser_cdp`, `browser_dialog`, `browser_vault`) | browser toolsets | live DOM for JS-heavy pages | `web-search.md:67-71`, `website/docs/reference/tools-reference.md:11` |
| `session_search` | local state DB | past sessions' messages (FTS5) | `tools-reference.md:175-179` |

Caching: `web_search` memo per process; `web_extract` full text cached under `~/.hermes/cache/web/`
for `web.cache_ttl_minutes` (default 20), shared across processes, identical concurrent requests coalesced
(`web-search.md:73-107`). xAI search results are model-generated, not index-backed (`web-search.md:28,338-360`).

**Plugin-driven research pass: yes.** A plugin tool `idea_research(questions, source_budget)` can call
`ctx.dispatch_tool("web_search", ...)` and `ctx.dispatch_tool("web_extract", {"urls": [...], "char_limit": N})`,
count sources against the budget, and store `url, title, fetched_at, provider, content_sha256, content`
in `plugin_db`. That gives a verifiable source ledger: the Critic/fact-checker gets source ids, and a
deterministic quote-check (normalized substring or fuzzy match of the quoted span against stored text)
runs in plugin code with no LLM. Caveats: dispatch bypasses `check_fn`, so check the result for
`success: false` / per-URL `error`; truncated pages need a larger `char_limit` (do not read Hermes's
cache files directly: that is a read outside plugin data); web calls bill the user's web provider
(disclose); there is no separate "citation" tool besides `x_search`'s citations and Perplexity's
query-relevant snippets.

Alternative: a research subagent via `ctx.subagent_lifecycle.launch(allowed_toolsets=("web",))` that
returns a JSON list of `{claim, url, quote}`; then our code re-fetches each URL with `web_extract` and
quote-checks. Cheaper in parent context, more expensive overall.

## 5. Session history and the velocity ledger

- **Supported API**: `from hermes_state import SessionDB` (public module, `public-api.md:57`). Read
  methods (on mixins, reachable through `SessionDB`): `list_sessions_rich(source, cwd_prefix,
  min_message_count, include_children, include_subagents, order_by_last_active, ...)`
  (`hermes_state_sessions.py:1309-1340`), `get_session(id)` (`:836`), `search_sessions` (`:1553`),
  `session_count` (`:1582`), `get_messages(id)` (`hermes_state_messages.py:1385`), `search_messages`
  (`hermes_state_search.py:1154`), `usage_totals()` (`hermes_state_usage.py:456`). Usage examples and
  SQL in `website/docs/developer-guide/session-storage.md:387-575`.
- **Fields useful for velocity** (`session-storage.md:166-226`): `started_at`, `ended_at`,
  `message_count`, `tool_call_count`, token columns, `estimated_cost_usd`, `title`, `model`, `source`
  (`cli`, `desktop`, `telegram`, `cron`, `kanban`, `subagent`, ...), workspace `cwd`, `git_branch`,
  `git_repo_root`, `parent_session_id` lineage; per-message `timestamp`. Grouping by `git_repo_root` gives
  "active days and hours per repo"; kanban `runs` give per-card elapsed times (section 1).
- Use only public methods; calling private ones (`db._execute_write`) triggers a validate warning
  (catalog README rule 9, lines 66-79). Open read-only and never write. Check behaviour under
  `plugins.isolation: host` (the host process runs with the profile's environment, so `SessionDB()`
  should resolve the same `HERMES_HOME`; not verified).
- **Insights**: `hermes insights [--days N] [--source]` and `/insights`, `/usage`
  (`website/docs/reference/cli-commands.md:1857-1866`, `slash-commands.md:137-141`) are built on
  `agent/insights.py` `InsightsEngine(db).generate(days)` (lines 1-3, 196), which is **not** public
  (validate warns). `agent.account_usage` is public but reports provider account limits, not activity.
  Compute our own aggregates from `SessionDB`.
- The `session_search` tool is the model-facing route (FTS over past messages) if the agent should cite
  how a past project went.
- **Privacy rules**: no catalog rule forbids reading the state DB, but rule 13 requires disclosing
  "reads outside the plugin's own data" and makes telemetry opt-in (`catalog README:114-119`).
  Precedent wording: cadence "reads the selected profile state.db read-only", chat-length "reads the
  session title read-only from state.db", agent-station "reads state.db read-only"
  (`plugin-catalog/cadence.yaml`, `chat-length.yaml`, `agent-station.yaml`). Recommended: off by default
  (`config_schema` `velocity_from_history: false`), explicit opt-in prompt on first use, read only
  metadata (timestamps, counts, repo root, titles), never message bodies unless the user asks, store only
  derived aggregates in plugin data, never send raw history to an LLM.

## 6. File output (scaffold folder)

- **Through `ctx.dispatch_tool("write_file", {"path", "content"})`**: goes to the file tool handler,
  so the protected-path denylist and `HERMES_WRITE_SAFE_ROOT` apply; there is **no approval prompt** for
  ordinary paths (`security.md:369-372,401-415`), and plugin `pre_tool_call` hooks are bypassed
  (correction 1). Relative paths resolve against the agent's working directory (gateway mode: configured
  terminal cwd; `index.md:1922-1935`).
- **Direct writes from plugin code** (`pathlib`): allowed; nothing in Hermes guards them. Use
  `ctx.session_cwd()` (`ctx:404-407`) or `agent.runtime_cwd.resolve_agent_cwd()` to resolve the user's
  project dir, never `os.getcwd()` in the gateway (XB section 6).
- **Agent writes**: the skill can tell the agent to write the files itself with `write_file`; then other
  plugins' gates (plan-mode) and Hermes's mutation verifier apply, at the cost of model tokens for every
  file body.
- **Catalog rules**: writing outside plugin data must be disclosed (rule 13, `catalog README:114-119`).
  Plan-mode's disclosure ("creates .hermes/plans under the session working directory") is a good template.
- Recommendation: `idea_scaffold(path, files=[...], overwrite=False)` tool in plugin code that renders
  templates from plugin data, writes only inside the user-chosen folder, refuses to overwrite existing
  files unless asked, and is confirmed via `ctx.ask_choice` from `/idea scaffold` (sync handler) or a
  `pre_tool_call` `approve` on our own tool when the model calls it. Write `AGENTS.md` (Hermes's primary
  context file; subagents and workers load `.hermes.md` > `AGENTS.md` > `CLAUDE.md`, `deleg.md:86`) and
  optionally `CLAUDE.md` for Claude Code users, plus `README.md`, `DECISIONS.md`, `PLAN.md`.
- Then optionally `ctx.dispatch_tool("desktop_project", {"action": "create", "path": <scaffold>})` to make
  it a Hermes Project (Desktop/GUI sessions; `tools/project_tools.py:164-187`,
  `tools-reference.md:159`), and bind the kanban board to that Project so cards become worktrees in the
  repo (`kanban.md:221-237`).

## 7. Dashboard / Desktop page

Already covered in XB section 6 (dashboard `dashboard/manifest.json` + `dist/index.js` +
`plugin_api.py`; Desktop `desktop/plugin.js` with `ROUTES_AREA` + `SIDEBAR_NAV_AREA`, `ctx.rest` to the
same `plugin_api.py`; catalog rule 8). Additions for this plugin:

- **Minimal Desktop page** (shape from `sdk.md:297-321` and Crew's `desktop/plugin.js:3509-3527`):

```javascript
import { ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'
import { useEffect, useState } from 'react'

function IdeaPage({ ctx }) {
  const [projects, setProjects] = useState([])
  useEffect(() => { ctx.rest('/projects').then(setProjects) }, [])
  return jsx('div', { className: 'p-4 text-sm', children: projects.map(p =>
    jsx('div', { children: `${p.title}: phase ${p.phase}/6` }, p.id)) })
}

export default {
  id: 'hermes-blueprint',
  name: 'Blueprint',
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/idea' }, render: () => jsx(IdeaPage, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/idea', label: 'Ideas', codicon: 'lightbulb' } }
    ])
  }
}
```

  Crew registers exactly this pair plus a right-hand pane (`PANES_AREA`) for a live flow view. No JSX
  and no imports beyond `@hermes/plugin-sdk`, `react`, `react/jsx-runtime` (`sdk.md:148-155`).
- **Dashboard tab**: `{"name": "hermes-blueprint", "label": "Blueprint", "icon": "...", "tab": {"path":
  "/idea", "position": "after:kanban"}, "entry": "dist/index.js", "api": "plugin_api.py"}` (same shape as
  `plugins/kanban/dashboard/manifest.json`; reference `extending-the-dashboard.md:368-487,726-787`).
- **Transcript directive** (`TRANSCRIPT_DIRECTIVE_AREA`, `sdk.md:1100-1180`): the model writes
  `::idea{id="..."}` and Desktop renders our phase-tracker card inline in the chat. Good for showing the
  6-phase progress without a page switch.
- **Kanban card badges** (`sdk.md:857-946`): estimate and plan-gate chips on cards we created.
- Page content: phase tracker, decision log, variants with critique verdicts, the plan with per-task
  estimates (p50/p80) and calibration source, source ledger with quote-check status, recheck history.

## 8. Overlaps in Hermes core and the catalog

- **creative-ideation** (optional skill, `optional-skills/creative/creative-ideation/SKILL.md`, v2.1.0):
  a routed library of named ideation methods with an anti-slop rule ("refuse the first three ideas") and
  one method per response. Reuse in Phase 3 (Generation): point the agent at it when installed
  (`skills_list` check) instead of writing our own method catalog; our value is the structure around
  generation (3-5 variants scored on fixed axes), not the methods. Do not duplicate its method library.
- **decision-questionnaire** (optional skill, v1.0.0): turns a decision blocked on someone else's
  knowledge into an async questionnaire document. Interoperate in Phase 1/4 when the open question is
  for a third party (customer, co-founder); offer it as an exit, do not rebuild it.
- **grill-me** (optional skill, v2.0.0): adversarial interview of a plan as a design tree, in rounds, with
  the user. Overlaps our Phase 1 Understanding interview and part of Critique, but it questions the
  user; our Critic is an isolated model attacking the chosen variant. Reuse its "design tree / frontier
  rounds" for Phase 4 Deep dive questioning; keep our Critic separate.
- **PR #113468 PARALLAX** (open since 2026-09-16, no update since, 433 additions; author
  PraveenKumarSridhar): optional skill for evidence-based problem framing (mechanism vs desired
  outcome, upstream trigger, existing capabilities, smallest intervention). It is the closest match to
  our Phase 1-2 ("is this the right problem, does something already exist"). Do not depend on an unmerged
  PR; borrow the questions as a checklist idea and mention interop if it lands.
- **PR #147267 elephant-goldfish** (open since 2026-10-31, by teknium1, 3,465 additions): optional skill;
  the main agent drafts a design doc with full context, then fresh `delegate_task` reviewers ("goldfish")
  with personas review it, a synthesizer merges, the user decides; review-loop until two clean rounds
  (cap 5). It states that "read-only reviewer" is an instruction, not a sandbox. This is the same idea as
  our isolated Critic/Planner. Reuse the pattern (personas, synthesizer, convergence rule) and, if it
  merges, offer "/elephant-goldfish review PLAN.md" as an optional deeper review of our PLAN; our
  differentiator is the forced critique gate before planning, the cross-model route and the build/recheck
  loop.
- **hermes-council**: four fixed seats + chairman via `council_deliberate`, up to 2N+1 calls per turn.
  Interop: if installed, offer it as an optional multi-model critique backend for Phase 5. Do not build
  our own council.
- **storm-fusion-research**: perspective-panel research with seats and a judge through `ctx.llm`. Its
  panel overlaps a multi-perspective Phase 2; ours should stay a source-budgeted, URL-ledgered research
  pass (verifiability) and can point to storm for deep research.
- **plan-mode**: enforces "plan before edits" for implementation. It is downstream of us: after our
  handoff, a user building in Hermes can use plan-mode per card. Do not re-implement edit blocking for
  the build phase; borrow its state/turn-note pattern for ideation. Our scaffold writes from plugin code,
  so plan-mode will not block them (correction 1); disclose that.
- **disciplined-vibe-coding**: Define/Plan/Build/Verify skills for non-engineers. Overlaps our
  Plan/handoff; ours ends at a decided, critiqued plan plus scaffold and rechecks, theirs drives the build.
  Mention as a compatible build-phase companion; do not copy its skills.
- **crew**: `/crew` turns an ask into proof-gated kanban cards with a coordinator, verifier, token budget
  and installer-created profiles. It is the strongest overlap with our build handoff. Do not build a
  coordinator; our handoff should create plain kanban cards (title, body with acceptance criteria,
  parents, assignee) that Crew or the built-in dispatcher can run, and optionally hand the plan to
  `/crew` when the user has it. Its install side effects (cloned profiles) are not something we should
  copy.
- **advisor / hermes-verifier**: per-turn second-model review of the primary agent (post_llm_call),
  advice injected into the session. Different scope (every turn of any work). If installed they will
  also review our brainstorm turns; nothing to reuse except that our Critic should be on-demand and
  phase-scoped, not per turn.
- **Core features to reuse**: `/goal` (judge-driven loop, `goals.md`) and kanban `goal_mode` cards for
  "keep working until acceptance criteria hold"; `/review` for a manual second opinion; `kanban specify`
  for one-liner cards; `/loop` or cron blueprints (XB section 1) for periodic rechecks; `desktop_project`
  for the project folder.

## Design implications

1. **Methodology delivery** = `/idea` command (state, no tokens) + one coordinator skill with per-phase
   reference files + a `pre_llm_call` state card only for conversations with an active project + our own
   `idea_*` tools that own phase transitions. No always-on system prompt section beyond ≤200 chars.
2. **Phase gate in code**: `idea_phase(advance)` checks stored artifacts (variants recorded, critic
   verdict stored by our critic tool, decision logged) before moving on; `pre_tool_call` blocks
   `idea_plan` and `idea_scaffold` until Phase 5 is complete. State keyed by `conversation_id`, with a
   `session_id` map for the hook.
3. **Isolation**: Critic, fact-checker and Planner run through `ctx.subagent_lifecycle.launch` from our
   tools with plugin-assembled context packets; critic model/provider from `config_schema`; fallback to
   aux task `critic` via `ctx.llm`, then same-model `delegate_task`. Record which model judged what.
4. **Research ledger**: `idea_research` dispatches `web_search`/`web_extract` with a source budget, stores
   URL + fetched text + hash in `plugin_db`, and quote-checks claims deterministically. `x_search` only
   when configured, flagged as model-generated.
5. **Velocity ledger**: opt-in, read-only `SessionDB` metadata + kanban run durations + our own
   project timeline (phase timestamps, handoff date, recheck outcomes) to calibrate estimates (p50/p80
   from this user's past ratio of estimated vs actual). Disclosed per rule 13.
6. **Build handoff**: scaffold via plugin code with explicit confirmation; optional `desktop_project`;
   cards via `dispatch_tool("kanban_create")` with acceptance-criteria bodies, `parents`, assignee chosen
   from existing profiles (list them first), optional `goal_mode`, tenant `idea-<slug>`, idempotency keys
   `idea:<project>:<task>` so re-running the handoff never duplicates. Board creation only on request
   through `hermes kanban boards create`.
7. **Rechecks**: `/idea recheck` and a blueprint (`hermes-blueprint:recheck`, weekly) that calls
   `kanban_list`/`kanban_show` for the tenant plus the scaffold's git state, compares against PLAN.md
   gates, and asks the Critic whether results disconfirm the thesis or only the tuning. Optional hooks
   `kanban_task_completed/blocked` to timestamp progress in real time.
8. **UI**: Desktop page + transcript directive card + kanban card badges, dashboard tab sharing
   `plugin_api.py`. All read from `plugin_db`.
9. **Disclosures to prepare**: LLM calls on the user's credentials (critic/planner/fact-checker, possibly
   a second provider), web search/extract billing, opt-in read-only state.db reads, files written to the
   user-chosen folder, shell command for board creation, kanban cards created (workers then spend tokens
   under their profiles), cron recheck job left behind after uninstall.
10. **Compatibility**: every API above exists at `v0.23.0` (`subagent_lifecycle`,
    `register_system_prompt_section`, kanban tools, `dispatch_tool`), so `requires_hermes: ">=0.23.0"`
    fits; test against `v0.23.0` and `main` as in XB section 8. The test `FakeCtx` needs fakes for
    `dispatch_tool` (kanban/web/write_file), `subagent_lifecycle`, `state`, `llm`, `ask_choice`.

## Open questions

1. Does `ctx.subagent_lifecycle.launch` work from a plugin tool under `plugins.isolation: host`
   (docs say the facade works), and does its `model`/`provider` override need any operator opt-in in
   practice? Test with a second provider configured.
2. Do the 32k-character result cap and 1-hour in-process retention of lifecycle results suffice for a
   Planner that returns a full plan JSON? If not, have the Planner write to a file in plugin data via an
   allowed toolset, or split the plan.
3. Is the slash-command return text ever visible to the model (assumed no)? If not, `/idea start <text>`
   needs either the user's next message or `inject_message` with `allow_gateway_injection`.
4. Can kanban cards carry our plugin skill (`skills: ["hermes-blueprint:builder"]`) when the plugin is
   enabled in the worker profile, or must skills be on-disk installs? Test before relying on it.
5. Do plugin skill `skill_view(file_path=...)` reference files resolve relative to the registered
   SKILL.md path? (Works for on-disk skills; disciplined-vibe-coding ships templates this way.)
6. Should board creation go through `dispatch_tool("terminal")` (shell command, disclosure) or should we
   ask Hermes for a public `kanban_board_create` tool / `kanban_db` facade (rule 9: "open an issue")?
   Draft PR #31641 ("Kanban CRUD" API add-ons) is related but stale since 2026-05-24.
7. What is the right assignee default for handoff cards when the user has only the `default` profile?
   (Cards for a non-existent profile strand in `ready`.) Probably: list profiles, ask, offer to create
   one, and fall back to "no board, just PLAN.md".
8. `SessionDB()` under `plugins.isolation: host` and under the multiplex gateway: confirm it opens the
   active profile's `state.db` read-only without contending with the writer.
9. Elephant-goldfish (#147267) and PARALLAX (#113468) are unmerged; re-check their status at
   submission time and adjust interop text.
10. Does the native Desktop Kanban page show cards from all tenants by default, and can a deep link open
    a board filtered to our tenant (for a "View on board" button from our page)?
