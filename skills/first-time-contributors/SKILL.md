---
name: first-time-contributors
description: Use when checking whether recently merged PRs in a GitHub repository include first-time contributors — e.g. "who merged their first PR", "new contributors last week", crediting/celebrating a new contributor, or drafting a shout-out tweet/post. Works on the current repo or any given owner/repo list.
---

# First-Time Contributors Check

## Overview

Finds authors whose first-ever merged PR in a repo landed within a recent window (default 7 days). Uses `gh` CLI: list merged PRs in window, then per author count merged PRs before the window — zero prior = first-timer.

## Usage

```bash
~/.claude/skills/first-time-contributors/check-first-timers.sh                       # current repo, last 7 days
~/.claude/skills/first-time-contributors/check-first-timers.sh --days 14             # wider window
~/.claude/skills/first-time-contributors/check-first-timers.sh owner/repo owner/other-repo   # explicit repos
```

Output: per repo, each author with prior-PR count; first-timers flagged with 🎉 plus their PR titles and URLs.

## After running

- If first-timers found and the user wants a shout-out: draft a short celebratory message (tweet-length) crediting the author's handle, linking their PR. **Draft only — never post anywhere.**
- Report near-misses too: authors with 1–2 prior merged PRs are effectively new; mention when their first PR was (`gh api "search/issues?q=repo:OWNER/REPO+is:pr+is:merged+author:LOGIN"`).

## Gotchas

- Bots are excluded (`app/*` logins and `*[bot]`). `wpmobilebot`-style bot accounts without those markers slip through — sanity-check any surprising "first-timer".
- GitHub search API: 30 requests/min. Many distinct authors × many repos → add sleeps or run repos separately.
- "First-time" is per-repo, not org-wide or GitHub-wide.
- `--limit 200` caps PRs scanned per repo window; raise for very active repos.
