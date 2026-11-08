# Unit 1 spike: how it was run

A throwaway plugin (`idea-spike`) with one tool, `idea_spike`, and one slash command,
`/ideaspike`. Each check writes its raw result to `spike/results/<check>.json` (gitignored).
Results are summarized in `docs/DECISIONS.md` (D7).

Checks: `env` (handler kwargs, session helpers, plugin storage), `web` (`web_search` +
`web_extract` through `ctx.dispatch_tool`, quote check on the page text), `kanban`
(`kanban_create` with an idempotency key and a parent, `kanban_show`, `kanban_list`),
`lifecycle` (`ctx.subagent_lifecycle.launch`: fresh context, model override, provider override,
narrowed toolsets, unknown provider).

## Option A: normal terminal (outside the Claude desktop app)

Link the folder into Hermes and enable it:

```powershell
New-Item -ItemType Junction -Path "$env:LOCALAPPDATA\hermes\plugins\idea-spike" -Target "<repo>\spike"
hermes plugins enable idea-spike
hermes
```

Then ask the agent to call `idea_spike` with `check=env`, `web`, `kanban`, `lifecycle`, one call
at a time. Afterwards: `hermes plugins disable idea-spike` and remove the junction.

## Option B: from inside the Claude desktop app (how D7 was produced)

The Claude desktop app on Windows is an MSIX package. Processes it starts see `%LOCALAPPDATA%`
through file-system virtualization: files Hermes rewrites atomically (config.yaml, auth.json)
land in the package's private `LocalCache`, `Path.resolve()` then points there, and Hermes refuses
plugin changes ("config path is outside Hermes state") and cannot start a gateway for a new
profile. SQLite databases (state.db, kanban.db) are written in place, so they are the real ones.

`spike/harness.py` avoids all of that: it runs one real `AIAgent` turn in-process, with
`idea-spike` added to the enabled set for that process only. The junction must still exist.

```bash
cd "$LOCALAPPDATA/hermes/hermes-agent"
HERMES_DISABLE_LAZY_INSTALLS=1 PYTHONPATH="$PWD" \
  "<selected venv>/Scripts/python.exe" "<repo>/spike/harness.py" \
  "Call the idea_spike tool with check=lifecycle, then reply only: done."
```

`<selected venv>` is the `environment` path in
`%LOCALAPPDATA%\hermes\installs\<key>\facts.json`. `HERMES_DISABLE_LAZY_INSTALLS=1` stops
Hermes from trying to finish a pending source update (which fails in the sandbox).

Side effects of a run: web calls on the configured backend, two kanban cards in tenant
`idea-spike` on the real board (archive with `hermes kanban archive <id>`), a few short subagent
runs, the agent sessions in the real `state.db`.

Caution: a token refresh during a sandboxed run is saved only to the sandbox copy of
`auth.json`. Nous refresh tokens are single-use, so the real Hermes may later need
`hermes auth add nous`.
