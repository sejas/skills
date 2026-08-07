---
name: quick-pr-review
description: >-
  This skill should be used when the user asks to "quick review a PR",
  "fast pr review", "review this PR without checkout", "review PR diff",
  "review PR #123", or provides a GitHub PR URL for lightweight review
  without checking out the branch. Reads PR description, comments, and
  review threads, fetches Linear issue context, reviews the diff,
  and outputs a markdown review file opened in Obsidian. Complex PRs
  (>400 changed lines or >10 files) also get an isolated checkout
  with lint + tests run before the verdict.
user-invocable: true
allowed-tools: ["Bash", "Read", "Write", "SlashCommand",
  "mcp__plugin_context-a8c_context-a8c__context-a8c-load-provider",
  "mcp__plugin_context-a8c_context-a8c__context-a8c-execute-tool"]
---

# Quick PR Review

Lightweight code review. Small PRs: remote-only — fetch PR data via `gh`, review the diff, write markdown, open in Obsidian. Complex PRs (see Complexity Gate): additionally checkout the PR into an isolated worktree/clone, run lint + tests, and fold results into the review.

## Configuration

- **Output folder:** `~/claude.nosync/reviews/`
- **Filename:** see Filename Convention below.

## Workflow

### Step 1: Parse PR Input & Parallel Fetch

The user provides either a GitHub URL or a PR number.

**URL:** parse with `github\.com/([^/]+)/([^/]+)/pull/(\d+)` and ignore everything after the number — handles `/files`, `/commits`, `/checks` suffixes, `#discussion_r…` anchors, and query strings.

**If just a number:** detect repo: `gh repo view --json nameWithOwner --jq '.nameWithOwner'`. If that fails (not in a git repo, no default repo), try `git remote get-url origin`; if that also fails, ask the user for `owner/repo` — never guess.

Once you have `OWNER/REPO` and `PR_NUMBER`, launch **all of these in parallel** (single message, multiple tool calls):

1. **Bash:** `gh pr view <PR_NUMBER> --repo <OWNER/REPO> --json title,body,author,state,isDraft,baseRefName,headRefName,headRefOid,reviewDecision,url,files,additions,deletions,comments,reviews`
2. **Bash:** `gh pr diff <PR_NUMBER> --repo <OWNER/REPO>`
3. **Bash** (review threads + resolution state — not available via `gh pr view`):
   ```bash
   gh api graphql -F owner='<OWNER>' -F repo='<REPO>' -F pr=<PR_NUMBER> -f query='
     query($owner:String!,$repo:String!,$pr:Int!){
       repository(owner:$owner,name:$repo){ pullRequest(number:$pr){
         reviewThreads(first:100){ nodes{
           isResolved isOutdated path line startLine diffSide
           comments(first:50){ nodes{ author{login} body diffHunk originalLine } }
         }}
       }}
     }'
   ```
4. **Bash:** `mkdir -p ~/claude.nosync/reviews`

Check each result before proceeding. If `gh pr view` or `gh pr diff` errored (404 / auth / no access), stop and report the failure — do not write a review from partial data. If `gh pr diff` fails with a "diff too large" error, fall back to per-file patches: `gh api repos/<OWNER/REPO>/pulls/<PR_NUMBER>/files --paginate --jq '.[] | {filename, patch}'` (patch is omitted for huge/binary files — list those as not reviewed).

### Step 1b: Rename Session

Once PR metadata is fetched, rename the current Claude Code session so it's identifiable in the session list. Invoke the built-in slash command via the SlashCommand tool:

```
/rename PR #<PR_NUMBER>: <title>
```

Truncate the title to keep the whole name under ~60 chars. Best-effort: if the SlashCommand tool is unavailable or the command fails, skip silently and continue — never block the review on this.

### Step 1c: Complexity Gate

From the `gh pr view` JSON, compute `additions + deletions` and file count.

**Deep mode** when `additions + deletions > 400` OR `files > 10`. Otherwise **remote-only mode** — skip Step 2b entirely.

State the chosen mode in the review's `**Verified:**` header line.

### Step 2: Extract Linear ID & Fetch Issue

From PR metadata (now available), extract a Linear ID matching `[A-Z]{2,10}-\d+` from:
1. The PR body
2. The head branch name

Ignore false positives like `UTF-8`, `SHA-256`, `ISO-8601`; prefer the ID from the branch name when sources disagree.

If found, fetch the issue using the **context-a8c Linear provider**:
1. Load provider: `mcp__plugin_context-a8c_context-a8c__context-a8c-load-provider` with `provider: "linear"`
2. From the loaded tool list, pick the tool that fetches a single issue by identifier and call it via `mcp__plugin_context-a8c_context-a8c__context-a8c-execute-tool`, passing the extracted ID.
Store: `LINEAR_TITLE`, `LINEAR_URL`, `LINEAR_DESCRIPTION`.

If no Linear ID found, or the provider fails / issue not found, proceed without it and omit the **Linear:** line.

### Step 2b: Deep Mode — Checkout, Lint, Tests (complex PRs only)

`REVIEW_DIR=~/worktrees.nosync/pr-review-<repo>-<PR_NUMBER>`. If it already exists, remove it first (`git worktree remove --force` or `rm -rf`).

**Case A — cwd is inside a local clone of `OWNER/REPO`** (check `git remote get-url origin`):
```bash
git fetch origin pull/<PR_NUMBER>/head
git worktree add "$REVIEW_DIR" FETCH_HEAD --detach
cp -R <local-clone>/node_modules "$REVIEW_DIR/node_modules"   # only if it exists
```

**Case B — no local clone:**
```bash
gh repo clone <OWNER/REPO> "$REVIEW_DIR" -- --filter=blob:none
cd "$REVIEW_DIR" && gh pr checkout <PR_NUMBER>
npm ci || npm install   # best-effort; on failure skip lint/tests and note it
```

Then, from `$REVIEW_DIR`:

1. **Lint:** if `package.json` has a `lint` script, run `npm run lint`. Capture pass/fail + first errors.
2. **Tests:** prefer tests scoped to changed files (`npx jest --findRelatedTests <files>` / `npx vitest related <files>`) when the runner supports it; otherwise run the `test` script with a 10-minute timeout. On timeout, report partial results — never hang the review.
3. **Context reads:** use the checkout to read code *around* the diff before rating findings — verify a suspected bug against the full file, not just the hunk. Deep-mode findings should rarely be Low confidence for "surrounding code not visible".
4. **Cleanup (always, even if lint/tests fail):** `git worktree remove "$REVIEW_DIR" --force` (Case A) or `rm -rf "$REVIEW_DIR"` (Case B).

**Never** commit, push, or modify code in the checkout. Read + run only.

If checkout itself fails (no access, disk, etc.), fall back to remote-only mode and say so in the review's `## Notes` section.

### Step 3: Analyze & Generate Review

Review the diff focusing on **high-impact issues only**:

- **Bugs:** Logic errors, off-by-one, null/undefined access, race conditions
- **Security:** Injection, auth bypass, data exposure, unsafe input handling, exposed secrets/API keys
- **Data integrity:** Data loss risks, incorrect state mutations, missing validation
- **Error handling:** Swallowed errors, missing failure paths, unhandled rejections
- **Test coverage:** New logic with no test guarding it (flag only when the gap is significant)
- **Readability:** Confusing logic, misleading names, duplicated code, overly complex flow (only if significant)

**Do NOT flag:** minor style, trivial naming, missing comments on clear code, linter-catchable issues.

**Assess the discussion** (PR comments, reviews, review threads):
- Summarize substantive reviewer concerns and whether the author addressed them — use `isResolved` / `isOutdated` from the reviewThreads fetch, don't guess.
- Cross-check reviewer-raised issues against the current diff — flag any that remain unfixed.
- Note approvals / change-requests already on record (`reviewDecision`).
- Skip bot noise (CI status comments, dependabot chatter) unless it reports a real failure.

Compose the review markdown:

````markdown
# PR Review: [#<number> - <title>](<PR_URL>)

**Author:** @<author> | **Branch:** <head> -> <base> | **Date:** <YYYY-MM-DD> | **Linear:** [<LINEAR_ID>](<LINEAR_URL>)
**Verdict:** **<Approve | Comment | Request Changes>** — <1-2 sentences: what the PR does and why this verdict.>
**Verified:** <deep mode: "lint pass, tests 214/214 pass" or the failures | remote-only: "remote-only (small PR), lint/tests not run"> | **Size:** <fileCount> files +<additions> -<deletions>

## Suggested comments

### Overall (general PR comment — post first)

<Thank the author for the specific feature/fix by name (not a generic "thanks for the PR"), include one genuine positive about the code, then 1-2 sentences on the review outcome.>

### 🔴 `path/to/file.ts:42` — <short finding title>

**Confidence:** <High | Medium | Low> — <1-2 sentences justifying the rating: what makes it strong (verified against full diff context, clear logic error) or weak (surrounding code not visible in diff, depends on runtime behavior).>

**Current:**
```ts
// existing line(s) being replaced, verbatim from the PR head
```

**Comment (paste from here down):**

<Comment body exactly as it would be pasted into GitHub — concise, constructive, self-contained.>

```suggestion
// full replacement for the commented line(s), valid to apply as-is
```

## Outstanding discussion

<Only unresolved reviewer concerns that still apply to the current diff — who raised it, what remains. Note `reviewDecision` if changes were already requested. **Omit this section entirely** when there is nothing outstanding.>

## Notes

<Optional — only facts that change how to act on the review: areas not reviewed (huge PR), lint/tests skipped and why, deep-mode fallback, suspicious-but-confirmed-OK patterns. **Omit this section entirely** when empty.>
````

**Output rules:**
- The document is **verdict first, then pasteable comments** — everything else exists only if it changes what the reader does. Never write filler sections ("No critical issues found", "No substantive discussion yet") — omit the section instead.
- One findings list only: every finding lives in `## Suggested comments`. No separate Findings/Suggestions/Critical sections — a finding is written once, as its postable comment.
- Severity prefix on every file entry: 🔴 blocker (must fix before merge) or 🟡 suggestion (author's call). Any 🔴 → verdict is Request Changes.
- Omit the `**Linear:**` segment if no Linear ID found.
- Quality over quantity — a 3-comment review that gets posted beats a 10-section report that doesn't.
- Every code suggestion MUST show both the `**Current:**` block (existing code, verbatim from the diff) and the replacement, so the reader sees the before/after without opening GitHub. Never show a replacement alone.

**Suggested comments** (always present, always the first section):
- The **first entry is always the Overall comment**: thank the author for the specific feature/fix by name, include one genuine positive, then summarize the review outcome. No confidence line, no Current block, no severity prefix.
- Keep every comment **short, concise, kind, and easy to understand** — plain language, no jargon walls, no lecturing. One idea per comment.
- One `### <severity> \`path/to/file.ts:LINE\` — <title>` entry per finding.
- Every entry MUST start with a `**Confidence:**` line: High / Medium / Low, then an em dash and 1-2 sentences explaining the strengths or weaknesses of that rating (e.g. High: full context of the change visible in the diff, clear logic error; Low: depends on code outside the diff or runtime behavior you couldn't verify).
- The `**Confidence:**` line and `**Current:**` block are for the reader only — everything from the comment body down is what gets pasted verbatim into a GitHub inline comment. GitHub renders the before/after diff itself, so the pasted part needs no Current block.
- Include a GitHub ` ```suggestion ` block whenever a concrete replacement applies as-is (full replacement for the commented lines, no imports or context it can't carry). Otherwise, comment text only.
- Line numbers must match the PR **head** revision (`headRefOid`):
  - For existing review threads, trust the fetched `line` + `diffSide` fields (`RIGHT` = head). A `line: null` thread is **outdated** — it refers to an older commit (`originalLine`); say so instead of anchoring it.
  - For new findings, compute from the hunk header `@@ -a,b +c,d @@`: head numbering starts at `c` on the first line after the header; context (space) and `+` lines each advance it by 1; `-` lines advance it by 0. Example:
    ```
    @@ -40,6 +42,4 @@
     ctx        → head line 42
    -removed    → (none)
    +added      → head line 43
     ctx        → head line 44
    ```
  - Only anchor comments to lines present in the diff (`+` or context lines) — GitHub cannot accept inline comments on lines outside the diff.
- Findings with no file anchor (e.g. stale PR title) go last as a general PR comment — confidence line still required, no Current block.

### Step 4: Write Markdown & Open in Obsidian

1. **Write** the review markdown to `~/claude.nosync/reviews/<filename>.md`

2. **Open in Obsidian** using the URI scheme so it navigates to the note:
```bash
open "obsidian://open?vault=${OBSIDIAN_VAULT}&file=claude.nosync%2Freviews%2F<filename>.md"
```

Opening in Obsidian is best-effort: `open` exits 0 even if the vault/note fails to resolve. If the command itself errors (Obsidian not installed), fall back to `open <file>.md`.

Always report the absolute `.md` file path to the user.

## Filename Convention

Format: `YYYY-MM-DD-{project}-{pr-number}-{linearid}-{pr-title}`

Use `.md` extension.

- `{project}`: repo name, lowercase
- `{linearid}`: lowercase Linear ID. **Omit segment** if none found.
- `{pr-title}`: lowercase, spaces->hyphens, alphanumeric+hyphens only, max 50 chars, trim trailing hyphens.

## Rules

- **Remote-only by default.** Checkout allowed ONLY in deep mode (Complexity Gate), only into `~/worktrees.nosync/pr-review-*`, always cleaned up after.
- **NEVER commit, push, or modify code** — in any mode.
- **DO NOT post to GitHub** or approve/reject without explicit user request.
- Focus on high-impact findings. Skip trivial issues.
- One genuine positive belongs in the Overall comment — never a separate section.
- Be specific (file paths + line numbers) and constructive.
- For large PRs (>1000 lines), say in `## Notes` which areas you focused on and which you skimmed.
