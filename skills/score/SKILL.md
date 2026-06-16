---
name: score
description: Use when the user asks to rate, score, judge, critique with a number, or "how good is" an artifact — a live website/UI, a markdown draft (blog post, README, plan, docs), or code/a diff — or invokes /score, or sets up an iterate-until-score-N feedback loop (e.g. with /goal "repeat until 9/10").
---

# Score — calibrated artifact judging

## Overview

Produce a 0–10 quality score that is *earned by reasoning, not vibes*: a fresh judge subagent analyzes the artifact, writes strengths/weaknesses/improvements/reasoning **first**, and only then the score. Designed to drive iterate-until-N feedback loops.

**Core principle: the score comes LAST.** A score stated first anchors everything after it. Never let the judge (or yourself) write the number before the analysis.

## When to Use

- "Score this / rate this / how good is this" for a page, post, diff, plan
- Driving a `/goal repeat until ≥N/10` improvement loop
- NOT for: pass/fail correctness checks (use tests/lint), security review (use /security-review)

## Step 1 — Detect modality and capture the artifact

| Artifact | Capture | Judge input |
|----------|---------|-------------|
| Website / UI | Use the **browse** skill: serve local files over http (`python3 -m http.server`; `file:` is blocked), wait for app-ready state (not just `--load` — wait for the ready selector/element), full-page screenshot | Screenshot path (judge uses Read on the PNG) |
| Markdown / writing | None — no screenshot for text | File path (judge Reads it directly) |
| Code / diff | `git diff <base>` or file list | Diff text or file paths |

Screenshot ONLY makes sense for visual artifacts. Never screenshot a markdown draft.

## Step 2 — Dispatch a FRESH judge subagent

Always a new `general-purpose` subagent per round. Never score in the main context (you wrote the thing — you're biased), and never reuse the previous judge (it anchors on its own last number).

Judge prompt template — include every numbered element:

```
Read <artifact> with the Read tool. It is <one-line context: what the artifact is and its goal/audience>.

[If iterating] This is iteration N of an improvement loop. Iteration N-1 scored X/10
with these weaknesses: <list>. Fixes applied since: <list>.
Rate strictly and independently — do not inflate the score because it improved; judge what you see.

[If a pinned 10-definition exists] The bar for 10/10 was fixed in round 1: <pinned 10-definition>.
Score against THIS bar — do not invent a new vision of perfection.

Return your assessment in exactly this markdown structure:
## Strengths
## Weaknesses
## What a 10 looks like
(describe the concrete end state, specific to THIS artifact — what would exist on the
page/post/diff for you to give 10/10. No generic excellence ("better contrast") —
name the actual elements, content, or structure. If a pinned bar exists, restate it
and note what's still missing.)
## Improvements
(concrete, actionable — the diff between current state and the 10 above)
## Reasoning
(how you weighed strengths vs weaknesses to arrive at the score)
## Score
X/10

Judge these dimensions: <pick from table below>.
Be specific — reference actual elements/sentences/lines, not generic advice.
Calibration: 9–10 = production/portfolio-grade (a stranger would ship/publish it as-is);
7–8 = solid with a visible last mile of polish; 5–6 = sound core, rough execution;
<5 = structural problems. Do not withhold a 9 if earned; do not grant one if not.
Your final message is the deliverable; return only the structured rating.
```

Dimensions per modality:

| Modality | Dimensions |
|----------|-----------|
| Website/UI | visual hierarchy, typography, spacing, color/contrast, clarity of purpose, trust signals, polish |
| Blog post / writing | hook, structure/flow, clarity, voice, evidence & examples, takeaway, title |
| Code | correctness, simplicity, naming, consistency with codebase, error handling, test coverage |
| README/docs | what-is-it speed, quickstart accuracy, gotchas covered, honesty about limits, license/meta |

## Step 3 — Iterate (when a target score is set)

1. Fix the weaknesses (all of them — they're cheap; cherry-picking stalls the loop).
2. **Pin the bar:** round 1's "What a 10 looks like" becomes the fixed rubric. Pass it verbatim to every subsequent judge ("score against this bar"). Fresh judges otherwise each invent a new dream and the loop never converges.
3. Re-capture (fresh screenshot / re-read) and re-dispatch a fresh judge **with the iteration-memory block** (previous score, weaknesses, fixes applied, pinned 10-definition).
4. **Plateau rule:** same score 2 rounds in a row → read the 10-gap. If the gap names *material* (the demo photo itself, the post's core argument, the module's design) — change the substance; CSS/line edits are sanding a local maximum. If the gap names polish — finish the named items, nothing else.
5. Track progression (e.g. 6.5 → 7.5 → 8 → 8.5) so the user sees the trend.
6. Scores are noisy ±0.5 between judges. Near the target, run 2–3 judges and take the median before declaring success.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Score stated before reasoning | Template puts ## Score last — keep it there |
| Each judge invents a new "10" (moving goalposts) | Pin round 1's 10-definition; later judges score against it |
| 10-definition is generic ("more polish", "better UX") | Require artifact-specific end state — actual elements/content named |
| Reusing the same judge across rounds | Fresh subagent every round; pass history in the prompt |
| Omitting "don't inflate because it improved" | Judges drift upward on iteration framing without it |
| Generic advice ("improve contrast") | Require references to actual elements/lines |
| Screenshotting before app ready | Wait for the ready state; mid-load states score wrongly |
| Polishing CSS when the judge flags content | Plateau rule: fix substance, not surface |
| Declaring target hit on one noisy judge | Median of 2–3 judges at the threshold |
