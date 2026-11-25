# pr-desk prompt templates

Fill `<…>` from the gather JSON row. Every template ends with the same hard rules:
never post to GitHub (no reviews, comments, replies, approvals, reactions), never push,
never mark notifications read.

## 1. Review agent (INCOMING, `needs_review_agent: true`)

`subagent_type: general-purpose`, `name: review-<number>`.

> Follow ~/.claude/skills/quick-pr-review/SKILL.md to review PR #<number> in <repo> (<url>), "<title>" by <author>. Remote-only review unless your
> complexity gate says deep mode. Write the markdown review to ~/claude.nosync/reviews/ dated
> today. Do NOT post anything to GitHub. Do not run layout.sh. Return: verdict (approve / needs
> changes / needs discussion), merge confidence 0-100, top 3 findings with file:line, and the
> absolute paths of the review .md and walkthrough .html.

Re-review (`freshness: stale` or `rereview: true`), append:

> This is a re-review. Read the prior review first: ~/claude.nosync/reviews/<review_md>.
> My last review was <my_last_review>; the last commit is <last_commit>. Focus on the delta
> since then (`gh api repos/<repo>/compare/<old_sha>...<head>` if you can find the old sha,
> otherwise commits after that date) and say which prior findings were addressed.

Add PR-specific context when known: security fix → "verify the fix is real, not
scanner-appeasement"; dead-code removal → "check the default branch hasn't grown importers of the deleted
symbols"; dependency bump → "check the repo's pinning rules and the changelog for breaking changes".

## 2. Feedback triage agent (MINE, `needs_triage: true`)

`subagent_type: general-purpose`, `name: triage-<number>`. Read-only.

> Triage reviewer feedback on my PR <repo>#<number> (<url>), "<title>". I am <me>.
> New since I last looked (<since or "first run">): <new_activity as "kind by who at">.
> Flags: <flags>.
>
> 1. Fetch, read-only: `gh pr view <number> -R <repo> --json body,reviews,comments,headRefOid`,
>    `gh pr diff <number> -R <repo>`, and the review threads:
>    `gh api graphql -F owner=<owner> -F repo=<name> -F pr=<number> -f query='query($owner:String!,$repo:String!,$pr:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$pr){reviewThreads(first:100){nodes{id isResolved isOutdated path line comments(first:50){nodes{url author{login} body createdAt diffHunk}}}}}}}'`.
>    For context outside the diff: `gh api 'repos/<repo>/contents/<path>?ref=<headRefOid>' --jq .content | base64 -d`.
> 2. Consider every unresolved thread plus every review body and PR comment from someone other
>    than me that I have not answered. Skip bots unless they flag a real bug.
> 3. Classify each: `valid_fix` | `question` | `disagree` | `nit` | `out_of_scope`.
> 4. Give options and recommend one:
>    A `fix`: concrete change sketch (file, what changes, ≤15 lines of code if useful);
>    B `reply`: a short, human, friendly reply draft in my voice (no "Great catch!" filler);
>    C `push_back`: a reply draft with the reasoning;
>    D `defer`: follow-up issue title plus a one-line reply saying it is tracked.
> 5. Reply drafts on public repos must contain no internal URLs; check them against
>    <internal_hosts_re from config.json>. Link GitHub items as org/repo#123.
>
> NEVER post, reply, resolve threads, push or commit. Return ONLY this JSON:
> ```json
> {"pr": "<repo>#<number>", "summary": "≤25 words: what reviewers want",
>  "blocking": true,
>  "items": [{"id": "t1", "url": "<comment url>", "who": "login", "path": "file:line",
>             "quote": "≤20 words", "class": "valid_fix",
>             "options": {"fix": "...", "reply": "...", "push_back": "...", "defer": "..."},
>             "recommend": "fix", "why": "≤15 words", "effort": "xs|s|m|l"}]}
> ```

## 3. Fix agent (after the user picks "apply fix on #N")

Writes code, so it runs isolated. `Agent isolation: "worktree"` only isolates the session's
current repo; pr-desk sessions usually start elsewhere. So:

- Session cwd is a clone of `<repo>` → `isolation: "worktree"`, and the agent first runs
  `git fetch origin <head_ref> && git checkout -B pr-desk-<number> origin/<head_ref>`.
- Otherwise → `subagent_type: general-purpose` with the worktree steps below.

> Apply these fixes to my PR <repo>#<number> (<url>), branch <head_ref>: <chosen items with
> their fix sketches and comment urls>.
>
> Setup: `CLONE=$(~/.claude/skills/pr-desk/scripts/find-clone.sh <repo>)` (if it prints nothing:
> `gh repo clone <repo> ~/worktrees.nosync/pr-desk-<name>-<number> -- --filter=blob:none`).
> `git -C "$CLONE" fetch origin <head_ref>`. If `git -C "$CLONE" worktree list` shows <head_ref>
> already checked out in a clean worktree, work there; otherwise
> `git -C "$CLONE" worktree add --detach ~/worktrees.nosync/pr-desk-<name>-<number> origin/<head_ref>`.
> Copy `node_modules` from the clone if the repo has one and the worktree lacks it.
>
> Make the smallest change that resolves each item and follows the repo's conventions
> (read its AGENTS.md/CLAUDE.md). Run the relevant linter and the tests closest to the change.
> Leave everything UNCOMMITTED: no `git add`, no commit, no push. Save `git diff` to
> ~/claude.nosync/diffs/<YYYY-MM-DD>-<name>-<number>-pr-desk.diff.
> Return: worktree path, diff path, the full diff, lint/test commands and results, and for each
> item one line on how it was resolved (or why not).

## 4. Hourly tick prompt (CronCreate, verbatim)

```
pr-desk tick. Follow ~/.claude/skills/pr-desk/SKILL.md in tick mode: run `bash ~/.claude/skills/pr-desk/scripts/gather.sh --summary`, recheck GHE if configured (say "GHE: no connection" if it fails), then act only on rows whose delta is not "unchanged", on GONE rows and on other notifications. Fan out review/triage agents only for those (≤6 per message). If nothing changed, answer exactly "pr-desk: nothing new". Otherwise post deltas only as compact linked tables, call PushNotification with a one-line summary, append the tick to today's report file, offer actions with AskUserQuestion, then run mark-seen.sh. Never post to GitHub, never push, never mark notifications read.
```

## 5. GitHub Enterprise (optional)

1. Skip when `enterprise_repos` is empty. Use an MCP provider or `GH_HOST=<enterprise_host> gh`.
2. For each repo in `enterprise_repos` (identity config), with owner `enterprise_owner`, call
   `search-pull-requests` with `owner` + `repo` set (unscoped queries return 0 whatever exists, so
   never read an unscoped 0 as "nothing waiting"):
   - INCOMING: `is:open is:pr review-requested:<gh_user_enterprise>`
   - MINE: `is:open is:pr author:<gh_user_enterprise>`
3. For MINE hits, `pull-request` with `get_reviews`, `get_comments` and `get_status` to fill flags.
   Review MD names use the repo short name, so the same freshness rule applies (`-<repo>-<n>-`).
4. Keys are `ghe:<owner>/<repo>#<n>`; compare against `state.json` `.prs[key]` for the delta, and
   write rows (`key, kind, title, url, head, last_activity, ci, decision, mergeable`) to
   `~/claude.nosync/pr-desk/ghe.json` for `mark-seen.sh`.
5. Any failure (tool missing, provider load error, timeout, single repo 404) → a row
   `⚠️ No connection | GHE <repo> | <error>` at the top of the affected table, the same warning as
   the FIRST line of the reply, and `mark-seen.sh` without the GHE file (old GHE state is kept).

## 6. Report skeleton

```markdown
# PR desk · <YYYY-MM-DD HH:MM> · <since: first run | last run time>
<⚠️ source warnings first, if any>

## Incoming: review requested (<n>)
| PR | Title | Author | Age | Size | CI | Status | Confidence | Action |
|---|---|---|---:|---|---|---|---:|---|

## Mine: feedback & state (<n>)
| PR | Title | Age · idle | Review | CI · merge | Feedback | Recommended |
|---|---|---|---|---|---|---|

### Triage: <repo>#<n>
| # | Who | Where | Class | Recommend | Draft / sketch |
|---|---|---|---|---|---|

## Other notifications (<n>)            (only if any)
## Closed or merged since last run      (only if any)
## Week (<since> → today)               (Monday or `week`)
```

- PR cells are links: `[#123](https://github.com/owner/repo/pull/123)`, with
  `org/repo` prefixed when the table mixes repos. Linear IDs found in titles/branches are links too.
- Status (incoming): `new` / `re-review: commit after review` / `current (MD <date>)` /
  `draft, skipped` / `team: <team>` when the request is via a team, not direct.
- Feedback (mine): `changes requested by X`, `N unresolved`, `new: comment by Y`, `—`.
- Recommended (mine): `merge` (approved_unmerged, CI green), `rebase` (conflicts),
  `fix CI: <job>`, `triage below`, `nudge <reviewer>` (week), `wait`.
- Bots (renovate/dependabot) in incoming: one grouped line, not one row each.
