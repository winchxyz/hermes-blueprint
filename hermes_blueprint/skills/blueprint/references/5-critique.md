# Phase 5: Critique

Goal: an honest verdict on the chosen variant, stored before you show it, with predictions that
can be scored later. You are the critic now: specific, not polite, not hostile.

Known failure modes this phase guards against: sycophancy (agreeing with an enthusiastic user),
flipping under pushback (models change their answer about half the time when asked "are you
sure?", often to a wrong one), anchoring on the user's numbers, overconfidence.

## Order matters

1. **Outside view first.** Before reading the user's own numbers again: what class of projects is
   this (e.g. "Chrome extensions by solo developers", "Hermes plugins in the catalog")? What is
   the base rate of success in that class? Use `idea_verdict(action=base_rates)` or a verified
   claim from the research. No sourced base rate, no verdict.
2. **Steelman against.** The strongest case that this fails, before anything in favour.
3. **Premortem.** Assume it failed. Rank at least 3 causes; each gets its share of failures
   (`p_given_failure`, summing to at most 1). For a solo builder with agents, consider
   abandonment, no distribution, store or review friction, scope creep (agents make adding
   features cheap), and waits that do not compress.
4. **Builder fit.** How the profile changes the risks: skills, hated tasks, accounts, audience.
5. **Estimate realism.** Agent work in hours; which waits set the calendar.
6. **Must be true and tripwires.** From phase 4, sharpened: test, cost, deadline, kill threshold.
   Tripwires are dated thresholds that trigger stop or pivot.
7. **Probabilities.** `p_success` for the thesis within a fair-shot budget, and at least 3
   predictions: binary, observable by the user, dated (the thesis test result, the top premortem
   cause, time to first release, the first traction threshold). Ask the user for their own
   probability for each (`p_user`); both get scored.
   If every probability is 0.5 or more, re-examine for acquiescence and explain why in
   `acquiescence_note`.

## Commit, then show

`idea_verdict(action=commit, ...)` stores it. Then present: verdict, thesis, outside view with its
source, premortem, tripwires, predictions. Say plainly that it is stored and what would change it.

## Pushback

When the user disagrees:

- Call `idea_verdict(action=pushback, argument=...)`. Restate the verdict once, with its strongest
  reason. Do not soften it for an argument alone.
- If they bring a source or a fact: fetch it and record it with `idea_research(action=claim)`.
  Citations are the strongest trigger of wrong flips, so check the quote like any other.
- With new evidence (a claim recorded after the verdict, or a red-team run):
  `idea_verdict(action=revise, new_evidence=["C12"], reason, changes={...})`. The change and its
  evidence are logged.

## Optional red team

For one-way-door decisions (money, quitting a job, a long commitment):
`idea_verdict(action=redteam)` runs an independent critic in a fresh context (a different model
if configured) on a one-page summary. Reconcile: revise citing R# if it changes your view,
otherwise say why it does not.

Then `idea_phase(action=advance)`.
