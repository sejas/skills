---
name: sync-skills
description: Sync recently edited skills (`~/.claude/skills/<name>/`) and workflows (`~/.claude/workflows/<name>.js`) to a public skills repo. Reads the dirty-marker written by the `skill-dirty-marker.sh` PostToolUse hook, sanitizes secrets and personal identifiers, copies files to the repo, scans the staged diff, commits, and pushes. Use when the user says "sync skills", "sync workflows", "push skill", "update public skills repo", "sync my skills", or invokes /sync-skills.
user-invocable: true
---

# Sync Skills to Public Repo

Mirrors locally-edited **skills and workflows** to a public skills repo (configurable) with sanitization, secret scanning, and a single commit + push.

Companion piece to `hooks/development/skill-dirty-marker.sh` — the hook records *what changed*, this skill is the manual *push* step.

## Configuration

Reads from `~/.claude/skills/sync-skills/config.json`:

```json
{
  "public_repo_path": "~/path/to/your-skills-repo",
  "main_branch": "main",
  "personal_identifiers": ["your-handle", "your-handle-work", "<your-email>"]
}
```

- `public_repo_path` — destination working copy.
- `main_branch` — branch to commit/push to. Default `main`.
- `personal_identifiers` — additional substrings to grep for in the personal-ID sweep. Keep it short (just the ones that uniquely identify you).

If the config is missing, ask the user for these values on first run and write the file.

## Inputs

| Source | Purpose |
|---|---|
| `~/.claude/.skills-dirty` | Newline-separated list of entries dirtied since last sync, written by the marker hook. A bare name is a **skill**; a `workflow:<name>` line is a **workflow**. |
| `~/.claude/skills/<name>/` | Skill source of truth. |
| `~/.claude/workflows/<name>.js` | Workflow source of truth — user scope, so the `Workflow` tool finds it in every project. A copy under a project's `.claude/workflows/` is a convenience copy, never the source. |
| `${public_repo_path}/skills/<name>/` | Public destination for a skill. |
| `${public_repo_path}/workflows/<name>.js` | Public destination for a workflow. |

If `.skills-dirty` is missing or empty, ask the user what to sync, or offer to diff every skill and workflow against the repo.

## Files NEVER synced

- `config.json` — per-user state. **This is where anything identifying belongs**: real names and handles, colleagues, channel ids, internal URLs, tokens. A skill needing such data reads it from `config.json` at runtime and its `SKILL.md` names none of it. Keep `skills/*/config.json` git-ignored in both repos.
- `*.local.*`, `.env`, `.env.*`, `*.token`, `*.secret`.
- Anything matched by the secret-scan regex (see Step 4) even after sanitization attempts — abort and ask the user.

## Sanitization rules (applied to every file before copy)

| Pattern | Action |
|---|---|
| Personal `github.com` username | Replace with placeholder `your-handle` or env-var reference (`$GH_USER`, `$STANDUP_GH_USER`, etc. — match style already used in repo). |
| Personal Enterprise/work username | Replace with `your-handle-work` or `$GH_USER_ENTERPRISE`. |
| Real email addresses | Replace with `<your-email>`. |
| Hardcoded absolute paths leaking home-dir or vault layout | Replace with config-file lookup, `$HOME`, `~`, or env-var indirection. |
| API tokens (Telegram bot tokens, chat IDs, ntfy topics, OAuth secrets, AWS keys, GitHub PATs, OpenAI keys, etc.) | Hard-fail. Abort. Don't try to autoredact — surface to user. |
| **Third parties**: colleagues' handles, rotation schedules, Slack channel ids, internal wiki/tracker/CI URLs, team process | Not sanitizable by substitution — those people never consented. Stop, tell the user, and move the data into the skill's `config.json` before syncing anything. |
| A specific employer's `owner/repo` hardcoded in commands | Replace with an env var (`${REVIEW_REPO}`) or an `owner/repo` placeholder, even when that repo is public — it makes the skill reusable. |

Generic workspace paths (`~/claude.nosync/…`, `~/worktrees.nosync/…`) stay as they are; only the parts that name *you* get substituted.

When unsure, ask the user. **Never guess at redaction for a token.**

## Workflow

### Step 1 — Load config + read marker

Load `~/.claude/skills/sync-skills/config.json`. Resolve `public_repo_path` (expand `~`).

```bash
MARKER="$HOME/.claude/.skills-dirty"
[ -s "$MARKER" ] || { echo "no dirty skills"; exit 0; }
sort -u "$MARKER" -o "$MARKER"
```

If empty, ask user which skill to sync (or `--all` to diff every skill against the repo).

### Step 2 — For each dirty entry, build a sanitized copy

**Workflow entries** (`workflow:<name>`): copy `~/.claude/workflows/<name>.js` to
`${public_repo_path}/workflows/<name>.js` under the same sanitization rules. Workflow
scripts embed agent prompts — read the prompt strings too; a repo layout, an internal URL
or a team name hides there as easily as in a `SKILL.md`.

**Skill entries** (bare `<name>`):

1. Source dir: `~/.claude/skills/<name>/`.
2. Dest dir: `${public_repo_path}/skills/<name>/`.
3. List source files, filter out the NEVER-synced set above.
4. For each remaining file, read it, apply the sanitization rules, and write to the dest. Use judgment for placeholder/env-var style — match what the rest of the public repo already uses.
5. If a file would become identical to one already in the dest, skip it (avoid noise commits).

### Step 3 — Update README in the public repo

Skills belong in the `## Skills` tables, workflows in the `## Workflows` table.

If the entry is **new** (no row in `README.md`), prompt the user for a one-line "how I use it" description and add a row to the relevant table. If only the description has changed materially, ask whether to update.

If a skill was **renamed**, fix every README reference. If it was **removed** locally, ask whether to remove from public repo too (don't delete silently).

### Step 4 — Secret scan on staged diff

Generic secret regex (run unconditionally):

```bash
cd "${public_repo_path}"
git add -A skills/ workflows/ README.md
git diff --cached | grep -iE "(api[_-]?key|bearer|secret|password|[0-9]{9,}:[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}|xox[abps]-[A-Za-z0-9-]+)" && {
  echo "secret-like content in staged diff — aborting"
  git reset
  exit 1
}
```

Personal-identifier sweep (built from `config.personal_identifiers`):

```bash
# Build alternation: id1|id2|id3 (regex-escape each)
PATTERN=$(printf '%s|' "${PERSONAL_IDS[@]}" | sed 's/|$//')
git diff --cached | grep -E "($PATTERN)" && {
  echo "personal identifier leaked — aborting"
  git reset
  exit 1
}
```

If either guard fires, stop, show the matching lines to the user, and ask how to proceed (don't auto-fix tokens).

### Step 5 — Commit + push

```bash
git commit -m "<short subject>"
git push origin "${main_branch}"
```

Commit subject guidance:

- Single skill: `feat: sync <name> skill` or `fix: <name> <short reason>`.
- Single workflow: `feat: sync <name> workflow`.
- Multiple: `chore: sync skills (<comma list>)` — past ~3 names, truncate with `+N`.

No body unless the change is non-obvious. Some repos enforce a max subject length via a commit hook — keep it short (≤75 chars is a safe default).

### Step 6 — Clear marker

After a successful push:

```bash
: > "$HOME/.claude/.skills-dirty"
```

Tell the user: what synced (skills and workflows), commit SHA, files changed.

If something was deliberately **not** synced — a skill still holding third-party data, say —
don't clear its line. Rewrite the marker with just that entry so it resurfaces next time,
and say so.

## Pitfalls

- **Commit hook subject limits**: keep subject short, no `-m` body unless needed.
- **Don't commit `.skills-dirty`** itself if it ever ends up tracked (it lives in `~/.claude/`, not the repo).
- **Worktrees / non-main branches**: this skill assumes the configured `main_branch`. If the repo is on a feature branch, ask the user before committing.
- **First-time skill**: if a brand-new skill is being synced, the dest dir won't exist; `mkdir -p` it.
- **Renames**: the hook records the *new* name only. If the user renamed `foo` → `bar`, the old `foo/` in the repo won't be cleaned up automatically. Ask.
- **Never copy a local `SKILL.md` wholesale over its public counterpart.** The public copy is the sanitized one; overwriting it re-introduces every identifier the last sync stripped. Re-apply the *changes*, then let the scans confirm.
- **Workflows have no per-file config escape hatch.** A workflow needing private data reads it from a skill's `config.json` or an env var — never inline in the script.
- **Secret-scan false positives are normal**: prose like "scans for secrets", or a review checklist mentioning "API keys", trips the regex. Show the lines and let the user judge; never auto-strip.

## Done criteria

- `~/.claude/.skills-dirty` is empty, or holds only entries deliberately withheld.
- The public repo has one new commit on the configured branch containing only sanitized skill/workflow files + README updates.
- Secret-scan and personal-identifier-scan both passed.
- User informed of the new commit SHA.
