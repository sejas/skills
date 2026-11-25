---
name: pr-desk
description: This skill should be used when the user starts their workday PR session and wants one desk for everything PR — "pr desk", "start my PR desk", "what needs my review", "review sweep", "review queue", "which PRs can I merge", "triage feedback on my PRs", "watch github", "monitor my PRs", "check hourly for reviews", "weekly PR review", or /pr-desk [week]. Gathers PRs awaiting their review and their own PRs with new feedback (github.com + GitHub Enterprise), fans out review and feedback-triage subagents, reports linked tables with merge confidence and recommended actions, lets them pick actions, then watches hourly in the same session. Never posts, pushes or marks anything read.
---

# PR desk

Run once at the start of a workday session (Mondays, or every weekday), then keep watching in
that conversation. One run = gather → fan out → report → pick actions → schedule the watch.

## Files

- `scripts/gather.sh [--summary]`: github.com INCOMING + MINE + notifications as JSON, with
  `delta` per PR against `state.json`. Saves `last-gather.json`. Read-only.
- `scripts/mark-seen.sh [ghe.json]`: record what was reported. Run it **after** the report.
- `scripts/week.sh`, `scripts/board.sh <owner/repo>`: weekly section and repo board.
- `scripts/notifications.sh`, `scripts/find-clone.sh <owner/repo>`: helpers.
- `config.json` (copy `config.example.json`; git-ignored): paths, `board_repos`, agent cap, cron, bot logins.
- `prompts.md`: agent prompts, tick prompt, GHE recipe, report skeleton. Read it before step 2.
- Identity comes from `identity_config` (`gh_user`, `gh_user_enterprise`, `enterprise_host`,
  `enterprise_owner`, `enterprise_repos`). Never hardcode handles or hosts.
- State: `~/claude.nosync/pr-desk/`. Reports: `~/claude.nosync/reviews/pr-desk/YYYY-MM-DD.md`.
  Review docs: `~/claude.nosync/reviews/YYYY-MM-DD-<repo>-<n>-<slug>.md`.

## Hard rules

- Never post to GitHub: no reviews, comments, replies, approvals, thread resolutions.
- Never push. Never commit unless the user asks in this conversation. Fixes stay uncommitted.
- Never mark notifications read (`PATCH /notifications` is forbidden).
- Every PR and Linear number shown is a markdown link, in chat and in the saved report.
- Reply drafts for public repos contain no internal URLs: grep each draft for
  your internal-hosts regex (`internal_hosts_re` in `config.json`) and rewrite any hit before showing it.
- A source that fails is never skipped silently: warning as the reply's FIRST line plus a
  `⚠️ No connection` row in the affected table.

## 1. Gather (parallel, one message)

- `bash ~/.claude/skills/pr-desk/scripts/gather.sh --summary` (then read fields from
  `~/claude.nosync/pr-desk/last-gather.json` with `jq` as needed). Any `errors[]` entry → warning
  rule above; `partial: true` means GONE was suppressed.
- GitHub Enterprise, if configured (`prompts.md` §5): try once, report, move on.
- Monday, or `/pr-desk week`: also `week.sh` and `board.sh` for each `board_repos` entry.

What the JSON already decides (do not recompute):

| Field | Meaning |
|---|---|
| `incoming[]` | open PRs with my review requested (`direct` false = via a team), plus PRs I reviewed that got commits after my review (`rereview`) |
| `freshness` | `new` no review MD · `stale` last commit after newest MD mtime · `current` · `draft` |
| `needs_review_agent` | `new`/`stale` and not draft |
| `mine[].flags` | `changes_requested`, `unresolved:N` (last word not mine), `ci_failing`, `conflicts`, `approved_unmerged`, `new_comments` |
| `needs_triage` | changed since last seen and has feedback to answer |
| `delta` | `new` · `new_commits` · `new_activity` · `state_change` · `unchanged` |
| `gone[]` | PRs seen last run that are no longer open (merged/closed) |
| `notifications[]` | participating notifications not covered above (mentions, team requests on others' PRs) |

Freshness compares **last commit** with the review MD mtime, never `updatedAt` (comments and
labels churn it).

## 2. Fan out (ONE message, ≤ `max_parallel_agents`)

- Each INCOMING row with `needs_review_agent` → general-purpose agent running the `quick-pr-review` skill (`prompts.md` §1).
- Each MINE row with `needs_triage` → general-purpose triage agent (`prompts.md` §2).
- Order: direct requests and re-reviews first, then MINE with `changes_requested`, then oldest.
  Over the cap: launch the first batch, start the next batch as agents finish.
- Bot PRs (dependency bumps) only get an agent when the user is a direct reviewer.
- Collect results. Ping a silent agent once with SendMessage. `ls` the review MDs before
  trusting a verdict. Show the tables (step 3) as soon as the gather is done, with
  `reviewing…` cells, and fill them when agents return; don't block the first answer on them.

## 3. Report

Use the skeleton in `prompts.md` §6. Keep it compact; one table per section.

**Merge confidence 0-100 (INCOMING)**, from the latest review MD for the PR (or the agent's
return): base by verdict, Approve 85-95, Comment/needs discussion 50-70, Request changes 10-40.
Subtract for blocking high-confidence bugs (-10 to -20), open product questions (-5 to -10),
20+ files (-5), draft (-10), no update in a month (-10), failing CI or conflicts (-5).
Add for tiny scope, screenshots and solid tests, only non-blocking findings. Say once that the
score blends verdict, finding severity and staleness. No MD and no agent result → `n/a`.

**MINE** rows: flags in plain words plus one recommended action. Rows with a triage result get
a sub-table (`### Triage: repo#n`) with the recommended option per comment; show the reply
draft text in full (it's what the user will copy).

Save the report to `~/claude.nosync/reviews/pr-desk/YYYY-MM-DD.md` (append `## Tick HH:MM`
sections later in the day; never overwrite the morning run).

## 4. Pick actions

AskUserQuestion, `multiSelect: true`, max 4 questions × 4 options: group as "Fixes",
"Replies", "Reviews", "Other". If there are more candidates, offer the top ones by priority
and list the rest numbered in chat. Options, labelled with the linked PR in the description:

- **apply fix on #N (items t1, t3)** → fix agent, `prompts.md` §3. Change stays uncommitted in
  a worktree; show the diff when it returns.
- **copy reply draft for #N t2** → print the final draft in a code block (and `pbcopy` it when a
  single draft is chosen). The user posts it.
- **open walkthrough for #N** → `/pr-walkthrough <url>`, or run the `layout.sh` command the
  review agent returned.
- **merge-ready #N** → show the checklist (approved, CI, conflicts, unresolved threads) only.
- **nudge draft for #N** (week) → short ping text for the reviewer; nothing is sent.
- **skip**.

Then run `bash ~/.claude/skills/pr-desk/scripts/mark-seen.sh [~/claude.nosync/pr-desk/ghe.json]`
(omit the file when GHE failed, so its old state is kept).

## 5. Weekly section (Monday or `week`)

From `week.sh` and `board.sh`:

- Merged and closed-unmerged of mine since last Monday; count of PRs I reviewed.
- Waiting on others > `waiting_nudge_days`: who is on the hook, and a suggested nudge.
- Oldest review debt (top 5 INCOMING by age).
- Repo board per `board_repos`: every open non-draft PR, columns PR · Title · Author ·
  Created · Updated · Review requested · Conversation · Status. `—` in Review requested marks
  orphans worth grabbing; a team (e.g. a rotation) is not a person. Conversation = unresolved
  threads first, then human comments, then review states; bot chatter is not a conversation.
  Group separately: mine, bots (one line), `merge_candidate` (approved, no unresolved threads).
  Drafts: count only. Flag updated > 30 days as stale.

## 6. Schedule the watch

CronCreate (session cron, not `/schedule`: cloud routines have no `gh` auth):
`cron` from `config.json` `tick_cron` (weekdays 09:07 … 15:07), `recurring: true`, `prompt` =
the tick prompt in `prompts.md` §4, verbatim. Tell the user the job id, the cadence, that it
dies with the session and expires after 7 days, and how to cancel (`CronDelete <id>`).
Don't schedule a second job if one from this skill already runs (CronList).

## Tick mode

The gather is already a delta: act only on rows with `delta != "unchanged"`, `gone[]` and
`notifications[]`. Fan out only for those. Nothing new → reply exactly `pr-desk: nothing new`,
no PushNotification, no mark-seen needed. Something new → compact delta tables, one-line
PushNotification, append to today's report, AskUserQuestion, mark-seen. Don't re-list items
already reported unless they changed. A morning tick (before 10:00) covers the overnight
or weekend gap automatically, because `since` is the last run.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running mark-seen before the report is shown | Deltas are lost on a crash; mark after reporting |
| Using `updatedAt` for review staleness | Use `freshness` (last commit vs MD mtime) |
| Unscoped GHE search returning 0 read as "nothing" | Scope every GHE search by owner + repo |
| Spawning agents one message at a time | One message per batch, ≤ cap |
| `isolation: "worktree"` from a session outside the PR's repo | Use the explicit worktree steps in `prompts.md` §3 |
| Reading every review MD | Only the newest MD per PR still open |
| Re-review agent starting from scratch | Point it at the prior MD and ask for the delta |
