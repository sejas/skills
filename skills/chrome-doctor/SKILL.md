---
name: chrome-doctor
description: Use when Claude in Chrome doesn't work or the user wants Claude to drive their real Chrome — "chrome doesn't work", "browser tools missing", "it fails from T3", "troubleshoot chrome", "control my browser", or /chrome-doctor [task]. Diagnoses why the mcp__claude-in-chrome__* tools are missing or failing (headless/T3 launches without --chrome, extension not connected, wrong browser), fixes what it can, then runs the optional task in their Chrome.
---

# Chrome doctor

Diagnose Claude in Chrome, then do the task (if one was given) in the user's real Chrome.

## 1. Are the tools in this session?

Run `ToolSearch` with `select:mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_close_mcp`.

**No tools come back** → the session was started without Chrome. The usual cause is that headless launches (`claude -p`, `--input-format stream-json`), which is how **T3 Code** spawns Claude, skip Chrome unless `--chrome` is passed. `claudeInChromeDefaultEnabled` only covers interactive sessions. Check the launch flags:

```sh
ps -o args= -p $PPID; ps -ax -o args= | grep -E '^claude .*stream-json' | head -3
```

Fix, then stop (the current session can't gain the tools; a new one must start):

- **T3 Code:** Settings → Providers → Claude → *Launch arguments* must contain `--chrome` (T3's settings UI is at `http://127.0.0.1:3773/settings/providers`, port in `~/.t3/userdata/server-runtime.json`). Start a **new** thread afterwards.
- **Terminal:** `claude --chrome`, or `/chrome` → enable.
- Verify headless gets the tools: `claude -p --chrome --model haiku "Any claude-in-chrome tools? YES/NO" </dev/null`.

## 2. Is a browser connected?

Call `list_connected_browsers`.

- **Empty list** → Chrome isn't running, or the extension is signed out or disabled. Ask the user to open Chrome, then click the Claude extension icon and confirm that it's signed in to the same account.
- **One marked `inUse`** → use it.
- **Several, none `inUse`** → ask with AskUserQuestion; never pick one yourself.

## 3. Smoke test

Run a standalone `navigate` to the target URL (or `https://example.com`) **without a `tabId`**. It creates the session's tab group and returns the tab id. Then take a `screenshot` at `scale: 0.5`.

| Symptom | Likely cause → fix |
|---|---|
| Permission / site not allowed | The extension's site permission → the user allows the domain in the extension popup |
| Tab "doesn't exist" | Stale id → call `tabs_context_mcp` and reuse a fresh id |
| Hangs, no response | A JS alert/confirm is open, or the extension service worker is asleep → the user dismisses the dialog or reloads the extension |
| Google login page | Wrong Chrome profile → switch browser (step 2) |

## 4. Do the task

Batch the steps with `browser_batch`, and verify the result with a zoomed screenshot. For Google Sheets, jump to cells through the Name box (click it at the top-left, type `A21`, then press Return) instead of clicking the grid. Report what changed and where. Close the tab when done unless the user wants to see it.
