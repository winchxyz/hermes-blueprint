# Phase 1: Understanding

Goal: understand the idea well enough that research has a target. No solutions yet.

## Interview

Ask one or two questions per turn, in this order, skipping what the user already said:

1. Who has the problem, and how do they deal with it today?
2. What exactly is the idea, in one sentence? What is it not?
3. Why now? What changed (a platform, a model, a price, a rule)?
4. What would "worth it" mean: fun, learning, portfolio, income (how much, by when)?
5. Constraints: deadline, budget, must-use or must-avoid tech, platforms.

Reflect back a short summary and let the user correct it.

## Builder profile

Call `idea_profile(action=get)`.

- If a profile exists, show it in two or three lines and ask "Use this profile? (yes / edit)".
- If fields are missing, ask for them with at most three questions: team and agents used, hours
  per day, accounts already held and audience. Store answers with `idea_profile(action=set)`.
- Fields the user does not answer get a default; name them in `assumed` when you confirm.
- After the user agrees: `idea_profile(action=confirm, assumed=[...])`.

## Record and advance

`idea_phase(action=record, kind=brief, content={...})` with:

```json
{"who": "...", "problem": "...", "idea": "...", "not": "...", "why_now": "...",
 "success": "...", "constraints": ["..."], "kind": "personal | startup | product | other"}
```

Then `idea_phase(action=advance)`. Phase 2 starts with a research plan.
