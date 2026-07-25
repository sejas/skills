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

4. Create the worktree with new branch:
   ```bash
   git worktree add ~/worktrees.nosync/<branch-name> -b <branch-name> origin/trunk
   ```

5. Copy node_modules if it exists in the source directory. Use `cp -c` — on APFS it clones the files instead of copying bytes, so a multi-GB `node_modules` lands instantly and costs no extra disk until something writes to it. Fall back to a plain copy on non-APFS volumes:
   ```bash
   SRC=$(git rev-parse --show-toplevel); WT=~/worktrees.nosync/<branch-name>
   cd "$SRC" && find . -maxdepth 4 -name node_modules -type d -not -path "*/node_modules/*" | while read -r nm; do
     mkdir -p "$WT/$(dirname "$nm")"
     cp -Rc "$SRC/$nm" "$WT/$nm" 2>/dev/null || cp -R "$SRC/$nm" "$WT/$nm"
   done
   ```
   The `find` loop also picks up per-workspace `node_modules` (monorepos), not just the root one — miss those and workspace builds fail in the worktree.

6. Report success with the path to the new worktree:
   ```
   Worktree created at: ~/worktrees.nosync/<branch-name>
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

## Cleanup Reminder

After completing work, remind the user they can remove the worktree with:
```bash
git worktree remove ~/worktrees.nosync/<branch-name>
```
