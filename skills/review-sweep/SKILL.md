---
name: review-sweep
description: Use when Antonio wants to review every PR waiting for his review — "review sweep", "sweep my review queue", "trigger review agents for my PRs", "which PRs need review and review them", or /review-sweep. Also when re-checking a queue already reviewed to catch new or updated PRs.
---

# Review Sweep

Find all PRs requesting my review, skip those with an up-to-date local quick-review MD, fan out parallel `quick-pr-review` subagents for the rest, and report a verdict table.

Review MDs live in `~/claude.nosync/reviews/` named `YYYY-MM-DD-<repo>-<number>-<slug>.md`.

## Steps

### 1. Fetch the queue

```bash
gh pr list --repo <owner>/<repo> --search "review-requested:@me state:open" \
  --json number,title,author,url,isDraft,updatedAt --limit 50
```

Default repo: the current directory's repo (`gh repo view --json nameWithOwner`). Skip drafts (`isDraft: true`) — list them in the table as skipped, don't spawn agents.

### 2. Classify each PR: new / current / stale

A PR needs a review agent when it has **no local MD** or was **updated after the newest MD**.

Freshness compares the PR's **last commit date** — NOT `updatedAt`, which churns on every comment, label, or trunk merge — against the newest matching MD's mtime:

```bash
# newest local review MD for PR $N (repo short name $REPO), epoch mtime or empty
MD=$(ls -t ~/claude.nosync/reviews/*-$REPO-$N-*.md 2>/dev/null | head -1)
MD_TS=$([ -n "$MD" ] && stat -f %m "$MD")
# PR last commit, epoch
PR_TS=$(gh pr view $N --repo <owner>/<repo> --json commits \
  --jq '.commits[-1].committedDate' | xargs -I{} date -j -f "%Y-%m-%dT%H:%M:%SZ" -u {} +%s)
# needs review if no MD, or commit newer than MD
```

Only run the per-PR `gh pr view` for PRs that have an MD; PRs without one need a review regardless.

### 3. Show the queue table

Before spawning: one row per PR — number (linked), title, author, local MD date, status (`new` / `re-review: commit after MD` / `current` / `draft, skipped`).

### 4. Fan out agents — all in ONE message

One `Agent` call per PR needing review, `subagent_type: quick-pr-review`, `name: review-<number>`. Prompt template:

> Review PR #<n> in <owner>/<repo> (<url>) — "<title>" by <author>. Remote-only review (no checkout). Write the markdown review to ~/claude.nosync/reviews/ (dated today). Do NOT post anything to GitHub. Return a concise summary: verdict (approve / needs changes / needs discussion), merge confidence 1-10, and top findings with file:line references.

For **re-reviews**, add: the prior MD path ("read it first"), what changed (last commit date, new human reviews), and "focus on the delta since our review; check whether our prior findings were addressed."

Add PR-specific context when known (security-sensitive → "verify the fix is real, not scanner-appeasement"; dead-code removal → "check trunk hasn't grown importers of the deleted symbols"; dep bumps → repo pinning rules).

### 5. Collect and report

Agents report back as they finish; silent-idle agents get one ping via SendMessage asking for the verdict. When all are in: verify the MD files exist on disk (`ls`), then output the final table — PR, title, verdict, confidence, one-line key point — and flag anything that isn't a clean approve.

## Rules

- Never post reviews, comments, or approvals to GitHub — local MDs only.
- Never spawn an agent for a PR whose newest MD postdates its last commit ("current") — note it in the table instead.
- Drafts: table row only, no agent.

## Common mistakes

| Mistake | Fix |
|---|---|
| Using `updatedAt` for staleness | Comments/labels churn it; compare last **commit** date vs MD mtime |
| Spawning agents one message at a time | All Agent calls in one message → parallel |
| Re-review agent starts from scratch | Point it at the prior MD and ask for the delta |
| Trusting agent report alone | `ls` the MD files before the final table |
