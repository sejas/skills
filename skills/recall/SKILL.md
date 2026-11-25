---
name: recall
description: Use after a fresh session, /clear or compaction to rebuild context for a piece of work — "recall", "where was I", "catch me up on <scope>", "rebuild context for <branch/PRs>", or /recall <scope | branch | PR list>. Reads the scope's plan file, worktree git state, PR state and recent session transcripts, and prints a ≤15-line recap with the next action. Read-only.
---

# Recall

Rebuild working context for one scope, cheaply. **Read-only**: never edit, commit, push, comment or mark anything.

## Input

A scope name (e.g. `checkout-banner`), a branch, and/or PR numbers or URLs. Ask once if nothing is given and the current branch doesn't suggest one. Default repo: the current checkout's (`gh repo view --json nameWithOwner`).

## Steps (run independent reads in parallel)

1. **State file:** read `~/claude.nosync/plans/<scope>.md` if present; else `ls -t ~/claude.nosync/plans | grep -i <scope>` and read the best match. Note goal, done-means and any open checklist items.
2. **Worktrees:** `git worktree list` in the repo, keep those whose path or branch matches the scope (`~/worktrees.nosync/…`). For each: `git -C <wt> status -sb` and `git -C <wt> log --oneline -5`. Flag uncommitted changes and unpushed commits.
3. **PRs:** for each PR (given, or `gh pr list --author @me --search <scope>` / `gh pr list --head <branch>`):
   - `gh pr view <N> --repo <owner/repo> --json number,title,state,isDraft,reviewDecision,mergeable,url`
   - `gh pr checks <N> --repo <owner/repo>` → pass / fail / pending (name the failing check).
   - Unresolved threads: `gh api graphql` on `reviewThreads(first:50){nodes{isResolved path comments(last:1){nodes{author{login} body}}}}`; count unresolved and keep one line for each.
4. **Transcripts:** `grep -l -i <scope> ~/.claude/projects/*/*.jsonl` and keep the 2–3 most recently modified. Read only the **tail** (`tail -c 20000`), pulling the last user requests, decisions and any stated next step. Never read a whole transcript.

## Output (≤15 lines)

```
**<scope>** — <goal, one line>
| PR | State | Checks | Unresolved | Note |
|---|---|---|---|---|
| [#<N>](https://github.com/<owner/repo>/pull/<N>) | draft / open / approved / merged | ✅ / ❌ <check> / ⏳ | <n> | <one line> |
Worktrees: <path> — <clean | n uncommitted | n unpushed>
Last session: <what was being done, one line>
**Next:** <the single next action>
```

- Every PR number is a markdown link; use the PR's own repo, not the default.
- Linear keys are links too: `[ABC-123](https://linear.app/<workspace>/issue/ABC-123)`.
- Say what couldn't be read (no plan file, `gh` auth error) in one line instead of guessing.
- Stop after the recap; don't start the next action until asked.
