---
name: ai-radar
description: Use when Antonio wants to catch up on frontier AI — "what's new in AI", "AI radar", "what is karpathy working on", "AI trends", "research digest", "what should I learn next", "where to invest learning time", or /ai-radar.
---

# AI Radar

## Overview

Scan frontier AI sources → distill into **pills** (short, digestible units) → recommend what to adopt into workflows and where to invest learning time. Everything filtered through the Relevance Lens below — not general hype.

## Workflow

1. **Check history.** List the output dir (see Output), skim the latest report. Don't repeat pills already covered unless there's a major update.
2. **Fan-out.** Launch parallel research agents (general-purpose, one per bucket in [sources.md](sources.md)): researchers, labs, papers, repos & community. Each agent returns raw findings: `item | date | url | one-line what | why notable`. Restrict to items from the last ~6 weeks. A source with nothing in-window → agent reports `source quiet this window` (plus its most recent notable item, dated) instead of padding with stale coverage.
3. **Filter & rank.** Dedupe against history. Score each candidate against the Relevance Lens. Keep 5–8. Stale-but-newly-actionable items: orchestrator's call at this step, never the fan-out agents'.
4. **Write pills** using the Pill Format contract. Assemble the report in the Report Shape.
5. **Save + summarize.** Write the report file, show the TL;DR in chat with the file path.

## Pill Format (contract — every pill has exactly these slots)

```markdown
### 💊 <Name>
- **What:** one sentence.
- **Who/where:** person or lab + link.
- **Why care:** ≤2 sentences, concrete — what changes because of this.
- **For me:** Adopt | Experiment | Watch | Skip — one line tying it to the Relevance Lens. E.g. `Adopt — trim over-prescriptive examples from CLAUDE.md; maps onto the Claude Code skills lens.`
- **Go deeper:** the single best resource (link) + rough hours if it's learnable; `n/a` allowed for Watch/Skip news items.
```

## Report Shape

1. **TL;DR** — 3 bullets.
2. **Pills** — 5–8, ordered by relevance (Adopt first, Skip last).
3. **Adopt this week** — max 3 concrete actions ("add X to Claude Code workflow", "try Y on Studio side project").
4. **Learning bets** — ranked: "invest ~N hrs in Y because Z". Max 3.
5. **Sources checked** — bullet list of what was actually scanned (so gaps are visible).

## Relevance Lens (Antonio)

- WordPress Studio: Electron, React/TS, local dev tooling
- PHP-WASM / WordPress Playground
- Claude Code: skills, subagents, MCP, multi-agent orchestration
- LLM-assisted creation: writing, comics/images, research automation
- Personal automation & second-brain (Obsidian vault)

A paper with no plausible path into one of these = **Watch** or **Skip**, however famous the author.

## Output

- Inside the Obsidian vault repo: `📚 knowledge/ai-radar/YYYY-MM-DD.md` with frontmatter `type: ai-radar`, `date: YYYY-MM-DD`, `tags: [ai-radar]`.
- Anywhere else: `~/claude.nosync/digests/ai-radar/YYYY-MM-DD.md`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Listing 20 papers | Hard cap 8 pills. Radar, not survey. |
| "Why care" restates the abstract | Say what the reader can *do* differently. |
| Every pill = Adopt | Most frontier work = Watch. Adopt is rare and concrete. |
| Stale items | 6-week window. Older only if it just became actionable. |
| Skipping history check | Repeat pills waste the whole report. |
