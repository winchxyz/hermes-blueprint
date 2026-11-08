# Re-check (after the plan)

Goal: learn from reality. Score the predictions, compare estimates with actuals, and decide
whether the results disconfirm the **thesis** or only the **tuning**.

## Steps

1. `idea_recheck(action=report)` (or `overview` first when no project is bound, e.g. in a
   scheduled run). It returns card progress, units with and without actuals, predictions that are
   due, Brier scores and tripwires whose date has passed.
2. For each due prediction, ask the user what happened, then
   `idea_recheck(action=resolve, prediction="P3", outcome="1" | "0" | "void")`.
3. For each finished unit without an actual, ask for the active hours (or days for a wait), or
   use the card's run time when the card shows one: `idea_recheck(action=actual, unit="U2",
   value=1.5)`. Actuals go into the velocity ledger; after 3 in a class, future plans use them.
4. Check the tripwires that are due against what the user reports.

## Thesis or tuning?

- An A unit that ran long is **tuning** (re-estimate the class; the ledger does it).
- An unforeseen wait, a failed must-be-true test or a tripwire crossed is **planning or thesis**.
- A thesis test that failed within its fair-shot budget means the thesis is disconfirmed: say so,
  and propose pivot or stop. A test that was never run fairly means: run it first.

Show Brier scores with the small-sample warning when fewer than ~20 predictions are resolved:
then report hits and misses, not calibration.
