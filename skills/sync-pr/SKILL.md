---
name: sync-pr
description: Use when the user wants one of their open PRs brought up to date with trunk and pushed — "pull origin trunk, resolve conflicts, commit and push", "sync this PR", "update #123 with trunk", "I merged #A, update #B", "is the PR description still accurate?", or /sync-pr [PR url|number]. Merges trunk into the PR branch (never rebases or force-pushes), resolves conflicts, checks the touched files, pushes, refreshes the PR description when it drifted, and ends with an explicit "Pushed: yes/no".
---

# Sync PR

Bring one PR branch up to date with `trunk`, push it, and keep its description true. Works in any repo whose default branch is `trunk`; substitute `main` otherwise.

**Done means:** branch contains latest `origin/trunk`, conflicts resolved, touched files lint-clean, pushed with a plain `git push`, description matches the diff, and the report's first line says whether it pushed.

## 1. Resolve the PR and its checkout

- Argument: PR URL or number. None → the PR of the current branch (`gh pr view --json number`). Several PRs → do them one at a time, parent before child.
- `gh pr view <pr> --json number,url,state,headRefName,baseRefName,body,isCrossRepository`. Stop if it is merged, closed, or from a fork.
- Find where the branch is checked out: `git worktree list --porcelain` (main checkout and `~/worktrees.nosync/*`, `~/.t3/worktrees/*`). Not checked out anywhere → ask whether to create a worktree with the `worktree` skill; never switch the branch of a checkout that is on another branch.
- `git status --porcelain` in that checkout. Uncommitted changes → stop and ask: commit them first, or leave them out. Never `git stash` (the stash is shared across worktrees).
- `git config user.email` must be the address this remote expects (work vs. personal); fix the `includeIf` pattern in `~/.gitconfig` if not, before any commit.

## 2. Stacked PR whose parent merged

When `baseRefName` isn't `trunk` and the base branch's PR is merged (or the branch is gone): retarget with `gh pr edit <pr> --base trunk` and say so in the report. When merging trunk in step 3, the parent's own commits arrive squashed; for conflicts in code that came from the parent (`gh pr diff <parent>`), take trunk's side — it is the merged version of the same change.

## 3. Merge

```bash
git fetch origin trunk "$HEAD_BRANCH"
git merge --ff-only @{u} || git merge @{u}   # the remote branch may have moved (other pushes, suggested changes)
git merge origin/trunk                        # never rebase: rebasing forces a force-push
```

Conflicts: read both sides and resolve each by intent — keep this PR's change on top of trunk's latest code, not one side wholesale. Lockfiles (`yarn.lock`): take trunk's, then `yarn install` and commit the result. If a conflict changes behaviour on both sides and the right merge is unclear, stop and show the hunk instead of guessing.

Commit with git's default merge message.

## 4. Check what changed

Node: the zsh `.nvmrc` hook fails on `cd` (exit 3, which breaks `&&` chains), so use absolute paths and `git -C <checkout>`, and run node tools with `env PATH=$HOME/.nvm/versions/node/v$(cat <checkout>/.nvmrc)/bin:$PATH bash -c "cd <checkout> && …"`.

- Lint the PR's files: `git diff --name-only --diff-filter=d origin/trunk...HEAD`, then the repo's linter on those (e.g. `yarn eslint <files>`).
- If conflicts were resolved in code: run the unit tests next to those files, and the type-check for that area in a background subagent that reports only errors.
- A failure caused by the merge → fix it and commit. A failure that is already on trunk → report it, don't fix it here.

## 5. Push

`git push`. Never `--force` / `--force-with-lease`. Rejected → fetch, merge `@{u}` again, re-check, push once more; rejected again → stop and report.

## 6. Description

Compare the body with `git diff origin/trunk...HEAD --stat`, the commit list and what the code now does. If it is still accurate, leave it. If it drifted:

- Rewrite only the parts that are wrong; keep structure, headings, before/after tables and images exactly as they are. Concise, easy to understand.
- Follow the repo's own PR template or PR-writing skill when it has one.
- Public repo: grep the new body for your internal hosts (company intranet, Slack, Figma, support desk: `$INTERNAL_HOSTS_RE`) and fix every hit.
- Show the diff of old → new body, then apply with `gh pr edit <pr> --body-file <file>`. If the edit would remove content (a section, a screenshot, testing steps), ask before applying.

## 7. Report

```
Pushed: yes — <short sha> to <branch>        (or: Pushed: no — <reason>)
PR: <url>
Merged trunk: <n> commits; conflicts: <files, or none>
Checks: <what ran → result>; not run: <what and why>
Base: retargeted to trunk / unchanged
Description: updated (<what changed>) / unchanged
```
