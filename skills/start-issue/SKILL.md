---
name: start-issue
description: Start work on a Linear issue end-to-end — create a worktree, fetch issue context from Linear, implement the fix, then commit, push, and open a draft PR. Use when the user says "start issue", "work on STU-1234", "create a worktree and fix <Linear link>", "start a worktree for this ticket", or gives a Linear URL/issue id and wants the whole branch→PR flow.
user-invocable: true
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "Task", "AskUserQuestion"]
---

# Start Issue

One command from a Linear link (or branch name) to a draft PR. Fetches issue
context, spins up an isolated worktree, does the work, verifies, and ships a
draft PR — filling in everything it can from MCP so the user supplies only the
link or branch.

## Inputs

The user gives **one** of:
- A Linear URL — `https://linear.app/a8c/issue/STU-1835/...`
- A bare issue id — `STU-1835`
- A branch name that embeds the id — `stu-1835-fix-dark-mode-...`

Plus optional free-text scope/constraints ("focus on Studio Code tab UI").
**Front-load anything that scopes the work into the first prompt** — it becomes
the acceptance bar below.

If no id and no Linear link can be derived, ask for one (or proceed worktree-only
if the user explicitly wants no ticket).

## Workflow

### 1. Resolve the issue
- Extract the issue id from whatever was given (URL path, bare id, or branch
  prefix like `stu-1835-`).
- Fetch it: `mcp__claude_ai_Linear__get_issue` with the id. Fallback if that
  MCP is absent: context-a8c → `load-provider linear` then `execute-tool` to get
  the issue.
- Keep: **title**, **description** (the bug/feature spec + screenshots),
  **gitBranchName**, **url**, **assignee**.

### 2. Decide the branch name
- If the user supplied a branch name, use it verbatim.
- Else use the issue's `gitBranchName` (Linear's canonical
  `stu-1835-<slug>`). Branches come off `trunk`.

### 3. State the acceptance bar (before touching code)
Restate in one or two lines: "Done means: <fix> + lint + typecheck + relevant
tests pass + (UI? both light & dark verified)." For anything over one file or
~15 min, plan first (plan mode / `writing-plans`). Use the Linear description as
the source of truth for what "fixed" looks like.

### 4. Create the worktree
Invoke the **`worktree`** skill with the branch name (it fetches `origin/trunk`,
creates `~/worktrees.nosync/<branch>`, copies `node_modules`). The
node_modules copy is large — run it in the background and proceed while it
finishes. All file edits happen **inside the worktree**, never the source
checkout.

### 5. Implement
- Read the issue description carefully; locate the real code (grep for the
  user-visible string from the ticket — e.g. a modal title — to find the
  component fast).
- Make the smallest change that satisfies the ticket. Mirror existing patterns
  in the repo.
- If the same bug obviously affects a sibling (e.g. two dialogs sharing one
  broken token), fix both — but say so.

### 6. Verify (before claiming done)
Per the repo's AGENTS.md / CLAUDE.md. For Studio:
- `npx eslint --fix <changed files>`
- `npm run typecheck` — if it surfaces **pre-existing** errors in an app you
  didn't touch (e.g. `apps/ui` missing `@wordpress/core-data`), confirm they
  exist on trunk too and typecheck the touched app in isolation
  (`cd apps/<app> && npx tsc -p tsconfig.json --noEmit`). Don't let unrelated
  red block you, but don't hand-wave real errors either.
- `npx vitest run <touched dir>` for the relevant tests.
- **UI/CSS change → verify in BOTH light and dark.** If you can't drive the app,
  say so plainly and leave the visual checkbox unchecked on the PR.

### 7. Commit, push, draft PR
- **Commit:** conventional-commit prefix is required (`fix:`, `feat:`, `chore:`,
  `refactor:`, …). The Studio commit hook also rejects any `git commit` whose
  command contains `-f`, `-F`, or `--file` (matched as "force") — so **don't use
  a message file or `-F`**, and avoid a `-f` substring in the message. Use a
  single-line `-m "fix: …"`. Put the full rationale in the PR body, not a long
  commit body.
- **Push:** `git push -u origin <branch>`.
- **Draft PR** against `trunk`, `--draft`:
  - Fill the repo's `.github/PULL_REQUEST_TEMPLATE.md` sections.
  - **Related Issues** → link the Linear URL ("Fixes STU-1835").
  - **Proposed Changes** → the intent + user-visible impact (the "why"), not a
    file list.
  - **Testing Instructions** → concrete repro steps from the ticket.
  - Assign per project convention (e.g. `--assignee @me`, or `--assignee <your-handle>`).
  - Do **not** credit Claude/AI as the PR author (Studio convention); the
    template's "How AI was used" section is fine to fill.
  - PR body is fine to pass via `--body-file` (the `-f` hook only guards
    `git commit`, not `gh`).
- Large/vibe-coded features: open as draft + `Proof of Concept` label, and
  consider a companion issue (per AGENTS.md).

### 8. Report
Give the user: PR URL, what changed + why, verification results (honestly —
including anything unverified), and the worktree path.

## Gotchas (learned)
- Worktree teardown goes through `git worktree remove` / `prune`, never
  `rm -rf` — see the `worktree` skill.
- `--color-frame-*` vs `--wpds-color-*` token rules differ per app in Studio —
  read AGENTS.md before picking dark-mode color tokens.
- Linear `get_issue` returns `gitBranchName` — prefer it over inventing a slug.
