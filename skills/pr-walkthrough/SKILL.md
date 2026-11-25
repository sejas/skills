---
name: pr-walkthrough
description: Use after every PR review (quick-pr-review hands off here), or when the user wants to understand a PR piece by piece — "walk me through this PR", "explain each change", "pr walkthrough", "guided review", "teach me this diff", or /pr-walkthrough <url> [--log]. Builds a local, keyboard-driven HTML page that first asks whether the solution is the right approach for the problem, maps the blast range (which screens, components and APIs the change reaches), then tells the PR as a story (data → logic → wiring → tests), one short step per idea, with notes pinned to exact lines, "spot it" probes before each finding, copy-ready GitHub comments with deep links, and ≤3 transferable lessons. Works with github.com and GitHub Enterprise PRs.
---

# PR Walkthrough

An understanding tool, not a report. **Concise is the feature.** The reader skims a title and one line, looks at the code, and opens extras only when wanted.

**Output:** `~/claude.nosync/reviews/<YYYY-MM-DD>-<repo>-<number>-walkthrough.html`. It's self-contained and private code never leaves the machine; highlight.js loads from cdnjs only for colours.
**Work dir:** `~/claude.nosync/reviews/.walkthrough/<repo>-<number>/`, holding `pr.diff`, `hunks.json`, `walkthrough.json` and optionally `findings.json`, `screenshots.json` and `screenshots/`.

## Steps

1. **Fetch.** Parse the URL (`<host>/OWNER/REPO/pull/N`, ignore suffixes). Create the work dir first and write **every** fetched file there (`pr.json`, `pr.diff`, `threads.json`), never to the scratchpad or `/tmp`: parallel reviews share those and one PR's data silently overwrote another's. Before using `pr.json`, check its `number` equals N.
   - github.com: `gh pr view N --repo O/R --json number,title,body,author,headRefOid,additions,deletions,url > pr.json`, then `gh pr diff N --repo O/R > pr.diff`.
   - GitHub Enterprise: `GH_HOST=<enterprise-host> gh …` (set `HTTPS_PROXY` if it sits behind a proxy).
   - Get the *why* from the PR body and the Linear issue (`[A-Z]{2,10}-\d+` in the branch or body).
   - **Preview deployment** (repos that post one, such as Vercel or Netlify). `PREVIEW_BOT=… PREVIEW_URL_RE='…' ~/.claude/skills/pr-walkthrough/scripts/preview-url.sh O/R N` prints the link from the PR comments. Store it as `pr.live` (the header shows it as a chip, so the reader can match it against the preview window). Empty output means no build was posted: note it in `testing` and continue.
   - **Deep links.** Every route in `testing` is a link into the preview, so one click lands on the page to test.
   - **Test data:** use a real test account or site of the user's (ask once, keep it in `config.json`) wherever a route needs one; never leave `<site>` or `example.com` placeholders. If the PR needs a state it can't have, say so in the step and name what to use instead.

2. **Parse.** `python3 -I ~/.claude/skills/pr-walkthrough/scripts/parse_diff.py pr.diff hunks.json` prints one line per hunk. Lockfiles, snapshots, `dist/`, `.snap` and files over 1500 changed lines are auto-collapsed into an appendix and need no step.

3. **Reuse the review.** If quick-pr-review already ran for this PR, `findings.json` is in the work dir. Don't rewrite those findings: reference them with `"finding": "f1"`. render.py turns each one into the step's comment and risk. Findings without a file anchor (Overall, spec questions) show on the wrap-up page automatically.

4. **Understand before writing.** Read every non-collapsed hunk. When a hunk depends on code outside the diff, read that code (`git -C <clone> show <sha>:<path>` or `gh api repos/O/R/contents/<path>?ref=<sha>`). Write checked facts only.

4b. **Ask first: is this the right approach for the problem?** Answer it before writing any step, because a line-by-line read of the wrong solution is wasted. It becomes `approach`, the first card on the overview.
   - State the problem from the issue and PR body in your own words: the user-visible symptom or need, not the PR title.
   - Check the fit: does the change fix the cause or only the symptom? Is it at the right layer (client vs. API, this component vs. a shared one)? Does something that already exists do this (grep for it)? Is there a markedly smaller change that solves the same problem?
   - `fit` is `right`, `unsure` or `wrong`. `unsure` and `wrong` need an `alternative` you checked is feasible, and the wrap-up `verdict` must agree with it. `right` still says in `why` what makes it right ("fixes the cause in the shared hook, so both callers get it"), not "looks good".
   - Can't tell what problem the PR solves (no issue, thin body)? That is `unsure`, and the first entry in `questions[]` asks the author.
   - If `findings.json` exists and its Overall comment doesn't raise an `unsure`/`wrong` approach, say so in your report: the review verdict may need revisiting.

4c. **Map the blast range: what else does this change reach?** The diff shows what changed; this shows who feels it. It becomes `blast`, the second card on the overview.
   - For every changed export (component, hook, selector, util, API helper, endpoint, CSS class, translation string, feature flag), find its consumers outside the diff: `gh search code` / `gh api search/code` or `git grep` in a clone at `headSha`. Follow re-exports one level.
   - Turn consumers into user-facing surfaces: which **screens and routes** render the changed component (map to routes, and to the apps that bundle it), which **components** share it, which **APIs or data** (endpoint shape, store, cache key, DB column) callers depend on, which **packages** publish it.
   - `level`: `contained` (only the screen/feature the PR names), `moderate` (other screens or a shared component in one app), `wide` (shared package, design-system component, API contract, data migration, or several apps).
   - A surface the PR didn't mention and no test covers is worth a `testing` step or a screenshot; tie it with `step` when a walkthrough step explains it. A surprising surface is a finding: give it a risk, not only a blast row.
   - `untouched` names what a reader might fear is affected but isn't ("Checkout imports a different copy").
   - Only checked facts: if a consumer search was incomplete (private repo, dynamic import), say so in `summary`.

5. **Learn from past questions.** `cat ~/claude.nosync/reviews/.walkthrough/*/questions.jsonl` lists what the reader asked through Ask on earlier walkthroughs. Terms and concepts they had to ask about should be explained up front: a note on first use, ≤15 words.
   **Learn from past reviews (if a log exists).** Read the learnings log (`$REVIEW_LEARNINGS`, default `~/claude.nosync/reviews/learnings.md`). Don't repeat a logged lesson. If a past *missed* pattern appears in this PR, give that step a probe.

6. **Write `walkthrough.json`** in story order (data → core logic → wiring → UI → tests "Proof" → bookkeeping). One step = one idea, usually 1–3 hunks of ≲60 lines; split big hunks with `"slice": [start, end]`.

   | field | budget | rule |
   |---|---|---|
   | `title` | 8 words | It *is* the "what". Verb or fact first. |
   | `why` | 15 | One sentence: the reason it exists. |
   | `more` | 40 | Optional, hidden behind ▸. How it connects or the non-obvious mechanics. |
   | `notes[]` | 15 each, ≤2/step | Only where the code alone would mislead: regex, guard, magic value, library quirk. |
   | `risk` | 20 | `{level: watch\|concern, text}`. Problem; fix. Only for real findings (otherwise use a note). Usually comes from `finding`. |
   | `probe` | 20 | Only on steps with a risk. Point at where the bug hides without naming it, answerable from the code shown. ✅ "The cookie passed www's consent check. What consent can change after that?" ❌ "What could go wrong here?" |
   | `comment` | 80 (excl. code) | Only if there's no `finding`: `{line, endLine?, side?, body}`. Kind and pasteable. Use a ```` ```suggestion ```` fence only if it drops in exactly for `line..endLine`; anything bigger goes in a plain ```` ```ts ```` fence. |
   | `lesson` | 20, **≤3 per PR** | A transferable pattern with **no identifiers from this PR**. ✅ "Re-check consent where data is used, not only where it was collected." ❌ "`impactClickId` is nullable so the migration is instant." |
   | `approach` | problem 20, why 25, alternative 25 | **Required.** `{problem, fit: right\|unsure\|wrong, why, alternative?}` from step 4b. `alternative` is required unless `fit` is `right`. |
   | `blast` | summary 25, `how` 15 each, untouched 15 | **Required.** `{level: contained\|moderate\|wide, summary, surfaces: [{kind, name, how, link?, step?}], untouched?}` from step 4c. `kind` is screen\|component\|hook\|api\|data\|package\|config\|other; ≤8 surfaces, grouped. `name` is a route, component or endpoint; `link` a preview deep link for screens. |
   | `tldr` | 30 | What the PR does plus scope. |
   | `context` | ≤3 bullets of ≤12 | Where it fits; every PR/issue mention is a link. |
   | `testing` | bullets, ≤25 each | Shown as the overview's **Test it** card. First bullet is `**Links:**` with the PR, the preview build (plus a note that it may lag the head commit) and the Linear issue. Then 3–6 numbered steps (`- 1. …`): where to go, what to do, what to see. The "where" is a clickable link: the preview URL of that screen, or the screen name. Never a placeholder. Tie each finding to a step ("step 4 finding"). |
   | `verdict` / `questions[]` | 25 / ≤3 × 15 | Wrap-up only. |

   Writing rules:
   - Never restate what the code visibly says.
   - One finding has one home: elsewhere write "the step 3 finding" rather than repeating it.
   - No meta lines ("reviewers should check…").
   - Cut words until removing one more would lose a fact.

   Skeleton:
   ```json
   {"title": "", "pr": {"url": "", "repo": "", "number": 0, "author": "", "additions": 0, "deletions": 0, "headSha": "", "live": ""},
    "approach": {"problem": "", "fit": "right", "why": "", "alternative": ""},
    "blast": {"level": "moderate", "summary": "", "untouched": "",
              "surfaces": [{"kind": "screen", "name": "/settings/domains", "how": "", "link": "<live-url>/settings/domains", "step": "2.1"}]},
    "tldr": "", "context": "- …", "testing": "- **Links:** [PR #N](…) · [Preview](…) · [ABC-123](…)\n- 1. Open [/settings/domains](<live-url>/settings/domains), click …: expect …",
    "chapters": [{"title": "1 · …", "steps": [
      {"title": "", "why": "", "more": "", "probe": "", "finding": "f1", "lesson": "",
       "hunks": [{"id": "h4"}, {"id": "h6", "slice": [0, 12]}],
       "notes": [{"hunk": "h4", "line": 16, "text": ""}]}]}],
    "verdict": "", "questions": []}
   ```
   Note and comment `line` values are new-file line numbers. Use `"side": "old"` for deleted lines.

6b. **Plan before/after screenshots (UI changes only).** If the PR changes anything a user sees, write `screenshots.json` next to `walkthrough.json`. Skip it for backend-only, test-only, config-only or build-tooling PRs, and say so in your report.
   ```json
   {"before": {"label": "main", "url": "<base-preview-url>"},
    "after": {"label": "PR build", "url": "<pr.live>"},
    "shots": [{"id": "s1", "title": "≤8 words", "route": "/settings/ssh", "step": "3.2",
               "do": "what to click or hover before capturing, and what to crop to", "note": "optional, ≤15 words"}]}
   ```
   - 1–4 shots, one per visible change, each tied to the step that explains it. Prefer a crop of the changed component, plus one full page if the layout moved.
   - **Before = the PR's base branch**, on its own preview or on a deployed environment that runs it. For a stacked PR, the base is the parent branch.
   - If the change needs state the test data lacks (an expired record, a flag), say so in `do` and put flags in the route.
   - No preview for the repo? Skip the shots.
   - Write the plan only. The images are captured in step 10.

7. **Render.** `python3 -I ~/.claude/skills/pr-walkthrough/scripts/render.py hunks.json walkthrough.json <out.html>`.
   - It **fails** on: a missing or incomplete `approach` or `blast`, unknown hunks or lines, any uncovered changed line, an anchored finding no step uses, more than 3 lessons, a probe without a watch/concern risk, `info` risks, and comments on lines GitHub can't anchor.
   - It **warns** on word budgets.
   - Fix and re-run until it reports **0 budget warnings**. Never pass `--allow-uncovered` unless asked.
   - render.py computes each comment's GitHub link: `<pr>/files#diff-<sha256(path)>R<line>[-R<end>]`. GitHub redirects `/files` to `/changes` and keeps the line selected.

8. **Verify notes.** For each note and comment, print the code at `(hunk, line)` from `hunks.json` and confirm it is the line meant.

9. **Open the review layout.** Run `~/.claude/skills/pr-walkthrough/scripts/layout.sh <workdir> <out.html> <pr-url> [<preview-url>]`. It serves the page with Ask on a fixed port (`4` + the PR number's last 4 digits) and tiles the browser on the main screen: walkthrough on the left half, PR files on the right top, the preview on the right bottom. Without a preview link (other repos, or none posted) the PR fills the right half. macOS only; defaults to Brave, set `REVIEW_BROWSER="Google Chrome"` to use Chrome.
   - **Several PRs at once:** open one layout at a time (3 windows each) and give the user the command for the rest. Subagents never run this step or step 10; they return the command and the parent runs both. When the user asks to open several, run the commands in the order they will review them, last one first, so the first PR ends on top.
   - **Ask:** select text and click Ask, or press `a`; answers stream into a side drawer, and follow-ups keep the thread.
   - Each question runs `claude -p` with **no tools, no MCP and no hooks**, so text inside the PR can't trigger actions. It's given the diff, the walkthrough (including notes) and the findings.
   - The server is protected by a per-run token, Host/Origin checks, and an idle shutdown after 30 minutes.
   - Report the approach fit first, then the blast level and any surface the PR didn't mention, then the URL, the step count, and which steps have findings. Opening the .html file directly still works, just without Ask.
   - No local checkout or dev server for testing: rely on the PR's own preview, if any.

10. **Take the before/after screenshots** (main session only, after the layout is open, when `screenshots.json` exists). Subagents can't do this: it needs the user's logged-in browser.
    - Use claude-in-chrome in a **new tab**. For each shot, open `before.url` at the shot's `route`, do what `do` says, and take a screenshot. Zoom in on the component's region for the crop, with `save_to_disk` and **no `scale`**: `scale` also shrinks the saved file. Then do the same on `after.url`.
    - Some previews drop the route on first load while a container starts. Once it lands, navigate to the route directly.
    - **Start a slow base build early.** Open `before.url` in a background tab as soon as the layout is open, and capture the PR side while it builds.
    - **If the base build fails**, use the preview of the most recently merged PR that touched the same area as "before". Confirm with `gh api repos/O/R/compare/<mergeSha>...<base>` that no file in that area changed since it merged, and label the side e.g. `main (≈ build of #N)`.
    - Copy each image from the claude-in-chrome screenshot folder (`$TMPDIR/claude-chrome-screenshots-*/`, newest file) to `<workdir>/screenshots/<id>-before.png` and `<id>-after.png`. Set `"before"` and `"after"` in `screenshots.json` to those relative paths.
    - If one side can't be captured (no such state on the base, a login wall, a browser permission dialog), leave that side out and set `"skip": "<reason>"`. Never trigger browser dialogs to get a shot.
    - Re-run step 7's render command. serve.py reads the HTML on every request, so reloading the walkthrough tab shows the **Before / after** card on the overview. Click an image to toggle full width.
    - Close the tabs you opened. Report which shots differ and which are identical. Say whether identical shots are expected for this PR.

11. **Log (only with `--log` or when asked).** First ask the user which probes they spotted. Then append to the learnings log, one line per lesson:
    `- YYYY-MM-DD [repo#N](url) · <lesson> · spotted|missed|—`
    If the file doesn't exist, create it with a one-paragraph purpose. The log is append-only.

## Viewer

- **Header:** PR title link, +/− counts, and the preview chip (build + env) when `pr.live` is set.
- **Overview:** **Right approach?** (problem, fit, why, alternative) first, then **Blast range** (level, summary, surfaces table, not affected), TL;DR, background, **Test it** (links + testing steps), **Before / after** (screenshots side by side, when captured), route, and which step covers each file.
- **Each step:** title + risk dot, one "why" line, then the probe (`r` reveals it, then ✓/✗ spotted). Buttons appear only when there's content: `▸ more` (m), `💬 comment` (c), `💡 lesson` (l). Below them, the diff with pinned notes.
- **Comment panel:** current lines vs. the suggestion as a mini-diff, the body, **Copy**, and **Open on GitHub ↗**.
- **Wrap-up:** verdict, spotted X of Y (with missed steps linked), Takeaways, all comments (Copy each / **Copy all**), and open questions.
- **Keys:** `j`/`k` move, `space` "got it" (progress bar), `t` theme. State is saved per PR in localStorage.

## Rules

- Read-only: never commit, push, comment on or approve the PR from this skill.
- Don't publish the page (it contains private code) unless asked.
