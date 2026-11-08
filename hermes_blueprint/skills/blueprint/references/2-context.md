# Phase 2: Context (research)

Goal: the facts that decide whether and how to build, each one sourced, plus an honest list of
what is not verified. LLM research fails in known ways: citation errors, snippets taken as facts,
queries that only look for support, syndicated copies counted twice, "nothing exists" stated as
fact. The tool blocks most of these; the rest is on you.

## 1. Plan

`idea_research(action=plan, tier, kind, questions)`:

- `tier`: `quick` for a personal project, `standard` by default, `deep` for money or a startup.
- `kind`: `software` if the idea is software (needs the competitor sweep), else `other`.
- 3-8 questions from four angles: user and demand, competitors and alternatives, feasibility,
  distribution and money. Each answerable by a page you could fetch.

The reply lists the requirements the briefing will be checked against.

## 2. Search, fetch, quote

- `search` with a purpose: `support`, `disconfirm`, `competitor` (with a `channel`) or
  `background`. Results are leads.
- **Disconfirm on purpose**: "<idea> failed", "why not <idea>", "<idea> alternatives",
  "<competitor> criticism", "<market> shrinking". At least two of these.
- **Competitor sweep**: one or more `competitor` searches per channel the plan requires (github,
  registries such as PyPI/npm, plugin marketplaces and catalogs, app stores, Product Hunt, Hacker
  News, Reddit, X, the web). A Hermes plugin idea also checks the Hermes plugin catalog and its
  open PRs.
- `fetch` the pages that matter (up to 5 per call). Prefer the original: the vendor's pricing
  page, the store listing, the repo, the paper, the official policy page, not coverage of it.
  Long pages: `read` with `find` or `offset`.

## 3. Claims

`claim` = one atomic statement + `type` + `evidence: [{source: "S#", quote: "exact words"}]`.

- The quote must be copied from the page text (20+ characters). Code checks it; a failed check
  means re-read the page, not rephrase from memory.
- Numeric or disputed claims: `contested: true`; they need two independent sources (different
  sites, not one article republished) for ✅. One source gives ⚠️.
- Add `as_of` when the fact can change (prices, counts, policies).
- A lead you cannot source yet: `unverified: true` (🔍). It goes to Not verified.
- "Nothing like this exists": `absence` with at least 3 search ids. It is never ✅; the briefing
  lists where you looked.
- Wrong claim: `retract` with the reason.

Stop when new searches stop producing new claims (the briefing reports this).

## 4. Verify, then brief

- `verify`: an independent fresh-context verifier checks that each quote supports its claim as
  worded and that the source is an original. It may downgrade or retract claims. If it cannot run,
  the briefing says so.
- `briefing(summary, surprises, unknowns)`: the summary is prose for the user, every fact cited
  inline as `[C#]`. The tool appends the claims, the source log, the coverage and Not verified.
  If it refuses, fix what `problems` lists.

Show the returned briefing markdown to the user (translated into their language if needed, with
the [C#] and S# references kept). Ask what surprised them, then `idea_phase(action=advance)`.
