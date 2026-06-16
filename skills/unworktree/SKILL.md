---
name: unworktree
description: Use when the user wants to undo, absorb, collapse, or reverse a git worktree — "undo worktree", "absorb worktree", "move worktree branch back to main repo", "remove worktree and checkout in main", "get rid of this worktree", or finish work in a ~/worktrees.nosync worktree and continue it in the main studio checkout.
---

# Unworktree

## Overview

Absorbs a git worktree back into the main repo: takes the branch checked out in a worktree, checks it out in the **main repo**, and deletes the worktree folder. The reverse of the `worktree` skill.

**Main repo:** `$MAIN_REPO` (set to your main checkout — the repo worktrees branch off)
**Worktrees live under:** `~/worktrees.nosync/`

**Core principle:** Removing a worktree is non-destructive for committed work — commits live in the shared `.git`, so checking the branch out in the main repo recovers everything. The only thing at risk is **uncommitted** changes, which is why the dirty check is a hard gate.

## When to Use

- User says "undo / absorb / collapse / reverse / remove this worktree" and wants the branch back in the main checkout.
- User is done in a `~/worktrees.nosync/<name>` directory and wants to continue the branch in the main repo.

**Do NOT use** to merely delete a throwaway worktree the user wants discarded (no branch to keep) — that's a plain `git worktree remove`.

## Procedure (ORDER MATTERS)

Run these steps in order. Never use `--force`. Never `git add`, commit, or push.

### 1. Resolve the worktree path and branch name

```bash
git -C $MAIN_REPO worktree list --porcelain
```

- Argument is a **branch name** → find the matching `worktree` line in the porcelain output.
- Argument is a **path** → find the matching `branch` line.
- **No argument** → check the current directory (`git rev-parse --show-toplevel`). If it sits under `~/worktrees.nosync/`, that's the target worktree; read its branch from the porcelain list.

You must end this step with both: `WORKTREE_PATH` and `BRANCH`. If you cannot resolve both unambiguously, STOP and ask.

### 2. Safety gate — abort on uncommitted changes

```bash
git -C <WORKTREE_PATH> status --porcelain
```

- **Non-empty output → STOP.** Report the dirty/untracked files to the user and do nothing else. Do **not** offer `--force`. The user must commit, stash, or discard first.
- Also check for commits not yet on the remote (warn, do not abort):

```bash
git -C <WORKTREE_PATH> log --oneline @{upstream}..HEAD 2>/dev/null
```

If this lists commits (or there is no upstream), tell the user the branch has local-only commits. Removing the worktree is still safe (the commits stay in the shared repo and come back at step 4), but they should know nothing is being pushed.

### 3. Remove the worktree (frees the branch + deletes the folder)

```bash
git -C $MAIN_REPO worktree remove <WORKTREE_PATH>
```

This MUST happen **before** step 4 — git refuses to check out a branch in the main repo while it is checked out in a live worktree. Removing the worktree both releases the branch lock and deletes the folder.

### 4. Check out the branch in the main repo

```bash
git -C $MAIN_REPO checkout <BRANCH>
```

### 5. Confirm and report

```bash
git -C $MAIN_REPO branch --show-current
test -d <WORKTREE_PATH> && echo "STILL EXISTS" || echo "removed"
```

Report: main repo is now on `<BRANCH>`, worktree folder is gone, and surface any local-only-commits warning from step 2.

## Common Mistakes

- **Checking out before removing the worktree** → `fatal: '<branch>' is already checked out at ...`. Always remove first (step 3 before step 4).
- **Using `--force` to get past a dirty worktree** → silently discards the user's uncommitted work. Forbidden. The dirty check is a hard stop.
- **Running `worktree remove` from inside the worktree directory** → can fail or leave cwd invalid. Run with `git -C <main-repo>` and don't have your shell sitting inside the folder being deleted.
