# Phase 4: Deep dive

Goal: compare the variants fairly, find what must be true for the best one, and let the user
choose.

## Compare without bias

LLM judges favour the first option shown, the longer one, and their own earlier ideas. So:

- Score each variant **separately** against the same rubric, writing the evidence first and the
  score second. Never ask "A or B?" in one pass.
- Rubric (1-5 each): demand evidence, competition and differentiation, builder fit (skills,
  accounts, audience from the profile), time to first real use, upside, risk.
- If you compare two directly, do it in both orders.

## What must be true

For the leading one or two variants, list the assumptions that must hold. For each: how to test
it, what the test costs, by when, and the result that would kill it. These carry into the
critique and the plan's gates.

## Record

- `idea_phase(action=record, kind=deepdive, content={...})` with the scores, evidence and the
  must-be-true list.
- Ask the user to choose. Then `idea_phase(action=record, kind=choice, content={"variant":
  "<name>", "reason": "..."})`. The reason is the user's, in their words.
- `idea_phase(action=advance)`.
