---
name: yolo-guardian
description: Use when the user is on guardian/on-call rotation duty and asks for a "guardian check", "daily guardian", "guardian duties", "triage the queues", "guardian handoff", or invokes /yolo-guardian. Runs the daily monitoring checklist (Slack pings, Linear triage, Dependabot PRs, Buildkite builds, Sentry issues) and the end-of-week handoff.
user-invocable: true
---

# Guardian Daily Check

Weekly rotating role: first line of awareness for the team. Guardian work outranks project
work. Respond or triage the same day during working hours, and route to the right person —
don't fix everything solo.

## Step 0 — load the private config (required)

Everything identifying — who is on rotation, which Slack channels, which Linear teams,
which repos — lives in `config.json` next to this file. It is git-ignored and never
published. **Read it first; this file names no people, channels or internal URLs.**

```bash
cat ~/.claude/skills/yolo-guardian/config.json
```

Missing? Stop and tell the user to create it, listing the keys used below. Never invent
names, channel ids or URLs, and never write any of them back into this file.

Keys: `me`, `rotation_source`, `rotation[]` (`week_starting`, `guardian`),
`slack_channels[]` (`name`, `id`, `primary`, `errors`, `match`), `linear_teams[]` (`key`,
`name`, `triage_url`), `repos[]`, `buildkite_url`, `standup_path`.

Then: match today against `rotation`. Past the last row → fetch `rotation_source` for the
current schedule. Not `me`'s week → say who is on duty and stop, unless the user explicitly
wants to run it anyway. Last working day of their week (usually Friday) → also run **Handoff**.

## Daily checklist — all 5, in order

Track with todos, one per check. Per check report: what's new, what needs action, what was
routed. Parallelize independent tool calls.

### 1. Slack pings

`context-a8c` MCP, `slack` provider (`context-a8c-load-provider`, then `execute-tool`).
Search the last 24h — on Monday, since Friday — across every entry in `slack_channels`, by
id, or by name prefix where `match` is `name-prefix`. Look for mentions, unanswered
questions and team-tagged pings; weight hosting- and support-flavoured channels highest.

Per ping: acknowledge, route to the owner, or open a Linear issue. **Draft replies — never
post without the user's OK.**

### 2. Linear triage queues

`mcp__claude_ai_Linear__list_issues` filtered to Triage, once per entry in `linear_teams`.
Per issue: suggest owner and priority, flag duplicates to close, flag stale ones, escalate
blockers. Propose first; mutate through the Linear MCP only after confirmation.

### 3. Dependabot PRs

```bash
gh search prs --author "app/dependabot" --state open --limit 50 -- repo:<each repos[] entry>
```

Per PR: check CI (`gh pr checks`), then classify — safe-to-merge (patch/minor, green) vs
needs-review (major bump, breaking changes). Merge only on explicit OK; flag breaking
changes to the right person.

### 4. Build health

`buildkite_url` from the config. No API token is configured, so check through the browser
(claude-in-chrome) or ask the user to open it. Look for failing or flaky builds on trunk
pipelines. Failing → suggest a rerun, open a Linear issue, ping the likely author. Don't
wait for someone else to notice.

### 5. Sentry issues

The sentry plugin (`sentry:getIssues`, or the `sentry:issue-summarizer` agent for bulk).
Review new and unresolved issues. Triage each: noise → resolve; real → Linear issue;
user-impacting → escalate in the channel flagged `errors` in the config.

## Log findings

Append a `## Guardian` section to today's standup note at `standup_path` (create it per
/standup conventions if missing): bullets per check — pings handled, issues triaged, PRs
merged or flagged, build status, Sentry outcomes. This is the raw material for the handoff.

## Handoff (last day of the rotation week)

1. Collect the week's `## Guardian` sections from the standup notes.
2. Draft the note: open triage items, in-flight issues being kept, flaky builds under
   watch, anything half-routed.
3. Next guardian = next row in `rotation`.
4. Draft a Slack message for the `primary` channel tagging them. The user sends it.

## Boundaries

- **Never** post to Slack, merge a PR, or mutate Linear without explicit confirmation.
  Read and draft freely; write only on OK.
- Guardian is shared responsibility, not a blocker: route, don't hoard.
- Names, channel ids and internal URLs stay in `config.json`. If you find yourself about to
  write one into this file, a report, or a commit — don't.
