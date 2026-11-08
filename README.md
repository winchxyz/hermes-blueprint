# hermes-blueprint (work in progress)

A Hermes Agent plugin that turns a raw idea into a plan you can build, right in the Hermes chat:
sourced research where every ✅ has a quoted, fetched source; three really different variants; a
critic that starts from base rates and does not cave to pushback; a plan estimated the way you
actually build (agent hours vs your hours vs outside waits); then the plan becomes Hermes kanban
cards, and a weekly re-check scores the predictions and compares estimates with what happened.

Status: platform spike done, skeleton in place (`/idea` command, `idea_phase` tool, phase gates
checked in code). The harness tools come next. See:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): phases, the quality harness (H1-H8), Hermes surfaces, demo
- [docs/PLAN.md](docs/PLAN.md): build units with estimates and gates
- [docs/DECISIONS.md](docs/DECISIONS.md): open and settled decisions
- [docs/research/](docs/research/): estimation evidence and the owner's velocity ledger, research
  and judgment methods, Hermes platform notes

## License

MIT
