---
name: release-notes
description: Use when writing or polishing release notes for a version from a list of merged PRs (e.g. RELEASE-NOTES.txt, CHANGELOG). Produces concise, user-facing, thematically grouped notes where every line covers one coherent change and every PR is cited exactly once, with scripted verification.
---

# Polished Release Notes

Turn a list of merged PRs into release notes where each line is concise, user-facing, and cites only truly related PRs. Never grab-bag unrelated fixes into one line.

## Workflow

### 1. Collect the PR set

- If a draft section already exists in the notes file, extract every `#NNNN` from it — that is the authoritative PR set.
- Otherwise list merges since the last release tag: `git log <last-tag>..HEAD --oneline | grep -oE '#[0-9]+'`. This also matches issue refs in commit subjects ("fixes #123") — sanity-check each number resolves to a merged PR via `gh pr view` before treating the set as authoritative.
- Fetch titles: `gh pr view <num> --json title,body`. Fetch bodies only for PRs whose title is ambiguous.
- Optional version column: `git tag --contains $(gh pr view <num> --json mergeCommit -q .mergeCommit.oid) | sort -V | head -1` gives the first tag containing each PR.

### 2. Draft (3 angles via subagents, or single-pass for small sets)

For >15 PRs, launch 3 parallel subagents, each drafting the full list from a different angle, then pick/synthesize:

- **Impact-first**: each line answers "what changed for me as a user?"
- **Minimalist**: shortest lines, split aggressively, multi-PR lines only for a feature + its direct follow-up
- **Grouped** (usually the winner): headline feature first, then cluster by product area; one bullet per coherent sub-theme

Each agent prompt MUST include: the full PR number→title list, the output format rules below, the style reference (3–5 lines quoted from the previous release section), and the instruction to end with a self-check line (`Check: N/N PRs used, no duplicates`). Agents may run read-only `gh pr view`; they must not edit files or post to GitHub.

For ≤15 PRs, draft the grouped angle directly yourself.

### 3. Line rules

- Format: `* Sentence #NNNN, #NNNN` — PR refs at end, comma-separated, match the file's existing conventions exactly (trailing period or not, prefix labels like `Studio Code:`, heading style).
- One coherent theme per line. Related PRs together (feature + follow-up fix, N PRs of one visual cleanup). Unrelated PRs never merged — no "and other improvements" grab-bags.
- Plain user-facing language. No implementation jargon (IPC, daemon socket, mu-plugins) unless the audience is developers and there is no user-visible phrasing.
- Order: headline feature → other features → improvements → fixes → maintenance/deps.
- Keep product names and established terms exactly as the project writes them.

### 4. Verify (mandatory before applying)

Every PR appears exactly once — check by script, never by eye. Usage: `python3 check.py <notes-section.txt> <expected-prs.txt>`, where the expected file holds bare PR numbers (no `#`), whitespace-separated — e.g. built with `grep -oE '#[0-9]+' old-section.txt | tr -d '#' | sort -u > expected-prs.txt`:

```python
import re, sys
expected = {n.lstrip('#') for n in open(sys.argv[2]).read().split()}
nums = re.findall(r'#(\d+)', open(sys.argv[1]).read())
assert len(nums) == len(set(nums)), f"duplicates: {sorted(n for n in nums if nums.count(n)>1)}"
assert set(nums) == expected, f"missing: {sorted(expected-set(nums))} extra: {sorted(set(nums)-expected)}"
print(f"OK {len(nums)}/{len(expected)}")
```

Do not trust a subagent's self-reported check — re-run the script on the final text yourself.

### 5. Apply

- Replace only the target version's section in the notes file.
- Re-run the verification script against the file section after editing.
- Do not commit unless the user asks.

## Pitfalls

- A reworded line silently dropping one PR of a group — the script catches this; run it after every edit.
- Copying a subagent draft that added trailing periods or headings the file doesn't use — match the file, not the agent.
- Bundling a "polish" mega-line: if a line needs "and other details" to close, split it.
