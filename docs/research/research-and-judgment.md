# Research and judgment quality: evidence and protocol for hermes-blueprint

**Date:** 2026-11-08
**Scope:** methodology research for hermes-blueprint. It covers the two failure modes of LLM brainstorming the plugin has to prevent: research that is shallow or sloppy, and judgment that caves or is miscalibrated.

## How to read the confidence tags

- **[primary]**: I opened the primary source in this session (paper abstract or table, official documentation, official policy page), and the claim matches what it says.
- **[secondary]**: taken from news coverage, a third-party summary, or a search-engine summary of the source. I did not check it against the original.
- **[unverified]**: from memory, or from a source I could not open (403 or paywall). Treat it as a lead.

**Method caveat.** The fetch tool used here returns text summarized by a model, not raw page bytes. "Primary" therefore means "checked against the primary page's content as returned by the tool", not a byte-level quote match. This is the same weakness discussed in A1. One example happened during this research. A search summary said Valve's onboarding docs require a **30-day** wait between paying the Steam app fee and release. The fetched Valve page says **"A 21-day waiting period"** ([Valve onboarding](https://partner.steamgames.com/doc/gettingstarted/onboarding) [primary]). Search summaries are leads, not evidence.

## Baseline: prompt-level rules, and where they leak

The methodology's prose rules are a reasonable start: a Tier 1/2/3 search policy, ✅/⚠️/🔍 labels, freshness windows (18 months, or 6 for fast-moving fields), "2+ sources when feasible", a "Surprises" section and an "Unknowns" section in research, a forced adversarial critique, thesis-vs-parameters analysis, and a re-check after the build.

Written only as instructions to the model, they leak (each gap maps to a design consequence at the end of this document):

1. **No rule about what counts as evidence.** "✅ Verified = found an authoritative current source" can be satisfied by a search snippet. Nothing requires fetching the page, keeping an exact quote, or recording the date.
2. **No claim decomposition and no verification pass.** The briefing is written and shipped in one pass.
3. **No disconfirmation step.** Queries are framed by the idea, so they tend to find support for it.
4. **"Two sources" has no definition of independence.** Syndicated copies count twice.
5. **No minimum evidence per claim type, no budget and no stopping rule.** Depth is left to mood, which is where sloppy research comes from.
6. **Absence claims are treated like presence claims.** "No competitor exists" is the most decision-relevant and least verifiable claim in Phase 2.
7. **Confidence guidance breaks its own rule.** It is easy to write base rates with no source ("startup pivots succeed ~30%") into the same prompt that forbids unsourced numbers.
8. **The critic has no outside view, no pre-commitment against caving to pushback, and no awareness of who the builder is.** A strict cross-project isolation rule even forbids importing the builder's background.
9. **Predictions are not recorded in a scoreable form.** A re-check that judges thesis vs tuning never scores calibration.

---

## A. Research quality

### A1. Known failure modes of LLM web research, with measured rates

| Failure mode | Measured evidence | Tag |
|---|---|---|
| **Citations that do not support the sentence** | Audit of generative search engines: only **51.5%** of generated sentences were fully supported by their citations, and **74.5%** of citations supported their sentence ([Liu, Zhang, Liang 2023, arXiv:2304.09848](https://arxiv.org/abs/2304.09848)). | [primary] |
| **Misattributed or wrong sources in AI search** | Tow Center (CJR), March 2025: 8 AI search tools, 1,600 queries. Collectively **>60%** of answers were incorrect: Perplexity **37%**, Grok 3 **94%**. ChatGPT misidentified 134 of 200 articles and signaled uncertainty only 15 times. Premium tiers gave more *confidently* wrong answers. Tools cited syndicated copies instead of originals ([CJR/Tow Center](https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php)). | [primary] |
| **Fabricated or broken URLs** | Same study: for Gemini and Grok 3, more than half of responses cited fabricated or broken URLs, and 154 of 200 Grok 3 citations led to error pages ([CJR](https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php)). Across 10 commercial LLMs and deep-research agents (about 221k URLs), **3–13%** of cited URLs appear fabricated (no Wayback record ever) and **5–18%** do not resolve. Deep-research agents fabricate URLs at *higher* rates than search-augmented LLMs ([Rao, Wong, Callison-Burch 2026, arXiv:2604.03173](https://arxiv.org/abs/2604.03173)). | [primary] |
| **Citation accuracy of deep-research agents** | DeepResearch Bench (100 PhD-level tasks), FACT citation accuracy: OpenAI Deep Research **77.96%**, Gemini-2.5-Pro DR **81.44%**, Grok DeeperSearch **83.59%**, Perplexity DR **90.24%**, Claude-3.7-Sonnet with search **93.68%**, Perplexity Sonar Reasoning Pro **39.36%**. Effective citations per task ranged from about 4 to 111 ([Du et al. 2025, arXiv:2506.11763, Table 1](https://arxiv.org/html/2506.11763v1)). Even the best systems leave roughly 1 in 10 to 1 in 5 citations unsupported. | [primary] |
| **Shallow coverage vs experts** | DeepResearch Bench II (132 tasks, 9,430 expert-derived binary rubrics): the strongest agents satisfy **<50%** of rubric items ([Li et al. 2026, arXiv:2601.08536](https://arxiv.org/abs/2601.08536)). | [primary] |
| **Fabricated references from memory (no search)** | GPT-3.5: **55%** of citations fabricated. GPT-4: **18%** fabricated. Among real citations, 43% (GPT-3.5) and 24% (GPT-4) had substantive errors ([Walters & Wilder 2023, Scientific Reports](https://www.nature.com/articles/s41598-023-41032-5.pdf)). | [secondary] |
| **Browsing increases confidence in wrong answers** | BrowseComp: Deep Research reached **51.5%** accuracy, versus 1.9% for GPT-4o with browsing, but with a **91% calibration error**. The authors note that "access to web tools may increase the model's confidence in incorrect answers" ([Wei et al. 2025, arXiv:2504.12516](https://arxiv.org/html/2504.12516v1)). | [primary] |
| **SEO and affiliate spam** | Anthropic's research agents "consistently chose SEO-optimized content farms over authoritative" sources until source-quality heuristics were added to the prompts ([Anthropic Engineering, June 2025](https://www.anthropic.com/engineering/multi-agent-research-system)) [primary]. In a one-year study of 7,392 product-review queries on Google, Bing and DuckDuckGo, affiliate content was over-represented relative to the web ([Bevendorff et al., ECIR 2024](https://gwern.net/doc/technology/google/2024-bevendorff.pdf)) [secondary]. | mixed |
| **Stale data and false premises** | FreshQA: "all models (regardless of model size) struggle" on fast-changing knowledge and false-premise questions. Adding retrieved, dated evidence helps, and the number and order of evidence items matter ([Vu et al. 2023, arXiv:2310.03214](https://arxiv.org/abs/2310.03214)). | [primary] |
| **Confirmation bias in query choice** | People issued *more biased queries* with LLM-powered conversational search than with conventional search, and the bias got worse when the LLM held an opinion that agreed with theirs ([Sharma, Liao, Xiao, CHI 2024, arXiv:2402.05880](https://arxiv.org/abs/2402.05880)) [primary]. Agents also show "inertia bias": they judge the outcome of their *own* earlier search actions less objectively, and isolating context at triage and validation points mitigates it ([Zhang et al., EMNLP 2026, arXiv:2608.23045](https://arxiv.org/abs/2608.23045)) [primary, new and unreplicated]. | mixed |
| **"Search snippet as fact"** | I found no study that measures this directly. Mechanism evidence: syndicated copies get cited in place of originals ([CJR](https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php)) [primary], and the Valve 30-day vs 21-day discrepancy observed in this session (see the method caveat) [primary for the Valve page]. Misattribution also propagates through citation chains: Klein's widely quoted claim that a premortem improves the ability to *correctly* identify reasons by 30% traces to a 1989 study that counted the *number* of reasons and did not assess their quality ([Collins, "The premortem"](https://corporate.jcx.au/premortem)) [secondary]. | mixed |
| **Single-source claims** | No measured rate found. The audits above imply that one unchecked citation is wrong roughly 10–25% of the time (inference from Liu 2023 and DeepResearch Bench). | inference |

**Takeaways for the plugin**

- Unsupported or wrong citations are not rare. They are the base rate. Plan for 10–25% bad citations unless each one is checked against fetched text.
- A source being *present* is not evidence. The quote must be *in* the page, the page must *exist*, and it must be the *original* rather than a copy.
- Web access makes the agent *more* confident, not more calibrated. Confidence labels must be computed from the evidence trail, not from how the agent feels.
- Confirmation bias enters at query generation, before any source is read. The protocol must force disconfirming queries.

### A2. Techniques with evidence

| Technique | Evidence | What an in-chat agent can do | Tag |
|---|---|---|---|
| **Claim decomposition, then per-claim verification** | FActScore splits text into atomic facts. ChatGPT scored 58% on biographies, and the automated estimator's error was below 2% ([Min et al. 2023, arXiv:2305.14251](https://arxiv.org/abs/2305.14251)). SAFE (Google DeepMind) issues a Google search per atomic fact. It agrees with human annotators 72% of the time, is right in 76% of disagreements, and is more than 20x cheaper ([Wei et al. 2024, arXiv:2403.18802](https://arxiv.org/abs/2403.18802)). | After drafting, list the decision-relevant atomic claims (usually 8–20) and verify each one separately. | [primary] |
| **Chain-of-Verification (CoVe)** | Draft → plan verification questions → answer them *independently*, so the answers are not biased by the draft → revise. This reduced hallucinations on list QA, closed-book QA and long-form generation ([Dhuliawala et al. 2023, arXiv:2309.11495](https://arxiv.org/abs/2309.11495)). | Verification questions are answered without the draft in view: a separate sub-agent, or at minimum a separate turn. | [primary] |
| **Quote grounding and retraction** | Anthropic's guidance: extract word-for-word quotes before the task, and after drafting find a supporting quote for each claim. "If it can't find a quote, it must retract the claim." It also says to allow "I don't know" ([Claude docs: Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)). | Every ✅ claim carries a quote of 25 words or fewer from a fetched page. No quote means downgrade to ⚠️ or 🔍. | [primary] |
| **URL liveness checks** | The urlhealth tool (liveness check plus Wayback lookup) cut non-resolving citations by 6–79x, to under 1% ([Rao et al. 2026](https://arxiv.org/abs/2604.03173)). | Fetch every cited URL before output. A URL that fails to load is removed or marked. | [primary] |
| **Source tiering and lateral reading** | Professional fact-checkers left a site quickly and checked it from other tabs. They reached "more warranted conclusions in a fraction of the time" than historians and students, who read vertically and were fooled by logos and domains (45 participants, deliberately not a random sample) ([Wineburg & McGrew 2019, Stanford news](https://ed.stanford.edu/news/stanford-scholars-observe-experts-see-how-they-evaluate-credibility-information-online)) [secondary]. Explicit source-quality heuristics in prompts fixed Anthropic's content-farm problem ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)) [primary]. | For an unfamiliar source, run one lateral query: "who is <publisher>", "<site> affiliate", "<site> reliability". | mixed |
| **Triangulation with independent sources** | I found no LLM-specific measurement. The CJR finding that syndicated copies get cited shows why independence has to be defined ([CJR](https://www.cjr.org/tow_center/we-compared-eight-ai-search-engines-theyre-all-bad-at-citing-news.php)). | Two sources are "independent" only if they have different owners or publishers, neither cites the other, and the text is not a copy. | practice |
| **Deliberate disconfirmation queries** | "Consider the opposite" as a debiasing strategy (Lord, Lepper & Preston 1984, *JPSP* 47(6)) [unverified, bibliographic from memory]. The echo-chamber result above shows the cost of skipping it [primary]. | Required queries: "<idea> failed", "<competitor> shut down", "why not <approach>", "<X> alternatives", "<X> criticism", "<X> problems reddit". | mixed |
| **Recency requirements** | FreshQA: dated, retrieved evidence improves answers on fast-changing facts ([Vu et al.](https://arxiv.org/abs/2310.03214)). | Each claim records "as of" (the page's date) and "fetched" (today). Keep the existing 18/6-month windows. | [primary] |
| **Perspective-guided question asking** | STORM discovers perspectives, simulates writer-expert conversations grounded in sources, then outlines. Its articles were judged better organized (+25% absolute) with +10% coverage breadth. Wikipedia editors flagged "source bias transfer" and "over-association of unrelated facts" as open problems ([Shao et al., NAACL 2024, arXiv:2402.14207](https://arxiv.org/abs/2402.14207)). | Before searching, write questions from 4 perspectives (see A3), so coverage is not set by the first query. | [primary] |
| **Search budgets and stopping rules** | Anthropic: "token usage by itself explains 80% of the variance". Effort is scaled by complexity: "Simple fact-finding requires just 1 agent with 3-10 tool calls". "Start with short, broad queries... then progressively narrow". Over-investing in simple queries was an early failure mode ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). BrowseComp: accuracy "scales smoothly" with test-time compute, and best-of-N over 64 samples gave +15–25% ([Wei et al. 2025](https://arxiv.org/html/2504.12516v1)). | Explicit budget tiers plus a saturation-based stopping rule (A3). | [primary] |
| **Separating retrieval from synthesis** | Anthropic runs a separate CitationAgent pass that maps report claims to source locations after writing ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). STORM separates pre-writing research from writing ([Shao et al.](https://arxiv.org/abs/2402.14207)). | Phase A: gather and log sources (no conclusions). Phase B: synthesize only from the log. Phase C: verify. | [primary] |
| **Adversarial verifier with fresh context** | Intrinsic self-correction without external feedback fails and can *degrade* reasoning ([Huang et al. 2023, arXiv:2310.01798](https://arxiv.org/abs/2310.01798)). LLM judges favor their own generations, and self-recognition correlates with self-preference ([Panickssery et al. 2024, arXiv:2404.13076](https://arxiv.org/abs/2404.13076)). Agents are less objective about their own prior actions, and context isolation helps ([Zhang et al. 2026](https://arxiv.org/abs/2608.23045)). | The verifier sees *claims plus the source log only*, not the drafter's reasoning. It must re-fetch pages (external feedback). Use a different model if the host allows it. | [primary] |
| **Rubric-based LLM judging** | Anthropic's judge scores factual accuracy, citation accuracy, completeness, source quality and tool efficiency. A single call producing a 0–1 score and pass/fail worked best ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). | The briefing self-scores against this rubric before output and lists any failing criteria. | [primary] |

### A3. A research protocol to encode

The protocol is designed for an agent working inside a chat with search, fetch and (optionally) sub-agent tools, and without the ability to sign in anywhere.

#### Inputs (from the coordinator)

- `idea_summary`, `scope`, `unknown_areas` (as today).
- `decision_questions`: the 3–7 questions whose answers would change the decision, for example "Is there already a free plugin that does this?" or "Will the Chrome Web Store accept the permissions we need?"
- `builder_profile` (see B6), so feasibility and distribution research targets the actual builder.
- `budget_tier`: `quick` | `standard` | `deep`.
- `today`: the date, used for freshness and for the source log.

#### Step 0. Question plan (STORM-lite, about 2 minutes, no tool calls)

Write 2–3 questions from each of 4 perspectives:

1. **The would-be user**: what do they use today, and what do they complain about?
2. **The incumbent or competitor**: who already does this, and how do they make money?
3. **The gatekeeper**: store review, platform policy, API terms of service, law.
4. **The skeptic who has seen this fail**: dead competitors, post-mortems, "why X failed".

Then add **mandatory disconfirmation queries** (at least 3): "<idea> failed / shut down / discontinued", "<closest competitor> problems / criticism", "why not <core approach>", "<X> alternatives". Log these queries in the output, so the user can see they were run.

#### Step 1. Retrieval (wide, then narrow)

- Start with short, broad queries. Narrow only after you see what exists ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)).
- **The fetch rule:** search results and search-tool summaries are **leads only**. They can produce 🔍 items, never ✅. Any claim that will be labeled ✅ must come from a **fetched page**.
- Prefer the **original** page over coverage of it: the vendor's pricing page, the store listing, the repo, the policy page, the paper.
- For an unfamiliar publisher, run one lateral query before trusting it.

#### Step 2. Source log (stored in the project record)

| id | URL | publisher | type (primary/secondary/tertiary) | page date / "as of" | fetched | exact quote (≤25 words) | supports claim ids | independence group |
|---|---|---|---|---|---|---|---|---|

Rules:

- The quote must be copied from the fetched text, not paraphrased.
- If the fetch tool returns only a summary, mark the quote "(summarized by fetch tool)" and cap the claim at ✅ for non-numeric claims. Numbers need the number visible in the returned text.
- Sources in the same **independence group** (same owner, syndication, one citing the other) count as one source.

#### Step 3. Minimum evidence per claim type

| Claim type | Minimum for ✅ | Otherwise |
|---|---|---|
| **Competitor exists / does Y** | 1 primary page (product site, store listing, repo) fetched, plus a **last-activity date** (last commit, update or release). | ⚠️ if only third-party mentions. |
| **"No competitor exists" (absence)** | **Never ✅.** At most ⚠️ "none found", with the list of channels searched and the queries used (checklist below). | 🔍 if fewer than 6 channels were checked. |
| **Pricing** | The vendor's own pricing page, fetched today, with tier, region and currency noted. | Third-party price mentions are 🔍 leads only. |
| **Market size / TAM** | 2 independent sources that **state their method**, with year and geography. Prefer a bottom-up proxy (store counts, installs, stars, subreddit size, search volume) over top-down TAM reports. | Do not state the number. Give the proxy instead. |
| **Technical feasibility** | Official docs or API reference for the version used (fetched) **plus** one existence proof (a repo or demo doing the same thing). Record rate limits and ToS constraints. | ⚠️, plus a recommended spike (a timeboxed prototype). |
| **Regulation / platform policy** | The official text (statute, regulator page, platform policy page) with its effective date and jurisdiction. Explainers are for orientation only. | 🔍, plus "check with <official page>". |
| **Statistic / base rate** | A source with a stated method, denominator and year. | Do not use it as an anchor. |
| **Demand signal** | At least 2 independent channels (for example Reddit threads plus HN comments plus GitHub issues), with counts and a verbatim user phrase. | ⚠️ "anecdotal". |

#### Step 4. Labels

Keep ✅/⚠️/🔍, but make ✅ mechanical: **✅ = a fetched source with a logged quote and an as-of date, and two independent sources if the claim is numeric or contested.** Show provenance inline, for example `✅ [S3, S7] as of 2026-10`. Use ✅ only for single-source primary facts such as "the pricing page says $X", where one source is enough. For decision-relevant claims, add a numeric confidence (the existing anchors in `recommendation-confidence.md`).

#### Step 5. Verification pass (separate from synthesis)

1. Decompose the draft briefing into atomic, decision-relevant claims (FActScore/SAFE style).
2. For each claim, the verifier **re-fetches** the cited page and checks that (a) the URL resolves, (b) the quote is present, (c) the quote supports the claim as worded, and (d) the date is within the freshness window.
3. The verifier should run in a **fresh context**: a sub-agent that receives only the claim list and the source log, not the drafter's reasoning ([Huang](https://arxiv.org/abs/2310.01798), [Panickssery](https://arxiv.org/abs/2404.13076), [Zhang](https://arxiv.org/abs/2608.23045)). If the host offers a different model, use it. If no sub-agent is available, run the pass as a separate step with the instruction "assume each claim is wrong until the quote is found".
4. Failures get downgraded or retracted, and every retraction is listed in the output, which builds trust.
5. Self-score against the Anthropic rubric (factual accuracy, citation accuracy, completeness, source quality, efficiency) and report the score.

#### Step 6. Budget and stopping rule

| Tier | When | Budget (tool calls) | Verifier |
|---|---|---|---|
| `quick` | personal project, reuse-vs-build check | about 8–15 | top 5 claims |
| `standard` | default for startup / plugin / game | about 20–40 | all decision-relevant claims |
| `deep` | one-way door, money at stake, regulated domain | 40+, or parallel sub-agents | all claims plus disconfirmation re-run |

The budgets are my proposal, scaled by analogy from Anthropic's "3-10 tool calls" for simple fact-finding ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)).

**Stop** when (a) every `decision_question` has an answer or an explicit 🔍, **and** (b) **saturation**: the last 3 queries in each perspective produced no new competitor or fact, **or** (c) the budget is spent. The output says which condition triggered the stop.

#### Step 7. Output additions

- **Coverage line:** the channels checked and the channels **not** checked (with reason: login wall, not indexed, budget).
- **"Not verified" block:** claims left at 🔍, searches that returned nothing, pages that could not be fetched (403, paywall), and for each one the specific action that would resolve it (for example "log into App Store Connect and check category X").
- **Retractions:** claims removed in the verification pass.
- **Disconfirmation results:** what the "why it failed" queries found, even if nothing.

#### Competitor search checklist (software, plugins, games, web apps)

Record for each hit: name, URL, what it does, price, **last activity date**, traction proxy (stars, installs, review count), and how it differs. Mark each channel checked or unchecked.

1. **General web**: "<problem> tool", "<X> alternative(s)", "<X> vs", "best <category> 2026", "<X> open source", "<X> self-hosted".
2. **GitHub**: keyword and topic search, sorted by stars *and* by recently updated. Check `awesome-<domain>` lists. Archived repos count as dead competitors ([github.com/search](https://github.com/search)).
3. **Package registries / IDE marketplaces**: npm, PyPI, crates.io, VS Code Marketplace / Open VSX, JetBrains Marketplace.
4. **Agent and plugin marketplaces**: Hermes Agent marketplace ([hermes-agent.nousresearch.com/marketplace](https://hermes-agent.nousresearch.com/marketplace); reported at about 976 entries in Official/Verified/Community tiers ([AlphaSignal](https://alphasignal.ai/news/nous-research-launches-hermes-agent-marketplace-with-976-plugins)) [secondary; the counts in that write-up are internally inconsistent]), agentskills.io, Claude Code plugin marketplaces, MCP registries, OpenAI apps/GPTs, Raycast Store, Obsidian community plugins, Chrome Web Store, Firefox Add-ons, Figma Community, WordPress/Shopify app stores (as relevant).
5. **App stores**: Apple App Store, Google Play (search plus "similar apps"), Microsoft Store.
6. **Games**: Steam (tag search, "more like this"), itch.io, SteamDB. Revenue estimators (Gamalytic, VG Insights) are **estimates**; Gamalytic itself warns of up to about 50% error ([secondary via search summary](https://gamedevreport.beehiiv.com/p/19-606-steam-games-made-16b-in-2025-most-made-0-but-that-s-not-a-problem)).
7. **Launch sites**: Product Hunt (search plus topics), Show HN via HN Algolia search ([hn.algolia.com](https://hn.algolia.com/)), BetaList, Indie Hackers product pages.
8. **Discussions (demand and complaints)**: HN comments, Reddit (r/SideProject, r/selfhosted, r/gamedev, domain subreddits; `site:reddit.com` queries), X (often login-walled, so mark as unchecked if so), Discord servers (not indexed, so always "unchecked").
9. **Dead competitors**: "<X> shut down", "sunset", "discontinued", archived repos, Wayback snapshots of dead product pages. Dead competitors are the best evidence for the premortem and for the base rate.
10. **Absence statement**: if nothing is found, write "No direct competitor found in channels 1–9 (queries logged) as of <date>". That is ⚠️, never ✅.

---

## B. Judgment quality

### B4. LLM judgment biases relevant to critique, and mitigations

#### The biases (evidence)

- **Sycophancy is the default behavior.** Five state-of-the-art assistants were consistently sycophantic across four tasks. Humans and preference models sometimes prefer convincingly written sycophantic answers over correct ones ([Sharma et al. 2023, arXiv:2310.13548](https://arxiv.org/abs/2310.13548)) [primary]. On personal-advice queries, LLMs offered emotional validation in 76% of cases (vs 22% for humans) and used indirect language 87% of the time (vs 20%) ([Cheng et al., ELEPHANT, arXiv:2505.13995](https://arxiv.org/abs/2505.13995v2)) [secondary, via search summary]. In April 2025 OpenAI rolled back a GPT-4o update after an extra reward signal from thumbs-up/down feedback weakened the signal that had been "holding sycophancy in check" ([OpenAI, "Expanding on sycophancy"](https://openai.com/index/expanding-on-sycophancy/)) [secondary; the page returned 403, content via coverage].
- **Caving after pushback.** When challenged with "Are you sure?", models flip their answer **46%** of the time on average, and accuracy drops **17%** ([Laban et al., FlipFlop, arXiv:2311.08596](https://arxiv.org/abs/2311.08596)) [primary]. SycEval: sycophancy appeared in **58.19%** of cases, and **14.66%** were *regressive* (switching from a correct answer to a wrong one). **Citation-based rebuttals produced the highest regressive rates.** Sycophancy persisted 78.5% of the time once triggered ([Fanous et al., AIES 2025, arXiv:2502.08177](https://arxiv.org/abs/2502.08177)) [primary]. This matters directly here: a user pasting "but this article says..." is the strongest trigger for a wrong flip.
- **Position, verbosity and self-enhancement bias in LLM judges** ([Zheng et al., NeurIPS 2023, arXiv:2306.05685](https://arxiv.org/abs/2306.05685)) [primary]. Changing the order of two answers swung a ChatGPT judge enough that Vicuna-13B "beat" ChatGPT on 66 of 80 queries ([Wang et al. 2023, arXiv:2305.17926](https://arxiv.org/abs/2305.17926)) [primary]. LLM judges favor their own generations ([Panickssery et al. 2024](https://arxiv.org/abs/2404.13076)) [primary].
- **Overconfidence.** Browsing raises confidence in wrong answers (BrowseComp, 91% calibration error) ([Wei et al. 2025](https://arxiv.org/html/2504.12516v1)) [primary]. LLM forecasters show acquiescence bias: their mean predictions were above 50% although the questions resolved roughly half and half ([Schoenegger et al. 2024, arXiv:2402.19379](https://arxiv.org/abs/2402.19379)) [primary].
- **Anchoring.** Anchoring is common across LLMs, conventional mitigations do not remove it, and reasoning reduces it somewhat ([Huang et al. 2025, arXiv:2505.15392](https://arxiv.org/abs/2505.15392)) [primary]. Models are more susceptible to high anchors than low ones (Owusu & Feldman, ACL 2026, [aclanthology 2026.acl-short.16](https://aclanthology.org/2026.acl-short.16/)) [secondary]. In a brainstorm the anchors are the user's first idea, the user's numbers, and the first variant generated.
- **Self-critique without external input does not work reliably** ([Huang et al. 2023](https://arxiv.org/abs/2310.01798)) [primary]. **Inertia toward one's own earlier steps** ([Zhang et al. 2026](https://arxiv.org/abs/2608.23045)) [primary].

**Note on critic placement.** A critic that runs in the conversation's context is plausibly as sharp or sharper than an isolated one at *finding* cracks, because context helps specificity. The evidence above points to a different risk: **holding** a verdict under pushback, and judging one's own choices. These are not contradictory. Keep the in-context critic as the default, and add independent samples and pre-commitment as guards.

#### Mitigations, with evidence strength

| Mitigation | Evidence | How to encode |
|---|---|---|
| **Pre-commitment of the verdict** | Indirect: FlipFlop and SycEval show that flips happen *without new evidence*. | The critic stores its verdict and probabilities **before** it shows them to the user. Any later change must name the *new evidence* that caused it, and the log records "changed because <evidence>" or "unchanged". Pushback without evidence: restate the verdict once and keep it. |
| **Treat citation-based pushback as a claim to verify** | SycEval: citation-based rebuttals cause the most regressive flips. | When the user cites a source, check it like any claim (fetch, quote check) before updating. |
| **Opposite case first** | Consider-the-opposite (Lord et al. 1984) [unverified]. Premortems generate more risks and lower overconfidence (Veinott et al. 2010; Gallop & Bischoff 2016, summarized by [Collins](https://corporate.jcx.au/premortem)) [secondary]. | The critic writes the steelman *against* the idea before it lists anything in favor, in that explicit order. |
| **Independent samples, then aggregate** | A crowd of 12 LLMs matched a crowd of 925 humans on forecasting ([Schoenegger et al.](https://arxiv.org/abs/2402.19379)) [primary]. Best-of-N and voting gave +15–25% on BrowseComp ([Wei et al.](https://arxiv.org/html/2504.12516v1)) [primary]. Multi-agent debate improved factuality ([Du et al. 2023, arXiv:2305.14325](https://arxiv.org/abs/2305.14325)) [primary]. Anthropic recommends best-of-N comparison to detect inconsistency ([Claude docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)) [primary]. | For key probabilities (thesis holds, top premortem cause), elicit 3 independent estimates (separate sub-agents or separate prompts without each other's output) and report the median and the spread. A wide spread is itself a finding. |
| **Cross-model or fresh-context review** | Self-preference ([Panickssery](https://arxiv.org/abs/2404.13076)) and inertia ([Zhang](https://arxiv.org/abs/2608.23045)) [primary]. I found no direct study showing that cross-model critique of *business ideas* beats same-model critique (open question). | For one-way-door verdicts, add a fresh-context "red team" sub-agent that gets only the one-page idea summary plus the evidence log, and reconcile its verdict with the in-context one. Use a different model when the host allows it. |
| **Rubric scoring, evidence before score, order randomized** | Multiple-evidence calibration and balanced position calibration reduced judge bias ([Wang et al.](https://arxiv.org/abs/2305.17926)) [primary]. | When comparing variants (Phase 3, recommendation ties), score each variant *separately* against a fixed rubric, writing evidence first and then the score. Never ask "which is better, A or B" in a single pass. If you do compare in one pass, run both orders. |
| **Explicit base rates (outside view first)** | Showing models the human median improved accuracy by 17–28%, and simply averaging human and model forecasts did better still ([Schoenegger et al.](https://arxiv.org/abs/2402.19379)) [primary]. | The critic states a sourced reference class and base rate *before* it reads the user's numbers or writes the inside-view premortem. |
| **Calibration prompts** | Verbalized confidence from RLHF models is better calibrated than token probabilities, with about 50% relative reduction in expected calibration error ([Tian et al., EMNLP 2023, arXiv:2305.14975](https://arxiv.org/abs/2305.14975)) [primary]. Less than one hour of forecasting training improved Brier scores by 6–11% (Chang et al. 2016, *JDM*) ([dlab.sauder.ubc.ca](https://dlab.sauder.ubc.ca/sjdm/journal/16/16511/jdm16511.html)) [secondary]. | Keep the numeric confidence. Add an acquiescence check: "If every probability I gave is ≥50%, re-examine". Track Brier scores (B5). |

### B5. Forecasting practices to borrow

1. **Reference class forecasting / outside view.** Kahneman and Lovallo's argument is that planners take the "inside view" and are overoptimistic, and that the fix is to forecast from the outcomes of a class of similar projects ([Lovallo & Kahneman, HBR, July 2003](https://hbr.org/2003/07/delusions-of-success-how-optimism-undermines-executives-decisions)) [primary for authorship and date; the procedure details are from memory, unverified]. Flyvbjerg's operational version: ignore the specifics, lay out the reference-class distribution, place the project in it, regress the inside-view guess toward the class mean, and widen the interval to the class spread. The uplift is read off a percentile chosen by risk appetite. In his rail example, a 40% uplift gave a 50% overrun risk and a 68% uplift gave a 10% risk ([Flyvbjerg, arXiv:1303.6571](https://arxiv.org/pdf/1303.6571); [Edinburgh Tram report, arXiv:1805.12106](https://arxiv.org/pdf/1805.12106)) [secondary, via search summary].
   **For the agent:** pick the reference class, cite its distribution, then adjust with *named* reasons, each with a bounded size.

2. **Base rates relevant to the owner's domains** (a seed table for the plugin; each row needs re-verification on a schedule):

   | Reference class | Base rate | Tag |
   |---|---|---|
   | Steam games released in 2025 | About 20,000 releases. Median revenue about $249. About 66% earned under $1,000. Estimates may be off by up to about 50% ([Game Dev Report summary of Gamalytic/VG Insights](https://gamedevreport.beehiiv.com/p/19-606-steam-games-made-16b-in-2025-most-made-0-but-that-s-not-a-problem)) | [secondary] |
   | Chrome Web Store extensions (2019 snapshot) | 87% under 1,000 installs, 50% under 16 installs, about 10% with zero ([TechSpot on Extension Monitor](https://www.techspot.com/news/81286-most-google-chrome-extensions-have-fewer-than-1000.html)) | [secondary, dated] |
   | US new employer establishments | About 49% survive 5 years (1994–2022 average, BLS via SBA tabulation) ([BLS BED](https://www.bls.gov/bdm/bdagefaq.htm)). Poor reference class for side projects. | [secondary] |
   | Experienced developers using AI tools on their own repos (early 2025) | They were **19% slower**, after expecting to be 24% faster, and still *believed* afterwards that they had been 20% faster ([METR RCT, arXiv:2507.09089](https://arxiv.org/abs/2507.09089)). This is the base rate for optimism about build time with AI. | [primary] |
   | AI agent task length | The 50% time horizon was about 50 minutes for Claude 3.7 Sonnet and has doubled roughly every 7 months since 2019 ([METR, arXiv:2503.14499](https://arxiv.org/abs/2503.14499)) | [primary] |

3. **Premortem (Klein).** Assume that the project has failed and generate the reasons ([Klein, HBR, Sept 2007](https://hbr.org/2007/09/performing-a-project-premortem)) [primary for the article]. The evidence that it improves *outcomes* is thin. It reliably produces *more* reasons and risks and lowers overconfidence, but outcome data is lacking ([Collins](https://corporate.jcx.au/premortem)) [secondary].
   **Implication:** keep the premortem as a risk *generator*. Do not treat its percentages as calibrated unless they are anchored to the base rate. A premortem's "5 ranked causes with %" should state that the percentages are conditional on failure, and give the overall failure probability from the reference class.

4. **"What would have to be true".** Strengthen each assumption into: test → cost → deadline → kill threshold.

5. **Outside view, then inside view.** Order matters because of anchoring (B4). Outside view first, then the inside-view adjustments, each one written as "+/− N points because <evidence>".

6. **Probabilities with calibration tracking (Brier score).** Brier = the mean squared error between the stated probability and the 0/1 outcome. 0 is perfect, and always saying 50% scores 0.25 (standard definition) [unverified, textbook]. Calibration is learnable with feedback ([Chang et al. 2016](https://dlab.sauder.ubc.ca/sjdm/journal/16/16511/jdm16511.html)) [secondary]. LLM forecasting systems approach crowd level: one system "nears the crowd aggregate of competitive forecasters" ([Halawi et al. 2024, arXiv:2402.18563](https://arxiv.org/abs/2402.18563)) [primary]. On ForecastBench, superforecasters scored 0.086 vs 0.103 for the best LLMs in the latest post I found ([FRI substack](https://forecastingresearch.substack.com/p/llms-are-closing-the-gap-on-human)) [secondary].

7. **Kill criteria and tripwires.** Pre-commit, *before* results, to thresholds that trigger kill or pivot (for example "fewer than 30 installs 14 days after the store listing goes live → stop feature work and run the distribution test"). This fits naturally with a "fair shot" bound in the critique (thesis vs parameters). Annie Duke's *Quit* popularized kill criteria [unverified].

8. **How to record and score predictions (for the recheck).** Keep a **Predictions** table in the project record:

   | id | made | by (model/user) | statement (binary, observable) | p | resolve by | resolution source | outcome (1/0/void) | Brier |
   |---|---|---|---|---|---|---|---|---|

   - Every critic verdict produces 3–5 predictions: the thesis test result, the top premortem cause, the time to first release, the first traction threshold, and any tripwire. Each must be binary, dated and observable by the user.
   - The model's probability and the user's probability are recorded **separately** (ask the user for a number). Over time, this shows who is better calibrated in this domain.
   - Recheck: list the predictions that are due, ask for each outcome, compute Brier per source, and show running totals. With fewer than about 20 resolved predictions, show raw hits and misses and warn that the sample is too small for calibration conclusions.
   - Run-record fields (model recommendation / decision / prediction / outcome) are mandatory for go/kill decisions.

### B6. Making the critic understand who will build the thing

**Why it matters.** The cost structure of a project depends on the builder. For a solo developer with AI coding agents, the code-shaped work compresses, though less than they think: METR found experienced developers 19% slower while they believed they were faster ([METR](https://arxiv.org/abs/2507.09089)) [primary]. **Calendar-bound** work does not compress at all. Examples, all from official pages fetched in this session [primary]:

- **Google Play:** personal developer accounts created after 13 Nov 2023 need **12 testers opted in for 14 consecutive days** of closed testing before production access ([Play Console Help](https://support.google.com/googleplay/android-developer/answer/14151465)).
- **Apple App Review:** it "typically review[s] at least 50% of submissions in less than 24 hours and 90% in less than 48 hours"; incomplete submissions are delayed ([Apple](https://developer.apple.com/distribute/app-review/)).
- **Steam:** a $100 fee per app, recoupable after $1,000 AGR ([Valve](https://partner.steamgames.com/doc/gettingstarted/appfee)); a 21-day wait between paying and release ([Valve onboarding](https://partner.steamgames.com/doc/gettingstarted/onboarding)); a Coming Soon page live for at least two weeks ([Valve](https://partner.steamgames.com/doc/store/coming_soon)).
- **Chrome Web Store:** "most... within a few days, but it can take up to a few weeks". Broad host permissions, powerful permissions, large code, new developers and new extensions all lengthen review ([Chrome docs](https://developer.chrome.com/docs/webstore/review-process)).

On top of these come account and identity checks, payments and tax setup, ToS and legal review, and building an audience. These items set the real critical path for a solo builder.

**Builder profile fields** (user-authored, short):

- **Team:** solo / duo / team. Which AI agents they use, and how autonomously.
- **Fluent stacks** and **hated tasks** (marketing, support, design). Hated tasks predict abandonment.
- **Time:** hours per week and the horizon (a weekend, 1 month, ongoing).
- **Cash budget**, and recurring costs they will tolerate.
- **Accounts already held:** Apple Developer, Google Play, Steam partner, Chrome Web Store, Stripe/payments, domains, plugin-marketplace publisher status.
- **Distribution assets:** followers or newsletter (size), GitHub stars, Discord, past launches and their results.
- **Jurisdiction**, which affects payments, tax and regulation.
- **Goal:** fun / learning / portfolio / income, plus risk tolerance.

**Tension with cross-project isolation.** Projects should not silently import each other's context or the user's background. Keep that rule (no silent import) and add one sanctioned path:

- Store a single user-level builder profile.
- At the start of each brainstorm, show it and ask "Use this profile? (yes / edit / no)".
- Log in the project record which profile version was used.

This turns the profile into an explicit, per-session invocation rather than a silent import.

**How evaluation changes by profile**

| Dimension | Solo + AI agents | Small team | Non-coder / novice |
|---|---|---|---|
| Build-time estimate | Split the work into **agent-compressible** items (code, tests, docs, assets) and **calendar-bound** items (reviews, tester quotas, waiting periods, KYC, legal, audience). Apply the METR caution to the first and official timelines to the second. | Add coordination overhead. | Skill gaps are the #1 risk. Prefer no-code or existing tools. |
| Premortem top causes | Abandonment, no distribution, store or review friction, scope creep (agents make adding features cheap). | Misalignment, burn. | Never finishes, tooling wall. |
| Feasibility check | Does the stack match "fluent stacks"? Is the hard part inside or outside agent competence (for example novel algorithms, platform-specific native APIs)? | Same, per person. | Ask what they have built before. |
| Distribution realism | With zero distribution assets, assume store-discovery base rates (for example the Chrome and Steam distributions above). With an audience, use their past launch results as the reference class. | Same. | Same. |
| Plan shape | Start calendar-bound items on **day 1**, in parallel with building: pay the Steam fee and publish the Coming Soon page early, recruit 12 Play testers early, minimize Chrome host permissions to shorten review. | Assign owners. | The smallest usable version first. |
| Kill criteria | Time-boxed in hours or weekends, plus a traction tripwire. | Budget-based. | Learning-goal based. |

---

## Design consequences for the plugin

Each item names where it lives in hermes-blueprint (H1-H8 refer to `docs/ARCHITECTURE.md`).

1. **Research protocol (H1, H2; Phase 2 reference file and `idea_research`):** the A3 protocol: the question plan (4 perspectives), mandatory disconfirmation queries, the fetch rule (snippets are leads only), the source log, the minimum-evidence-per-claim-type table, budget tiers and the saturation stopping rule, and the output additions (coverage line, "Not verified" block, retractions, disconfirmation results). The competitor search checklist is part of it.
2. **What ✅ means (H1, `idea_claim`):** ✅ is mechanical: fetched page + logged quote + as-of date, and two independent sources if the claim is numeric or contested. Independence is defined. Absence claims are never ✅. Inline provenance `[S#]` is required.
3. **Verifier pass (H3):** after Phase 2, and before any recommendation that rests on Tier 3 facts, a fresh-context subagent receives only the claims and the source log: re-fetch, quote check, URL liveness, retract or downgrade. A documented fallback covers hosts without subagents.
4. **User-cited sources:** the same evidence rule (fetch, quote, date, independence) applies, producing a source-log row. If the claim came from the user as pushback with a citation, the citation is verified before any verdict changes.
5. **Critic, first step "Outside view" (H4):** name the reference class, give a sourced base rate, and only then run the premortem. The premortem percentages are stated as conditional on failure, alongside the overall failure probability from the reference class.
6. **Critic, pre-commitment and anti-sycophancy (H4, `idea_verdict`):** the verdict and probabilities are stored before they are shown. A change requires named new evidence, logged as "changed because...". Pushback without evidence: restate once and keep the verdict. Acquiescence check: all probabilities ≥50% means re-examine.
7. **Critic, independent sample for one-way doors (H4):** optionally a fresh-context red-team subagent (a different model if available) on the one-page summary plus the evidence log, then reconcile. The in-context critic stays the default (see the note in B4). For key probabilities, take 3 independent estimates and report the median and spread.
8. **Critic, builder calibration (H5):** calibrate to the **builder profile** (B6 table), not only to the project kind. The premortem for a solo builder must consider calendar-bound and distribution causes.
9. **Recommendation confidence:** no unsourced base rates. A cited reference class from a maintained base-rate table (seeded from B5 §2, each row with a source and a review date). The acquiescence check applies. Every recommendation emits at least 1 scoreable prediction.
10. **Project record (`plugin_db`):** **Builder profile (as used, version/date)**, **Predictions** (B5 §8 table), **Source log** (A3 Step 2), **Not verified**, and **Verdict changes** (with evidence). Run-record fields are mandatory for go/kill decisions.
11. **Recheck (H8):** before the thesis-vs-tuning diagnosis, resolve the predictions that are due, compute Brier per source (model vs user), check tripwires and kill criteria, and append the results. Small-N warning below about 20 resolved predictions.
12. **Planner (H6):** split tasks into agent-compressible and calendar-bound. Calendar-bound items go on day 1 (store accounts, tester recruitment, Coming Soon pages, review submissions, payments). Every green-light criterion becomes a dated tripwire with a kill threshold and a defined "fair shot" budget.
13. **Builder-profile onboarding (H5):** a user-level profile, shown and confirmed at the start of each brainstorm, its use logged; this is the sanctioned explicit path past cross-project isolation.
14. **Per project kind:** a default `budget_tier` and the required claim types. Personal project: `quick` tier, competitor checklist limited to "reuse-before-build" channels (GitHub, registries, plugin marketplaces). Startup: `standard` or `deep`, full checklist plus pricing and demand evidence.
15. **User-facing docs:** explain the evidence chain, the verifier, outside-view-first, pre-commitment, the prediction ledger and the builder profile, with the citations from this file, for example "snippet ≠ evidence fights citation errors" and "prediction ledger fights uncalibrated confidence".

## Open questions

1. **Hermes runtime capabilities.** Does Hermes Agent provide (a) sub-agents with fresh context, (b) a choice of model per sub-agent, and (c) a fetch tool that returns **raw page text** rather than a model summary? Quote verification is only as strong as (c). If fetches are summarized, the verifier needs a raw-text path, or claims have to be capped at a lower label.
2. **Token and latency budget.** Anthropic reports that multi-agent research uses far more tokens than chat (I recall about 15x, [unverified]). What per-session cost does the owner accept for the `standard` and `deep` tiers?
3. **Is the in-context critic enough** compared with "in-context plus a fresh-context cross-model red team" once pre-commitment and outside-view-first are in place? Test it on a set of sample ideas with a fixed rubric and randomized order.
4. **Prediction resolution.** Users rarely come back. Should the plugin schedule reminders (if Hermes supports scheduling), or ask for outcomes at the next session start?
5. **Small-N calibration.** One user produces few resolved predictions. Is opt-in anonymous pooling across users acceptable, given the privacy concerns?
6. **Login-walled channels** (X, some Reddit views, Discord, App Store Connect analytics). Accept them as declared gaps, or let the user paste data in?
7. **Base-rate table upkeep.** Who re-verifies the rows (for example the 2019 Chrome snapshot is stale) and how often? Should each row carry an expiry date that downgrades it to 🔍 automatically?
8. **Builder-profile privacy.** Where is the user-level file stored, and should it be excluded from any shared or scaffolded output?
9. **Unverified items in this document** that need checking before they are quoted in the plugin docs: Lord et al. 1984 (bibliographic details), the Lovallo & Kahneman procedure details, the Brier definition wording, Annie Duke's *Quit*, the ELEPHANT and OpenAI sycophancy figures (secondary), the Steam 2025 and Chrome 2019 base rates (secondary), and the Hermes marketplace counts (secondary, internally inconsistent).
