---
name: standup
description: Create or update today's work standup file. Pulls PR activity from github.com (via gh CLI) and an optional GitHub Enterprise host (via context-a8c MCP), deduplicates across sources and sections, preserves existing content. Use when the user says "update my standup", "today standup", "fill my standup", or invokes /standup.
user-invocable: true
---

# Standup Tracker

Maintains a daily standup markdown file. Generic + configurable. Works with `github.com` only, or with an additional GitHub Enterprise host.

## Configuration

The skill reads its parameters from a JSON config file:

```
~/.claude/skills/standup/config.json
```

Schema:

```json
{
  "standup_path": "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<vault>/💼 work/standup",
  "gh_user": "your-handle",
  "gh_user_enterprise": "your-handle-a8c",
  "enterprise_host": "github.a8c.com",
  "enterprise_owner": "Automattic",
  "enterprise_repos": ["wpcom", "studio", "jetpack"],
  "gh_repos": ["owner/repo"],
  "track_linear": true,
  "linear_teams": ["STU"],
  "copy_to_clipboard": true
}
```

- `standup_path` — **required**. Directory where daily files live. May contain spaces or emoji; expand `~` and `$HOME`.
- `gh_user` — **required**. Your `github.com` login (used to detect author/reviewer/merger of PRs).
- `gh_user_enterprise` — optional. Login on the Enterprise host. If absent, the Enterprise step is skipped.
- `enterprise_host` — optional. Hostname (e.g. `github.a8c.com`). Used only to build URLs / log messages.
- `enterprise_owner` — optional. Org/owner for Enterprise PR searches.
- `enterprise_repos` — optional array. Repos to scope Enterprise queries to (Enterprise search returns 0 results without `owner` + `repo`). Only list repos that exist on the Enterprise host — repos that live on `github.com` (e.g. `studio`) return `422` here.
- `gh_repos` — optional array of `owner/repo` on `github.com`. Scanned to detect **PRs the user merged but did not author** (GitHub search has no `merged-by:` qualifier, so these must be found per-repo). If empty/absent, only authored-and-merged PRs are detected.
- `track_linear` — optional (bool). If `true`, gather Linear issues **created by the user today** via the `context-a8c` `linear` provider and add a "Created Linear issues" section. If absent/false, Linear is skipped.
- `linear_teams` — optional array of Linear team keys (e.g. `["STU"]`) to scope the created-issue scan. If absent, falls back to `my-issues`.
- `copy_to_clipboard` — **required** (bool). If `true`, copy the merged file contents to the system clipboard (`pbcopy` on macOS, `wl-copy` / `xclip -selection clipboard` on Linux) after writing. If `false`, only write the file to disk.

### First-run / missing-config flow

Before doing anything else:

1. Try to read `~/.claude/skills/standup/config.json`. If the file doesn't exist or any **required** key (`standup_path`, `gh_user`) is missing/empty, switch to setup mode.
2. In setup mode, ask the user **only for the missing keys** using `AskUserQuestion` (or plain prompts if that tool isn't available). One question per key:
   - **standup_path** — "Where should standup files be saved? (absolute path)"
   - **gh_user** — "What is your github.com username?"
   - **gh_user_enterprise** *(only ask if user wants Enterprise; first ask yes/no)* — "What is your Enterprise host username?"
   - **enterprise_host** — "What's the Enterprise hostname? (e.g. `github.a8c.com`)"
   - **enterprise_owner** — "Which org/owner on the Enterprise host?"
   - **enterprise_repos** — "Which Enterprise repos should be scanned? (comma-separated)"
   - **gh_repos** *(optional)* — "Any github.com repos where you merge others' PRs and want them tracked? (comma-separated `owner/repo`, or skip)"
   - **track_linear** — "Track Linear issues you create each day? (yes/no)"
   - **linear_teams** *(only ask if track_linear is yes)* — "Which Linear team keys to scan? (comma-separated, e.g. `STU`)"
   - **copy_to_clipboard** — "After writing, also copy the standup contents to the clipboard? (yes/no)"
3. Validate the path exists or can be created. Create it with `mkdir -p` if not.
4. Write the JSON file with **2-space indent**. Preserve unknown keys if the file already existed.
5. Confirm to the user the path written, then continue with the main workflow.

**Never hardcode** any of these values in this skill file. Always resolve at runtime from the config.

### Re-configuring

If the user says "reconfigure standup" or "reset standup config", overwrite the file by repeating the setup flow for every key.

## Output format (match exactly)

```
#yolo-standup 
Today:

- Created PRs:
    - [<auto-title>](<pr-url>)
- Merged:
    - [<auto-title>](<pr-url>)
- Reviewed:
    - [<auto-title>](<pr-url>)
- Created Linear issues:
    - [<ISSUE-KEY>: <issue title>](<issue-url>)

<free-form bullets / notes at top level, no header>

Next:
- <bullet>
```

**Auto-title pattern (PRs):** `<PR title> by <author> · Pull Request #<number> · <owner>/<repo>` — matches GitHub's own `<title>` element.

**Linear link pattern:** `<ISSUE-KEY>: <issue title>` (e.g. `STU-1771: Add a lint rule…`).

**Section order (canonical):** Created PRs → Merged → Reviewed → Created Linear issues → free-form → Next.

**Style rules (do not violate):**

- Section headers are top-level `- ` bullets ending in `:` (e.g. `- Created PRs:`).
- PR links nest one level deeper as `- ` bullets, indented with 4 spaces (or one tab).
- No inline state annotations (`— open`, `— merged`, timestamps). Section placement carries that info.
- No "Other:" header — free-form lines live at top level between Reviewed and Next.
- Sections are omitted entirely when empty; never leave empty headers.
- Trailing space after `#yolo-standup` is intentional (file convention).

## Section rules

| Section | Inclusion rule |
|---|---|
| **Created PRs** | PRs authored by the user with `created_at` today (local tz). Includes PRs created today that were also merged today. |
| **Merged** | PRs with `merged_at` today AND `created_at` < today, where the user is **either the author OR the merger** (`merged_by.login` ∈ user logins). Catches both "I landed my own PR" and "I merged someone else's PR". |
| **Reviewed** | PRs NOT authored by the user with a review by the user submitted today. Exclude PRs already in Created or Merged. |
| **Created Linear issues** | Linear issues whose `creator` is the user and `created_at` is today (local tz). Only when `track_linear` is `true`. |
| Free-form | Manual notes (meetings, blockers, learnings). Preserved verbatim. |
| **Next:** | Manual TODO bullets for tomorrow. Preserved verbatim. |

"Authored by the user" = `user.login` ∈ {`config.gh_user`, `config.gh_user_enterprise`}. "Merged by the user" = `merged_by.login` ∈ the same set.

## Dedupe rules

- **Cross-section:** a PR URL appears in at most one section, priority Created > Merged > Reviewed.
- **Cross-source:** the same PR URL must not appear twice even if it surfaces from both `gh` and the Enterprise MCP, or from both the authored-merged and merged-by-me queries. Normalize URLs (strip trailing slash, query string) before comparing.
- **Linear:** dedupe by issue URL (or `ISSUE-KEY`). If the file already lists the issue anywhere, skip it.
- **Append-aware:** if the file already lists a PR URL or Linear issue anywhere, do not add it again. Manually-written free-form lines stay untouched.

## Workflow

### Step 1 — Load config (see "First-run" flow above)

Load `~/.claude/skills/standup/config.json`. Expand `~` in `standup_path`. If incomplete, run setup.

### Step 2 — Gather data, in parallel

#### 2a. GitHub Enterprise (only if `gh_user_enterprise` is set)

Load provider once per session:

```
mcp__context-a8c__context-a8c-load-provider  provider: "github-a8c"
```

For each repo in `config.enterprise_repos`:

```
mcp__context-a8c__context-a8c-execute-tool
  provider: "github-a8c"
  tool: "search-pull-requests"
  params: { query: "author:<gh_user_enterprise> updated:YYYY-MM-DD", owner: "<enterprise_owner>", repo: "<repo>", perPage: 50 }
```

Repeat with `reviewed-by:<gh_user_enterprise>`.

> Note: global queries return 0 results on this host; always scope by `owner` + `repo`.

If output exceeds the response limit, the MCP server saves JSON to a file path — use `jq` to extract `{number, title, state, created_at, updated_at, closed_at, merged_at, html_url, user.login, pull_request.merged_at}`.

#### 2b. github.com via gh CLI

Use `gh search prs` (the `--created`/`--merged-at` date filters are reliable; the old `gh pr list --search "created OR updated"` form silently misses authored-and-merged PRs):

```bash
DATE=$(date +%Y-%m-%d)
# Created today (authored by me)
gh search prs --author=@me --created "$DATE" \
  --json url,title,number,createdAt,author,repository
# Merged today (authored by me) — created earlier
gh search prs --author=@me --merged-at "$DATE" \
  --json url,title,number,createdAt,author,repository
```

**Merged-by-me but NOT authored by me** — GitHub search has no `merged-by:` qualifier, so scan each repo in `config.gh_repos` and filter on `mergedBy.login`:

```bash
DATE=$(date +%Y-%m-%d)
for slug in <config.gh_repos>; do                # e.g. Automattic/studio
  owner=${slug%/*}; repo=${slug#*/}
  gh api graphql -f query='
  query($q: String!) {
    search(query: $q, type: ISSUE, first: 50) {
      nodes { ... on PullRequest {
        url title number createdAt mergedAt
        author { login } mergedBy { login }
      } }
    }
  }' -f q="repo:$owner/$repo is:pr is:merged merged:$DATE"
done
# Keep only nodes where mergedBy.login ∈ {gh_user, gh_user_enterprise}.
```

Reviews via GraphQL (bound both ends of the day so it scopes to the target date):

```bash
DATE=$(date +%Y-%m-%d)
gh api graphql -f query='
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      pullRequestReviewContributions(first: 50) {
        nodes {
          pullRequestReview { submittedAt }
          pullRequest { url title number author { login } merged createdAt }
        }
      }
    }
  }
}' -f from="${DATE}T00:00:00Z" -f to="${DATE}T23:59:59Z"
```

> **Verify every review date.** `contributionsCollection` appears to round `from`/`to` to whole UTC days: a window starting `2026-10-01T23:00Z` (local midnight in UTC+1) returned a review submitted 2026-10-01T14:49Z. Keep the window as written above (don't shift it to local tz), but still don't trust it as-is. Convert each node's `pullRequestReview.submittedAt` to local time and keep the PR only if it falls on the target date. The same applies to Enterprise `reviewed-by:` results: `updated:` matches any activity on the PR, so call `pull-request` with `method: "get_reviews"` and keep the PR only if one of the user's reviews has a local `submitted_at` on the target date.

> When the user passes an explicit date (e.g. `/standup Jun 2`), substitute that date for `$DATE` everywhere instead of `today`.

#### 2c. Linear issues created today (only if `config.track_linear` is true)

Use the `context-a8c` `linear` provider:

```
mcp__context-a8c__context-a8c-load-provider  provider: "linear"
```

- If `linear_teams` is set, for each team call `team-issues` with `days: 2` (small window covering today). Otherwise call `my-issues` with `days: 2`.
- These tools return `updated_at` but not always `creator`/`created_at`. For each candidate, fetch the `issue` detail (`subtool: "issue"`, `id: "<KEY>"`) and keep it only when **`creator.display_name` is the user AND `created_at` falls on the target date** (local tz).
- `my-issues` only returns issues assigned to the user, so issues the user created and assigned to *someone else* are missed — note this limitation if the user expected more. Prefer `linear_teams` for completeness.

### Step 3 — Classify each PR / issue

For PRs:

- author ∈ user logins AND `created_at` == today → **Created PRs**.
- `created_at` < today AND `merged_at` == today AND (author ∈ user logins OR `merged_by.login` ∈ user logins) → **Merged**.
- not authored by user, review `submitted_at` verified on the target local date (see 2b note) → **Reviewed** (only if URL not already in Created or Merged).
- Otherwise → ignore unless explicitly mentioned in free-form.

For Linear issues: `creator` is the user AND `created_at` == today → **Created Linear issues**.

### Step 4 — Resolve auto-title

Build the link using the auto-title pattern. Pull `title`, `user.login`, `number`, owner/repo (from `html_url` or `repository_url`).

Example:

```
[Some PR title by your-handle · Pull Request #12345 · owner/repo](https://github.com/owner/repo/pull/12345)
```

### Step 5 — Read existing file

Path: `${config.standup_path}/YYYY-MM-DD.md`. Quote the path in bash (may contain spaces or emoji).

If the file doesn't exist, scaffold:

```
#yolo-standup 
Today:

Next:

```

If the file exists, parse section-by-section. Collect every PR URL already present into a known-set for dedup.

### Step 6 — Merge

- For each new PR URL / Linear issue not in the known-set, append it to its target section in canonical order (Created PRs → Merged → Reviewed → Created Linear issues).
- Preserve every existing PR line, Linear line, free-form line, and `Next:` bullet exactly as-is. The skill is additive — never rewrites or reorders existing content.
- If the file is missing one of the headers and there's content for it, insert the header in canonical order (Created Linear issues goes after Reviewed, before any free-form bullets).
- Never insert an empty header.

### Step 7 — Write

Write the merged file.

### Step 8 — Clipboard (if `config.copy_to_clipboard` is true)

Pipe the merged file contents to the system clipboard:

- macOS: `cat "$FILE" | pbcopy`
- Linux (Wayland): `cat "$FILE" | wl-copy`
- Linux (X11): `cat "$FILE" | xclip -selection clipboard`

If the platform isn't detected or the binary is missing, surface a warning but don't fail the run.

### Step 9 — Confirm

Tell the user:

1. New PRs added per section (Created / Merged / Reviewed), and new Linear issues added.
2. Duplicates skipped (per source).
3. Hosts that errored (note `github-a8c` 422 errors for repos that don't exist or are inaccessible — e.g. a repo listed in `enterprise_repos` that actually lives on `github.com`).
4. Whether the contents were also copied to the clipboard.

## Pitfalls

- **Timezone:** GitHub returns UTC `created_at` / `merged_at`. Convert to the user's local date before comparing to "today". A PR at `2026-05-14T23:30:00Z` is `2026-05-15` for UTC+1.
- **Search index lag:** Enterprise search can lag by minutes for very fresh PRs. Retry once after a short pause; fall back to fetching by number with the `pull-request` tool if still missing.
- **Multiple repos:** when a configured repo returns nothing and the user expected activity, ask which other repo to query rather than guessing — and offer to add it to `enterprise_repos`.
- **Path quoting:** `standup_path` may contain spaces or emoji. Quote everywhere in bash.
- **No revert of user edits:** if the user previously trimmed annotations, do not re-add them on the next run.
- **Config drift:** if the user manually edits the JSON and breaks it (invalid JSON, missing required keys), surface the error and re-run setup for the broken keys only.

## Done criteria

- Config file present and complete.
- File at `${config.standup_path}/YYYY-MM-DD.md` exists with today's PR activity split into Created / Merged / Reviewed, plus Created Linear issues when `track_linear` is on.
- Merged section catches PRs the user merged, even when authored by someone else.
- No URL appears in more than one section.
- No URL appears twice within a section.
- All pre-existing free-form bullets and `Next:` entries are untouched.
- Short summary printed listing what was added and what was deduped.
