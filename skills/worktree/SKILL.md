---
name: worktree
description: Create a new git worktree from origin/trunk in ~/worktrees.nosync and copy node_modules. Use when the user wants to "create a worktree", "new worktree", "start a worktree branch", or needs an isolated working directory for a feature branch.
user-invocable: true
---

# Worktree

Create a new git worktree based on origin/trunk in ~/worktrees.nosync, with node_modules copied from the current directory for fast setup.

## Workflow

1. Gather information:
   - Ask for the branch name if not provided
   - Verify current directory has a git repo
   - Check if node_modules exists in current directory

2. Fetch latest from origin:
   ```bash
   git fetch origin trunk
   ```

3. Create the worktree directory if needed:
   ```bash
   mkdir -p ~/worktrees.nosync
   ```

4. Append a timestamp suffix to the branch name to keep it unique, then create the worktree:
   ```bash
   SUFFIX=$(date +%m%d%H)   # monthdayhour, e.g. 072415
   git worktree add ~/worktrees.nosync/<branch-name>-$SUFFIX -b <branch-name>-$SUFFIX origin/trunk
   ```
   The suffix applies to both the branch and the worktree directory (they share the name). If the user explicitly asks for an exact branch name with no suffix, skip it.

5. Copy node_modules if it exists in the source directory. Use `cp -c` — on APFS it clones the files instead of copying bytes, so a multi-GB `node_modules` lands instantly and costs no extra disk until something writes to it. Fall back to a plain copy on non-APFS volumes:
   ```bash
   SRC=$(git rev-parse --show-toplevel); WT=~/worktrees.nosync/<branch-name>-$SUFFIX
   cd "$SRC" && find . -maxdepth 4 -name node_modules -type d -not -path "*/node_modules/*" | while read -r nm; do
     mkdir -p "$WT/$(dirname "$nm")"
     cp -Rc "$SRC/$nm" "$WT/$nm" 2>/dev/null || cp -R "$SRC/$nm" "$WT/$nm"
   done
   ```
   The `find` loop also picks up per-workspace `node_modules` (monorepos), not just the root one — miss those and workspace builds fail in the worktree.

6. Report success with the path to the new worktree:
   ```
   Worktree created at: ~/worktrees.nosync/<branch-name>-<suffix>
   ```

## Important Rules

- Always fetch origin/trunk first to ensure the worktree is based on latest
- Branch name should be provided by the user or derived from their task
- If node_modules doesn't exist, skip the copy step and mention npm install is needed
- Never modify the source repository's working directory
- If the branch already exists, ask the user how to proceed

## Branch Naming Suggestions

If the user doesn't specify a branch name, suggest a format based on context:
- Feature work: `feature/<short-description>`
- Bug fix: `fix/<issue-id>` or `fix/<short-description>`
- Linear tickets: `stu-<ticket-number>-<short-description>` (for Studio)

## Teardown

**Always remove worktrees through git, never `rm -rf` the directory.** A manual `rm` leaves git's admin entry (`<repo>/.git/worktrees/<name>`) behind, or deleting the admin entry leaves the on-disk dir behind — either way you get orphans that `git worktree prune` cannot detect, silently wasting disk (build dirs alone can be multiple GB per orphan).

Correct teardown:
```bash
git worktree remove ~/worktrees.nosync/<branch-name>   # refuses if uncommitted work — that's the safety net
git worktree prune                                     # sweep any stale admin entries
```

## Doctor — find orphaned worktree dirs

When the user asks to "check worktrees", "clean up worktrees", or "worktree doctor", run this from inside the repo to list on-disk dirs that git no longer tracks:
```bash
comm -23 \
  <(ls -d ~/worktrees.nosync/*/ 2>/dev/null | xargs -n1 basename | sort) \
  <(git worktree list --porcelain | sed -n 's#.*worktrees.nosync/##p' | sort)
```
Each line printed is an orphan (dir exists, not registered). Before deleting any orphan:
1. Check its `.git` pointer: `cat ~/worktrees.nosync/<name>/.git` — and whether the admin dir it names still exists.
2. If the admin dir is GONE, git history is unrecoverable — inspect the working tree for unique/uncommitted work before removing. Surface findings to the user; do not blind-delete.
3. Build artifacts (`out`, `dist`, `node_modules`, `cli`, `bin`) are regenerable — safe to strip first to reclaim the bulk of the space cheaply.
4. Remove confirmed-dead orphans with `rm -rf`, then `git worktree prune`.
