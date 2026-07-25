# AI Code Skills

A flat collection of [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) and supporting hooks for development, presentations, and content workflows.

These are the skills I (Antonio Sejas) use day-to-day across Automattic work and personal projects. They are intentionally small, single-purpose, and composable — drop in whichever ones you find useful.

## Layout

```
skills/     # one folder per skill, each containing SKILL.md
hooks/      # standalone hook scripts grouped by purpose
workflows/  # multi-agent orchestration scripts for the Workflow tool
```

No plugin manifest, no marketplace — just drop the folders where you want them.

## Install

Copy or symlink any skill into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/commit" ~/.claude/skills/commit
```

Or symlink the whole directory to expose every skill:

```bash
for d in skills/*/; do ln -s "$PWD/$d" "$HOME/.claude/skills/$(basename $d)"; done
```

## Skills

Each skill is invoked by typing `/<skill-name>` in Claude Code, or by triggering a phrase from the skill's description (Claude auto-routes).

### Development

| Skill | What it does | How I use it |
|---|---|---|
| `commit` | Drafts a Conventional Commit message from the staged diff and creates the commit. | `/commit` when staging is ready. Lets me skip writing commit subjects by hand. |
| `explain` | Locates a function in the codebase and explains it for a junior dev. | `/explain handleAuth` when onboarding to a new repo. |
| `worktree` | Creates an isolated git worktree from `origin/trunk` in `~/worktrees.nosync/`, copies `node_modules`. | `/worktree feat/new-thing` to start parallel feature work without polluting the main checkout. |
| `pr-review` | Lists PRs awaiting my review, checks out each branch, runs the linter, and writes a structured review doc. | Daily review pass — pick one off the list and let the skill set up the workspace. |
| `quick-pr-review` | Lightweight diff review against a GitHub PR URL (no checkout). | When I just need a fast read on a colleague's PR. |
| `ai-prs` | Lists open PRs targeting the Studio AI command with status/approval/reviewers. | Triage Studio AI PRs before standup. |
| `react-doctor` | Scans recent React changes for common issues (hook deps, key warnings, state misuse). | After finishing a React feature, before /commit. |
| `create-agents-md` | Generates `AGENTS.md` / `CLAUDE.md` for a repository documenting conventions and structure. | When starting a new repo or onboarding a coding agent. |
| `studio-debug` | Inspects WordPress Studio local sites — SQLite DB, logs, plugin/theme issues. | When a Studio site misbehaves locally. |
| `teach` | Acts as a teacher that makes me deeply understand the current session — problem, solution, edge cases, broader impact — via a running checklist, incremental confirmation, and quizzes (`AskUserQuestion`). | `/teach` after Claude lands a non-trivial change I want to actually internalize, not just merge. |
| `score` | Calibrated 0–10 judging of any artifact — website/UI (screenshot), markdown draft (direct read), or code diff. A fresh judge subagent reasons first (strengths/weaknesses/improvements/reasoning), score last, with calibration anchors and a pinned "what a 10 looks like" bar so improve-until-N loops converge instead of chasing moving goalposts. | `/score` the landing page, then a goal loop "repeat until 9/10" — the judge drives design/writing iteration. |
| `start-issue` | From a Linear link or branch name: resolves the issue (Linear MCP, `context-a8c` fallback), spins up a worktree, implements the fix, verifies (lint/typecheck/tests, light+dark for UI), then commits, pushes, and opens a draft PR with the template filled in. | `/start-issue <linear-link>` to go from ticket to draft PR in one shot. |
| `unworktree` | Reverse of `worktree`: absorbs a worktree's branch back into the main checkout — dirty-tree safety gate, removes the worktree, checks the branch out in the main repo. Set `$MAIN_REPO` to your main checkout. | When I'm done in a `~/worktrees.nosync/` branch and want to continue it in the main repo. |
| `explore-exploit` | Generate-many-then-select for tasks with a large solution space and a measurable quality signal (naming, UI variants, copy, code/prompt tuning). Fans out candidates, scores them, and iterates toward the best — tournament / simulated-annealing style. | "Generate N options and rank them" or an iterate-until-score loop. |
| `design-review` | Designer's-eye QA of a running UI: screenshots at desktop/tablet/phone plus the states the happy path hides, then reports spacing, hierarchy, contrast, state and motion defects by severity with the CSS fix for each — including the AI-slop tells (gradient hero, emoji bullets, three feature cards). | Before shipping a user-facing screen, or when something looks off and I can't name why. |
| `review-queue` | Merge-confidence table for the PRs still waiting on my review, rated 0-100 from the review docs already on disk. Set `REVIEW_REPO`. | "Which of these can I just merge?" at the end of a review pass. |
| `review-sweep` | Fans out review agents across every PR awaiting my review, then re-checks the queue to catch new or updated ones. | When the queue has piled up and I want one pass over all of it. |
| `first-time-contributors` | Finds authors whose first-ever merged PR in a repo landed inside a recent window, via `gh`. | Crediting a new contributor in release notes or a shout-out post. |
| `pr-leaderboard` | Ranks merged PRs and contributors over a window, for the current repo or any `owner/repo`. | "Who shipped what this week" before a team update. |
| `release-notes` | Turns a list of merged PRs into user-facing release notes: grouped by theme, one line per coherent change, every PR cited exactly once, with scripted verification of the coverage. | Writing release notes for a version without missing or double-counting PRs. |

### Standup / Daily

| Skill | How I use it |
|---|---|
| `today` | Enriched daily activity from Claude Code sessions — branches, PRs, Linear issues, what I worked on. Run at end of day. |
| `standup` | Daily standup file at `${STANDUP_PATH}/YYYY-MM-DD.md`. Pulls PRs from `github.com` (via `gh`) and an optional GitHub Enterprise host (via `context-a8c` MCP), dedupes across Created / Merged / Reviewed sections, and appends without rewriting existing notes. Configure with `STANDUP_PATH`, `STANDUP_GH_USER`, `STANDUP_GH_USER_ENTERPRISE`, `STANDUP_ENTERPRISE_OWNER`, `STANDUP_ENTERPRISE_REPOS`. I run `/standup` once at end of day before posting in Slack. |

### Content

| Skill | How I use it |
|---|---|
| `brainstorming-names` | Names or renames anything — product, feature, brand, command — generating ranked candidate names with rationale. When something needs a name and I want options, not just the first idea. |
| `blog-post` | Drafts a markdown blog post in `~/claude.nosync/posts/`. I outline the topic, the skill produces a first draft. |
| `question` | Answers a question and renders the answer as a styled HTML page. Useful for sharing technical explanations as a link. |
| `presentation` | Generates Marp slides from a spec/intent doc. Turns a written brief into a deck. |
| `og-inspect` | Inspects a URL's Open Graph / Twitter Card metadata and renders multi-platform share-card previews (Facebook, X, LinkedIn, Slack, Tumblr). |
| `travel-routes` | Extracts travel routes from Apple Photos geolocation (via `osxphotos`), clusters dwell points into visited cities, builds interactive maps, and scaffolds trip blog posts. Config via `config.json` (copy `config.example.json`); posts dir overridable with `$TRAVEL_POSTS_DIR`. | Building a vacation recap or year-in-review map from my photo library. |
| `make-pdf` | Markdown to publication-quality PDF via WeasyPrint: cover page, clickable TOC with real page numbers, running headers, curly quotes, syntax-highlighted code, optional DRAFT watermark. Needs `uv` and Homebrew `pango`. Sending a written doc to someone who will not read markdown. |

### Productivity

| Skill | How I use it |
|---|---|
| `todo` | Adds a task to Things 3 via the `things:///` URL scheme. Voice-style: "todo: pick up groceries". |
| `context-window-statusline` | Sets up the Claude Code footer to show context window usage, token counts, and session cost. One-shot install. |
| `sync-skills` | Mirrors edited skills (`~/.claude/skills/<name>/`) and workflows (`~/.claude/workflows/<name>.js`) to a configurable public skills repo. Reads the `~/.claude/.skills-dirty` marker written by the `skill-dirty-marker.sh` hook, sanitizes personal IDs and scans for secrets, then commits + pushes. Config at `~/.claude/skills/sync-skills/config.json` (repo path, branch, personal-identifier list). I run `/sync-skills` after editing local skills to push the changes here. |
| `mac-cleanup` | Frees disk space on macOS: scans for space hogs, sorts them into risk buckets (regenerable caches / app data / personal media / backups), offloads irreplaceable media + deduped WordPress backups to remote storage (e.g. Hetzner Storage Box), and trashes only what regenerates. Ships tested scripts (`scan-disk.sh`, `offload-retry.sh` with SSH-drop retry, `backup-dedup.py` for latest-per-site), plus a macOS-quirks reference (bash 3.2, openrsync, `trash` vs `rm`). "Clean up my Mac" / "my disk is full". |
| `ai-radar` | Digest of what is moving at the AI frontier — new work, trends, and where to spend learning time — from a curated source list in `sources.md`. Catching up after a week heads-down. |

## Workflows

Scripts for Claude Code's `Workflow` tool — deterministic multi-agent pipelines. Drop them in `.claude/workflows/` (per project) or `~/.claude/workflows/` (global), then run `Workflow({ name: '<file-name>', args: { … } })`.

| Workflow | What it does |
|---|---|
| `linear-issue-pipeline` | Takes a Linear issue id and drives it to a branch: fetch + triage the issue, create a worktree, explore the codebase, plan, implement, review, verify (lint/typecheck/tests + UI screenshots), and optionally open a draft PR. Model tier scales with the triaged issue size, exploration output is handed to the implementer instead of being re-derived, and verification runs exactly once as the single gate. `args: { issue, push, assignee, repo, worktree, plan, team }`. The prompts assume the [WordPress Studio](https://github.com/Automattic/studio) repo layout — swap the repo-specific conventions for your own. |
| `explore-exploit-strategy-search` | Fans out 20 agents that each design a search strategy for Claude Code from a different metaheuristic seed (simulated annealing, genetic algorithms, beam search, …), then scores all 20 with a fixed 3-judge panel against a frozen rubric and returns the top 3. A worked example of the generate-many-then-judge pattern the `explore-exploit` skill applies inline. |

## Hooks

Standalone bash hook scripts, opt-in. Wire them into `~/.claude/settings.json` under the relevant hook events.

- `hooks/development/` — auto-format, session-context loader, save-summary, speak-commit (TTS), `skill-dirty-marker.sh` (PostToolUse on `Write|Edit|MultiEdit`: detects edits under `~/.claude/skills/<name>/` and appends the skill name to `~/.claude/.skills-dirty` so a later sync step knows what to push; ignores `config.json`, `.env*`, `*.local.*`, `*.token`, `*.secret`).
- `hooks/notifications/` — local + remote notification scripts. The remote variant auto-detects Telegram / ntfy.sh from env vars (`CLAUDE_TELEGRAM_TOKEN`, `CLAUDE_TELEGRAM_CHAT_ID`, `CLAUDE_NTFY_TOPIC`). **Never commit your actual token values** — keep them in a `.env` file (gitignored) and source it from your shell rc.
- `hooks/standup-tracker/` — end-of-session reminder that nudges me to run `/standup` before logging off.
- `hooks/statusline/` — the script behind the `context-window-statusline` skill.

## Secrets

This repo never commits tokens, API keys, or chat IDs. The `.env` file (containing `CLAUDE_TELEGRAM_TOKEN`, `CLAUDE_TELEGRAM_CHAT_ID`, `CLAUDE_NTFY_TOPIC`) is gitignored — populate it locally on each machine.

## License

MIT — see [LICENSE](./LICENSE).
