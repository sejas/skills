---
name: pr-leaderboard
description: Use when asked to analyze, rank, or explore merged PRs in a GitHub repo — "who merged what this week", "PR leaderboard", "rank contributors", "top authors", "PRs merged since X", weekly/monthly merge activity — for the current repo or any owner/repo.
---

# PR Leaderboard

Rank merged-PR activity by author using `gh` + `jq`. No checkout needed.

## Defaults

- Repo: current directory's repo (or `--repo <owner>/<repo>`).
- Window: "this week" = since most recent Monday. Otherwise use the user's range.
- Always state the window and repo in the answer.

## Commands

Raw list (titles, authors, sizes):

```bash
gh pr list --repo <owner>/<repo> --state merged --search "merged:>=YYYY-MM-DD" \
  --limit 200 --json number,title,author,mergedAt,additions,deletions
```

Ranking table (PRs per author + line totals, sorted desc):

```bash
gh pr list --repo <owner>/<repo> --state merged --search "merged:>=YYYY-MM-DD" \
  --limit 200 --json number,author,additions,deletions | \
  jq -r 'group_by(.author.login) | map({login: .[0].author.login, name: (.[0].author.name // ""), prs: length, add: (map(.additions)|add), del: (map(.deletions)|add)}) | sort_by(-.prs) | .[] | "\(.login)\t\(.name)\t\(.prs)\t+\(.add)\t-\(.del)"'
```

Date ranges: `"merged:YYYY-MM-DD..YYYY-MM-DD"`. Search also accepts `author:<login>`, `label:<name>`, `base:<branch>`.

## Output

Markdown table ranked by PR count: rank, user (login + real name), PR count, +/− lines, one-line "notable work" summarized from titles. After the table note: human vs bot split, dominant themes, biggest deleter (cleanup credit).

## Gotchas

- Bots: `author.is_bot` only catches app accounts (`app/dependabot`); release bots like `wpmobilebot` are regular users — flag by login.
- Release-branch merge PRs inflate line counts; call them out, don't count as feature work.
- `--limit` defaults to 30 — always pass `--limit 200` (raise if hit).
- `.author.name` can be empty; fall back to login.
