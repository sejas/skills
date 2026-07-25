---
name: design-review
description: Designer's-eye QA of a running UI — screenshots it at real breakpoints, then reports spacing, hierarchy, alignment, contrast, state and motion defects ranked by severity, with the CSS/component fix for each. Use when asked to "design review", "review the UI", "does this look right", "make this look less AI-generated", or before shipping a user-facing screen.
allowed-tools: Bash, Read, Edit, Grep, Glob, AskUserQuestion
---

# design-review

Reviews what the user actually sees, not what the code says it should be. A review that
never opened the page is worthless — always capture first.

**Default output is a report, not edits.** Apply fixes only when asked, and re-screenshot
after each one: a fix that wasn't visually re-verified didn't happen.

## 1. Capture

Ask for the URL if it isn't obvious. Then, with the `claude-in-chrome` tools (load them via
ToolSearch first; `playwright` works too if Chrome isn't connected):

1. `tabs_create_mcp` → `navigate` to the URL.
2. Screenshot at **1440×900** (desktop), **768×1024** (tablet) and **390×844** (phone) —
   `resize_window` then `computer` screenshot. Most defects only exist at one width.
3. Screenshot the **states the happy path hides**: hover and focus on the primary control,
   an empty list, a long-string overflow, a loading state, an error. Use `find` +
   `computer` to drive them.
4. `read_console_messages` — a design review that misses a layout-shift warning or a 404
   image is half a review.

Static mockup or Figma export instead of a running app? Read the image and skip to step 2 —
everything in the rubric still applies except the interaction checks.

## 2. Judge

Work through `rubric.md` in this directory. It is the opinionated part: spacing scale,
type scale, hierarchy, alignment, color and contrast, states, motion, and the AI-slop
patterns that make a screen read as machine-made.

Rank every finding:

| Severity | Meaning |
|---|---|
| **blocker** | Unusable or inaccessible — text under 4.5:1 contrast, invisible focus ring, tap target under 44px, content clipped or overlapping |
| **major** | Reads as broken or unfinished — misalignment over 4px, off-scale spacing, competing hierarchy, inconsistent components |
| **minor** | Polish — optical centering, letter-spacing on display type, hover timing |

## 3. Report

Per finding: **what** (one line), **where** (screenshot region + `file:line` of the rule
that causes it), **why it reads wrong** (the principle it breaks), **the fix** (the exact
declaration). Group by severity, blockers first. Nothing else — no praise section, no
summary of what the page does.

Then state, in one line each, what you did NOT check (states you couldn't reach, browsers
you couldn't test) — an unstated gap reads as a pass.

## Gotchas

- **Screenshot before and after every fix.** CSS changes cascade; the third fix routinely
  breaks the first one, and only the pixels prove otherwise.
- **A design system beats your taste.** If the repo has `DESIGN.md`, a tokens file, or a
  Tailwind/theme config, read it first and cite violations against *that* — "not on the
  8px scale" only means something relative to a declared scale.
- **Don't invent a redesign.** The job is finding defects in the intended design, not
  proposing a different one. A "this would look better as cards" finding is out of scope
  unless asked.
- **Contrast gets computed, not eyeballed.** Pull the resolved colors with
  `javascript_tool` (`getComputedStyle`) and compute the ratio; screenshots lie about
  contrast under antialiasing.
- **Zoom to 200% before calling text sizing fine** — it's a WCAG requirement and the
  fastest way to find fixed-height containers that clip.
