---
name: brainstorming-names
description: Use when the user wants to name or rename something — a product, feature, brand, project, command, or company — or asks to "brainstorm names", "find a better name", "naming ideas", or invokes /brainstorming-names.
---

# Brainstorming Names (multi-model tournament)

## Overview

Tournament workflow: parallel subagents on **randomized models** generate name candidates each round, a **fixed judge** scores them against a stable rubric, and top names carry forward. Model randomization replaces the removed temperature knob — each model family has a distinct creative distribution ("house style"), so mixing models samples a wider name space than any single model can.

**Core rule: randomize the generators, never the judge.**

## Phase 1 — Collect inputs (ask if missing)

1. What is being named: 1-2 sentence product description + audience.
2. If renaming: why the current name fails (collision, generic, legal).
3. Hard constraints — propose defaults, let user adjust: max words/syllables/characters, pronounceable in English, no trademark collisions (name the adjacent products to avoid), CLI-safe if relevant (lowercase, no spaces).
4. Budget: default 5 rounds × 3 agents × 10 names. Scale up only if user asks for thoroughness.

## Phase 2 — Fix the rubric before round 1; never change it mid-run

Default weights: memorability & distinctiveness 40%, fit with purpose 30%, pronounceability/spellability 15%, brand risk (collisions, bad meanings in major languages) 15%. Score 1–10 per criterion.

**Who judges:** the orchestrator (you) scores inline with this rubric, on your own session model — no judge subagent needed. If a `/score` skill is available, use it with this rubric instead. Either way, the **same judge and same rubric every round** — the judge is never randomized, otherwise round-1 and round-5 scores are not comparable and carried winners get unfairly re-ranked.

## Phase 3 — Tournament loop (per round)

1. **Randomize generator models with bash** — never pick "randomly" from your head (LLM self-selection is biased toward one model). Run via `bash -c` (zsh arrays are 1-indexed; this snippet assumes bash):

```bash
bash -c 'models=(fable opus sonnet haiku); for i in 1 2 3; do echo "${models[RANDOM % ${#models[@]}]}"; done'
```

Duplicates within a round are fine — the strategy still differs. Drop `haiku` from the pool if its candidates' average score is the lowest of all models in each of the first two rounds.

2. **Spawn 3 parallel Agent calls**, each with `model:` set from step 1 and ONE strategy from this ordered list: (1) invented/coined words, (2) real-word metaphors, (3) compound/portmanteau, (4) foreign-language roots, (5) mythology/nature/astronomy. Assign 3 *distinct* strategies per round, cycling through the list in order across rounds (round 1 → strategies 1-3, round 2 → 4, 5, 1, round 3 → 2-4, …). Each subagent prompt MUST contain — subagents see nothing of the conversation:
   - the full product context, verbatim
   - the hard constraints
   - its single assigned strategy
   - the full exclusion list (every name generated in ANY prior round; state "(none — round 1)" in round 1)
   - the current top 2 with scores and the instruction "beat these" ("(none — round 1)" in round 1)
   - output spec: exactly 10 candidates (or the per-agent count chosen in Phase 1) + 1-line rationale each, self-checked against constraints (drop failures and replace before returning)

3. **Score new candidates only.** Carried winners keep their original scores — re-scoring causes drift that kills good names.

4. **Carry top 2 forward.** Track per name: round, generating model, strategy, score.

5. **Early stop:** same #1 for 3 consecutive rounds.

## Phase 4 — Deliverable

Final table: top 5 names × (per-criterion scores, total, round discovered, generating model, strategy) + one-paragraph recommendation for the single winner. Include which models produced the finalists — useful signal for weighting the pool next time.

## Common mistakes

| Mistake | Fix |
|---|---|
| Randomizing the judge | Scores stop being comparable; fix judge model + rubric for the whole run |
| Picking "random" models mentally | Biased; use the bash `$RANDOM` snippet |
| Re-scoring carried winners | Score drift; keep original scores |
| No exclusion list | Later rounds regenerate earlier names, wasting the budget |
| Thin subagent prompts | Subagents lack conversation context; include context block verbatim |
| Vague constraints ("short, memorable") | Unenforceable; convert to numbers before round 1 |
