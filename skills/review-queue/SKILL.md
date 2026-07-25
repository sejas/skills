---
name: review-queue
description: Use when Antonio asks which PRs are still open and waiting for his review, wants a merge-confidence table from his saved review docs, or says "review queue", "rate my open PRs", "which PRs can I merge", or invokes /review-queue.
---

# Review Queue

Produce a table of open PRs awaiting the user's review, rated 0-100 on merge-readiness, based on the review docs saved in the Obsidian reviews folder.

## Inputs

- Reviews folder: `~/claude.nosync/reviews/` — where `/quick-pr-review` writes.
- `REVIEW_REPO` — the `owner/repo` to query (your team's main repo). Review filenames may reference other repos; only rate what `gh` can reach.

## Steps

1. **Get open PRs awaiting review** (authoritative filter — do NOT infer from review docs alone):
   ```bash
   gh pr list --repo "${REVIEW_REPO}" --search "review-requested:@me" --state open --limit 100 \
     --json number,title,isDraft,reviewDecision,author,updatedAt
   ```
2. **List review docs**: `ls` the reviews folder. Filenames follow `YYYY-MM-DD-<repo>-<PR>-<slug>.md` (e.g. `2026-07-22-studio-4301-...md`). Prefer `.md` over `.html`.
3. **Match**: intersect open PR numbers with review-doc PR numbers. Multiple docs per PR → read only the **latest by date**.
4. **Read matched docs** (in parallel). Extract: verdict (Approve / Comment / Request changes), critical issues, suggestions with their stated confidence, positive notes, open discussion threads.
5. **Rate 0-100** merge-confidence per PR:
   - Base by verdict: Approve 85-95, Comment 50-70, Request changes 10-40.
   - Subtract for: high-confidence bug findings that block merge (-10 to -20), unresolved product/discussion questions (-5 to -10), large surface (20+ files, -5), draft status (-10), staleness >1 month since last update (-10, likely conflicts).
   - Add for: tiny scope, screenshots + thorough tests, only optional/non-blocking findings.
6. **Output table**, sorted rating descending. Columns — strengths and weaknesses MUST be separate columns:

   | PR | Title | Rating | Strengths | Weaknesses |
   |---|---|---:|---|---|

   - PR column: markdown link to the GitHub PR.
   - Strengths/Weaknesses: 1-2 short phrases each, from the review doc; note verdict + draft/stale status in Weaknesses when applicable.
7. **List leftovers**: open PRs awaiting review with **no** review doc — name them below the table (numbers + short titles), state they can't be rated, suggest `/pr-review` or `/quick-pr-review`.
8. End with a one-line note that ratings blend verdict, finding severity, and staleness.

## Common Mistakes

- Rating PRs from review docs whose PR already merged/closed — always filter through `gh` first.
- Reading every review doc — only read docs matching open+awaiting PRs (folder has 150+ files, most merged).
- Merging strengths and weaknesses into one "Reason" column — they are separate columns.
- Reading an older duplicate doc when a newer one exists for the same PR.
- Treating `review-requested:@me` results as needing re-check — that search already excludes PRs the user has reviewed.
