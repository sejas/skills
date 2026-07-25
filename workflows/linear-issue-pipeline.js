export const meta = {
  name: "linear-issue-pipeline",
  description:
    "Work a Linear issue end-to-end: worktree, plan, implement, review, verify, finalize",
  whenToUse:
    'User asks to autonomously work a STU-* issue, e.g. "run linear-issue-pipeline for STU-1234" (add "and push" for a draft PR)',
  phases: [
    {
      title: "Setup",
      detail:
        "fetch issue + triage size (haiku), worktree (haiku), explore (sonnet)",
    },
    {
      title: "Plan",
      detail: "plan markdown — separate agent only for large issues (fable)",
    },
    {
      title: "Implement",
      detail: "implement + commit; opus for large, sonnet for small",
      model: "opus/sonnet",
    },
    {
      title: "Review",
      detail: "simplify, convention check, comment cleanup, commit (fable)",
    },
    {
      title: "Verify",
      detail:
        "lint, typecheck, tests + parallel screenshots; fix loop (sonnet)",
    },
    {
      title: "Finalize",
      detail: "update plan with reality; optional push + draft PR",
    },
  ],
};

// Some harnesses deliver args as a JSON string instead of an object.
if (typeof args === "string") {
  try {
    args = JSON.parse(args);
  } catch (e) {
    throw new Error(`args arrived as unparseable string: ${args}`);
  }
}
if (!args || !args.issue) {
  throw new Error(
    'args required: { issue: "STU-1234", push: false, assignee: "", repo: "", worktree: "", plan: "" }',
  );
}

const issueId = String(args.issue).toUpperCase();
const push = !!args.push;
const assignee = args.assignee || "";
const team = args.team || "Studio App & CLI";
// Absolute repo path is optional: without it, agents resolve the repo from their cwd.
const REPO = args.repo || "";
const repoRef =
  REPO ||
  "the git repo at the current working directory (`git rev-parse --show-toplevel`)";
const PLANS = "~/claude.nosync/plans";
const ARTIFACTS = "~/claude.nosync/agents";
const WORKTREES = "~/worktrees.nosync";

function must(value, what) {
  if (!value) {
    throw new Error(
      `STOPPING: ${what}. Inspect the workflow transcript, then re-run with Workflow({scriptPath, resumeFromRunId}) to reuse the steps that already completed.`,
    );
  }
  return value;
}

// ---- Setup: fetch + triage, then worktree (slow) overlapped with explore + plan ----
phase("Setup");
log(`Fetching ${issueId} from Linear`);

const issue = await agent(
  `Fetch Linear issue ${issueId} (WordPress Studio, team "${team}").
Use ToolSearch to load mcp__claude_ai_Linear__get_issue and mcp__claude_ai_Linear__list_comments (fall back to the context-a8c linear provider if unavailable).
Read the description, all comments, and any linked PRs/attachments mentioned.
Return: fetched=true plus title; summary (self-contained problem statement including key detail from comments — the reader has NO other context); acceptance (explicit or inferred "done means" criteria); branchName following the convention lowercase-issue-id-plus-verb-slug, e.g. "stu-1234-fix-login-crash"; and size, an honest estimate of the change: "trivial" (one file, e.g. a copy/CSS/config tweak), "small" (2-4 files, one clear code path, no new architecture), "large" (multiple layers, new IPC handler/state/dependency, or the approach is genuinely unclear from the issue).
If you CANNOT read the issue for any reason (tools unavailable, auth failure, issue not found, empty description) do NOT guess or invent content — return fetched=false and put the exact reason in error.`,
  {
    label: `fetch:${issueId}`,
    phase: "Setup",
    model: "haiku",
    effort: "low",
    schema: {
      type: "object",
      required: [
        "fetched",
        "title",
        "summary",
        "acceptance",
        "branchName",
        "size",
        "error",
      ],
      properties: {
        fetched: { type: "boolean" },
        title: { type: "string" },
        summary: { type: "string" },
        acceptance: { type: "array", items: { type: "string" } },
        branchName: { type: "string" },
        size: { type: "string", enum: ["trivial", "small", "large"] },
        error: {
          type: "string",
          description: "why the issue could not be read; empty if fetched",
        },
      },
    },
  },
);
if (!issue) {
  throw new Error(
    `STOPPING: the agent fetching ${issueId} died before returning — Linear issue could not be read. Nothing was created. Check Linear MCP connection and retry.`,
  );
}
if (!issue.fetched || !issue.summary.trim()) {
  throw new Error(
    `STOPPING: could not read Linear issue ${issueId}: ${
      issue.error || "empty issue content"
    }. Nothing was created — no worktree, no branch, no plan. Fix access to the issue and retry.`,
  );
}
const isLarge = issue.size === "large";
log(`Issue: ${issue.title} | size=${issue.size} → branch ${issue.branchName}`);

// Worktree setup is slow (node_modules). Start it, don't await — explore + plan
// run while it copies. args.worktree skips it entirely when re-running an issue.
const wtPromise = args.worktree
  ? Promise.resolve({ path: args.worktree, branch: issue.branchName })
  : agent(
      `Create a git worktree of ${repoRef} for a new branch based on origin/trunk. Run these commands and little else:

1. \`git fetch origin trunk\`
2. Pick BRANCH="${issue.branchName}"; if that branch or ${WORKTREES}/${issue.branchName} already exists, append a "-$(date +%m%d%H)" suffix to both.
3. \`mkdir -p ${WORKTREES} && git worktree add ${WORKTREES}/$BRANCH -b $BRANCH origin/trunk\`
4. Copy every node_modules directory so the worktree builds without npm install. On APFS \`cp -c\` clones instead of copying bytes (instant, no extra disk) — fall back to a plain copy if it fails:
\`\`\`
SRC=$(git rev-parse --show-toplevel); WT=${WORKTREES}/$BRANCH
cd "$SRC" && find . -maxdepth 4 -name node_modules -type d -not -path "*/node_modules/*" | while read -r nm; do
  mkdir -p "$WT/$(dirname "$nm")"
  cp -Rc "$SRC/$nm" "$WT/$nm" 2>/dev/null || cp -R "$SRC/$nm" "$WT/$nm"
done
\`\`\`
Do not ask questions, do not modify the source working tree, do not run npm install. Return the absolute worktree path (expanded, no "~") and the branch name actually used.`,
      {
        label: "worktree",
        phase: "Setup",
        model: "haiku",
        effort: "low",
        schema: {
          type: "object",
          required: ["path", "branch"],
          properties: { path: { type: "string" }, branch: { type: "string" } },
        },
      },
    );

const map = must(
  await agent(
    `Read-only exploration of the WordPress Studio repo at ${repoRef} (Electron app: main process apps/studio/src, renderer components/hooks/stores, CLI apps/cli, agentic UI apps/ui, shared packages/common).
Task context — Linear issue ${issueId}: ${issue.title}
${issue.summary}

Return:
- files: the files most relevant to this issue (path + one line why) — be precise, an implementer will work from this list instead of searching again.
- patterns: the existing conventions the fix must follow, and similar prior implementations worth imitating (name the file).
- risks: gotchas (IPC boundaries, config-file locking, dark-mode token rules per app, main-vs-renderer separation).
- alreadyFixed: true ONLY if the issue's symptom is already handled on origin/trunk (check \`git log\` and the actual code).
- priorArt: existing features/helpers that overlap what this issue asks for — anything that would make the fix a duplicate.
- conflicts: in-flight or recent work that clashes with this change (recent commits, adjacent refactors).
- evidence: one paragraph backing alreadyFixed/priorArt/conflicts, citing files and commits.`,
    {
      label: "explore",
      phase: "Setup",
      agentType: "Explore",
      model: "sonnet",
      effort: "medium",
      schema: {
        type: "object",
        required: [
          "files",
          "patterns",
          "risks",
          "alreadyFixed",
          "priorArt",
          "conflicts",
          "evidence",
        ],
        properties: {
          files: {
            type: "array",
            items: {
              type: "object",
              required: ["path", "why"],
              properties: { path: { type: "string" }, why: { type: "string" } },
            },
          },
          patterns: { type: "array", items: { type: "string" } },
          risks: { type: "array", items: { type: "string" } },
          alreadyFixed: { type: "boolean" },
          priorArt: { type: "array", items: { type: "string" } },
          conflicts: { type: "array", items: { type: "string" } },
          evidence: { type: "string" },
        },
      },
    },
  ),
  "exploration agent died — no codebase map, so implementation would be guesswork",
);

// Abort before the expensive phases if the issue is already resolved.
if (map.alreadyFixed) {
  const wtEarly = await wtPromise;
  return {
    issue: issueId,
    title: issue.title,
    stopped: "alreadyFixed",
    evidence: map.evidence,
    priorArt: map.priorArt,
    worktree: wtEarly ? wtEarly.path : "",
    note: "Exploration found this already handled on trunk. No plan, no implementation. Verify the evidence and close the issue, or re-run with a corrected issue description.",
  };
}
if (map.priorArt.length || map.conflicts.length) {
  log(
    `⚠ Overlap found — priorArt: ${
      map.priorArt.join("; ") || "none"
    } | conflicts: ${map.conflicts.join("; ") || "none"}`,
  );
}

// ---- Plan (separate agent only when the issue is genuinely large) ----
const planSections = `# <title>  |  ## Problem  |  ## Approach (and alternatives rejected, one line each)  |  ## Steps (each: files to touch, what changes)  |  ## Done means (testable acceptance criteria)  |  ## Verification plan (exact commands: eslint, typecheck, which tests; whether UI screenshots apply — apps/ui is screenshotable via "npm run cli:build:ui && node apps/cli/dist/cli/main.mjs ui --no-open" at http://localhost:8081, apps/studio is NOT headless-verifiable)`;
const planPathFor = `${PLANS}/$(date +%F)-${issue.branchName}.md`;

let plan = args.plan
  ? { planPath: args.plan, approach: "(plan supplied via args)" }
  : null;
if (!plan && isLarge) {
  phase("Plan");
  plan = must(
    await agent(
      `Write an implementation plan for Linear issue ${issueId} in the WordPress Studio repo (${repoRef}).

Issue: ${issue.title}
${issue.summary}
Acceptance criteria: ${JSON.stringify(issue.acceptance)}

Codebase map from exploration (verify anything you rely on by reading the files):
${JSON.stringify(map, null, 2)}

Save the plan to ${planPathFor} (run \`date +%F\` for the date) with sections:
${planSections}.
Prefer the smallest change that resolves the issue; no speculative abstractions. Return the plan path and a 3-line approach summary.`,
      {
        label: "plan",
        phase: "Plan",
        model: "fable",
        effort: "high",
        schema: {
          type: "object",
          required: ["planPath", "approach"],
          properties: {
            planPath: { type: "string" },
            approach: { type: "string" },
          },
        },
      },
    ),
    "planning agent died",
  );
}

const wt = await wtPromise;
if (!wt || !wt.path)
  throw new Error(
    "STOPPING: worktree creation failed — check the worktree agent output",
  );
log(
  `Worktree ready: ${wt.path}${
    plan
      ? ` | Plan: ${plan.planPath}`
      : ` | ${issue.size} issue — implementer writes its own short plan`
  }`,
);

// ---- Implement ----
// Model scales with the triaged size; the map is passed inline so the (expensive)
// implementer never re-discovers what exploration already found.
phase("Implement");
const impl = must(
  await agent(
    `Implement Linear issue ${issueId} in the git worktree at ${
      wt.path
    } (branch ${wt.branch}). Work ONLY inside this worktree.

Issue: ${issue.title}
${issue.summary}
Done means: ${JSON.stringify(issue.acceptance)}

${
  plan
    ? `Read the full plan at ${plan.planPath} and follow it.`
    : `No separate plan agent ran (issue triaged as "${issue.size}"). BEFORE coding, write a short plan (20 lines max) to ${planPathFor} with sections:\n${planSections}.`
}

Codebase map from exploration — start from this instead of re-searching:
${JSON.stringify(map, null, 2)}

Rules: follow AGENTS.md conventions (dark-mode color tokens per app, config-file locking, async IPC handlers, i18n). Smallest diff that satisfies the acceptance criteria. Add/extend a test when the change is non-trivial logic.
Run \`npx eslint --fix\` on the files you touched. Do NOT run npm run typecheck or the test suite — a later verification phase owns that gate and re-running it here wastes minutes.
You ARE authorized to commit in this worktree (this workflow's explicit purpose). Single-line message: "fix: ${issueId} <what and why>". Do NOT push.
Return commit hash(es), changed files, the plan path you used or wrote, and notes on any deviation from the plan and why.`,
    {
      label: "implement",
      phase: "Implement",
      model: isLarge ? "opus" : "sonnet",
      effort: isLarge ? "high" : "medium",
      schema: {
        type: "object",
        required: ["commits", "filesChanged", "planPath", "notes"],
        properties: {
          commits: { type: "array", items: { type: "string" } },
          filesChanged: { type: "array", items: { type: "string" } },
          planPath: { type: "string" },
          notes: { type: "string" },
        },
      },
    },
  ),
  "implementation agent died — the worktree may hold partial work, inspect it before re-running",
);
const planPath = (plan && plan.planPath) || impl.planPath;
log(
  `Implemented: ${impl.filesChanged.length} files, commits ${
    impl.commits.join(", ") || "(none reported)"
  }`,
);

// ---- Review ----
phase("Review");
const review = (await agent(
  `Senior review of the changes for Linear issue ${issueId} in worktree ${wt.path} (branch ${wt.branch}). The plan is at ${planPath}; implementer notes: ${impl.notes}

Review \`git diff origin/trunk...HEAD\` for: bugs and logic errors; violations of AGENTS.md conventions (especially --color-frame-* vs --wpds-color-* token rules per app, config locking, async IPC); over-engineering — simplify aggressively where behavior is preserved (delete unneeded abstractions, prefer the shorter equivalent); comment cleanup — rewrite comments to be concise, delete any comment that narrates what the code does or why the change was made (keep only non-obvious rationale/gotchas, matching surrounding density).

APPLY the improvements directly (don't just report). Then \`npx eslint --fix\` on touched files and commit "fix: ${issueId} review simplifications" (only if you changed something). Do NOT run npm run typecheck or the test suite — the verification phase right after you owns that gate. Do NOT push.
Return whether you changed anything, the full list of files the branch now changes (\`git diff origin/trunk...HEAD --name-only\`), the improvements applied, and any remaining concerns you chose not to fix (with reasons).`,
  {
    label: "review",
    phase: "Review",
    model: "fable",
    effort: "medium",
    schema: {
      type: "object",
      required: ["changed", "filesChanged", "improvements", "concerns"],
      properties: {
        changed: { type: "boolean" },
        filesChanged: { type: "array", items: { type: "string" } },
        improvements: { type: "array", items: { type: "string" } },
        concerns: { type: "array", items: { type: "string" } },
      },
    },
  },
)) || {
  changed: false,
  filesChanged: [],
  improvements: [],
  concerns: ["review agent died — changes are unreviewed"],
};
log(
  `Review: ${review.improvements.length} improvements, ${review.concerns.length} open concerns`,
);

// ---- Verify (test-runner fixes failures itself; 2 rounds max) ----
phase("Verify");
const changedFiles = Array.from(
  new Set([...impl.filesChanged, ...review.filesChanged]),
);
const touchesUi = changedFiles.some((f) => f.includes("apps/ui/"));
const touchesStudioUi = changedFiles.some(
  (f) =>
    f.includes("apps/studio/src/components") ||
    f.includes("apps/studio/src/index.css"),
);

const shotsPrompt = `Capture UI screenshots for Linear issue ${issueId} in worktree ${wt.path} (the agentic UI, apps/ui, changed).
Run "npm run cli:build:ui && node apps/cli/dist/cli/main.mjs ui --no-open", open http://localhost:8081 with Playwright (load the tools via ToolSearch), capture the screens affected by this change — ${issue.title}: ${issue.summary} — in BOTH light and dark themes, save PNGs to ${ARTIFACTS}/${issue.branchName}/, then stop the server. Change nothing in the repo, commit nothing.
Return the screenshot paths and anything that looks visually wrong.`;
const shotsOpts = {
  label: "screenshots",
  phase: "Verify",
  model: "sonnet",
  effort: "low",
  schema: {
    type: "object",
    required: ["screenshots", "observations"],
    properties: {
      screenshots: { type: "array", items: { type: "string" } },
      observations: { type: "string" },
    },
  },
};

let verify = null;
let shots = null;
let roundsUsed = 0;
for (let round = 1; round <= 2; round++) {
  roundsUsed = round;
  const gate = () =>
    agent(
      `Verification round ${round} for Linear issue ${issueId} in worktree ${
        wt.path
      }.
Changed files (\`git diff origin/trunk...HEAD --name-only\` is the source of truth): ${JSON.stringify(
        changedFiles,
      )}
${
  round > 1 && verify
    ? `Round ${round - 1} FAILED with: ${JSON.stringify(
        verify.failures,
      )}\nFix those first and re-run just them, then run the full gate below once to confirm nothing else broke.`
    : ""
}

1. \`npx eslint <changed files>\` — must be clean.
2. \`npm run typecheck\` — must pass.
3. \`npm test -- <test paths covering the changed files>\` — must pass. Report testsRun, the actual number of test cases executed. If your path selection matches no tests, that is NOT a pass: either find the right paths, or report testsRun=0 and state explicitly that no test covers this change.
If anything fails: fix it, re-run, and commit fixes as "fix: ${issueId} test fixes". Do NOT push.
${
  touchesStudioUi
    ? 'This diff touches apps/studio UI — do NOT attempt screenshots (Electron, not headless-verifiable). Note "needs human visual review in light + dark" in the summary.'
    : ""
}
Return passed (true only if 1-3 are all green), a summary, testsRun, and remaining failures.`,
      {
        label: `verify:round${round}`,
        phase: "Verify",
        agentType: "test-runner",
        model: "sonnet",
        effort: "medium",
        schema: {
          type: "object",
          required: ["passed", "summary", "testsRun", "failures"],
          properties: {
            passed: { type: "boolean" },
            summary: { type: "string" },
            testsRun: { type: "number" },
            failures: { type: "array", items: { type: "string" } },
          },
        },
      },
    );

  // Screenshots don't depend on the test gate — run them alongside round 1.
  if (round === 1 && touchesUi) {
    const [gateRes, shotRes] = await parallel([
      gate,
      () => agent(shotsPrompt, shotsOpts),
    ]);
    verify = gateRes;
    shots = shotRes;
  } else {
    verify = await gate();
  }

  if (verify && verify.passed) break;
  log(
    `Verify round ${round} failed: ${
      verify ? verify.failures.join("; ") : "agent died"
    }`,
  );
}
// Fix commits from round 2 invalidate round 1's screenshots.
if (touchesUi && roundsUsed > 1) {
  shots =
    (await agent(shotsPrompt, {
      ...shotsOpts,
      label: "screenshots:recapture",
    })) || shots;
}
const screenshots = shots ? shots.screenshots : [];
const verifyPassed = !!(verify && verify.passed && verify.testsRun > 0);

// ---- Finalize ----
phase("Finalize");
const finalReport = await agent(
  `Finalize Linear issue ${issueId}. Worktree: ${wt.path}, branch ${wt.branch}.

1. Update the plan at ${planPath}: append an "## Implementation notes" section written for a human reader — what was ACTUALLY built (vs planned, per these notes: ${
    impl.notes
  }), tradeoffs taken, review improvements (${JSON.stringify(
    review.improvements,
  )}), open concerns (${JSON.stringify(
    review.concerns,
  )}), verification results (${
    verify ? verify.summary : "verification agent failed"
  }; passed: ${verifyPassed}, tests run: ${
    verify ? verify.testsRun : 0
  }), screenshot paths ${JSON.stringify(screenshots)}${
    shots && shots.observations
      ? ` and visual observations: ${shots.observations}`
      : ""
  }${
    map.priorArt.length || map.conflicts.length
      ? `, and an "Overlaps found" note: priorArt ${JSON.stringify(
          map.priorArt,
        )}, conflicts ${JSON.stringify(map.conflicts)}`
      : ""
  }. Plain prose, no jargon, no file-by-file listing.
${
  push
    ? `2. Push branch ${
        wt.branch
      } to origin and create a DRAFT PR against trunk with gh, following .github/PULL_REQUEST_TEMPLATE.md (Related issues: link ${issueId}; Proposed Changes: intent and user impact only; Testing Instructions from the plan's verification section).${
        assignee ? ` Assign the PR to ${assignee}.` : ""
      } If verification did not pass, say so prominently in the PR body.${
        touchesStudioUi
          ? ' Add the line: "> ⚠️ Visual change: needs human review in light + dark mode."'
          : ""
      } Return the PR URL.`
    : "2. Do NOT push or create a PR (not requested). Return prUrl as an empty string."
}`,
  {
    label: "finalize",
    phase: "Finalize",
    model: push ? "fable" : "haiku",
    effort: push ? "medium" : "low",
    schema: {
      type: "object",
      required: ["planUpdated", "prUrl"],
      properties: {
        planUpdated: { type: "boolean" },
        prUrl: { type: "string" },
      },
    },
  },
);

return {
  issue: issueId,
  title: issue.title,
  size: issue.size,
  worktree: wt.path,
  branch: wt.branch,
  plan: planPath,
  planUpdated: !!(finalReport && finalReport.planUpdated),
  commits: impl.commits,
  reviewImprovements: review.improvements,
  openConcerns: review.concerns,
  priorArt: map.priorArt,
  conflicts: map.conflicts,
  verificationPassed: verifyPassed,
  verificationSummary: verify ? verify.summary : "verify agent failed",
  testsRun: verify ? verify.testsRun : 0,
  verificationRounds: roundsUsed,
  screenshots,
  pr: finalReport ? finalReport.prUrl : "",
};
