---
name: reflect
description: Use after a hard or bumpy task, or when the user says "reflect", "what did we learn", "how do we stop this happening again", or /reflect. Reviews the current session's friction (repeated corrections, failed checks, reviewer comments) and proposes the smallest durable fix, preferring automated checks over prose. Proposes only; applies nothing without approval.
---

# Reflect

Turn this session's friction into one durable fix, so the same mistake can't recur silently. **Never auto-apply.**

## 1. Collect friction (from this conversation only)

List each concrete instance, one line each, with where it happened:
- The user corrected or redirected you (especially the same thing twice).
- A check failed: lint, typecheck, tests, CI, a hook rejection.
- A reviewer comment pointed at something an earlier step should have caught.
- Time lost on a wrong assumption (wrong repo, path, command, convention).

Skip one-off typos and anything already fixed by a rule that exists. If nothing qualifies, say so and stop.

## 2. Pick the smallest durable fix per item

For each item, ask first: **"How do I turn this into a CI failure?"** Then pick the highest option that works:

1. **Lint rule / type / hook / CI check:** the machine catches it next time.
2. **Edit an existing skill or the repo's AGENTS.md:** fix the instructions where the mistake was made.
3. **One CLAUDE.md line:** only if it's a cross-project habit and not already covered.
4. **A memory:** only for facts about the user or their setup that fit nowhere else.

Prefer editing over adding: tighten an existing line before writing a new one. One fix per root cause; merge items that share a cause.

## 3. Propose

```
| # | Friction | Root cause | Fix (tier) | File |
|---|---|---|---|---|
```

Then show the **exact diff** for each proposed fix. Say what each one replaces or removes. Ask which to apply. Apply only the ones approved, back up any file first, and show the final diff.

## Rules

- Don't touch hook scripts or settings.json permissions without an explicit yes for that specific change.
- Don't add tests unless the friction was a real regression in core behaviour.
- Public repos: no internal URLs in any proposed text.
