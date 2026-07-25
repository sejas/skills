export const meta = {
  name: "linear-issue-pipeline",
  description:
    "Work a Linear issue end-to-end: worktree, plan, implement, review, verify, finalize",
  whenToUse:
    'User asks to autonomously work a STU-* issue, e.g. "run linear-issue-pipeline for STU-1234" (add "and push" for a draft PR)',
  phases: [
    {
      title: "Setup",
      detail: "fetch issue (haiku), create worktree (sonnet), explore code",
    },
    { title: "Plan", detail: "write plan markdown (fable)" },
    { title: "Implement", detail: "implement + commit", model: "opus" },
    {
      title: "Review",
      detail: "review, simplify, clean comments, commit (fable)",
    },
    {
      title: "Verify",
      detail: "lint, typecheck, tests, screenshots; fix loop (test-runner)",
    },
    {
      title: "Finalize",
      detail: "update plan with reality; optional push + draft PR (fable)",
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
  throw new Error('args required: { issue: "STU-1234", push: false }');
}
const issueId = String(args.issue).toUpperCase();
const push = !!args.push;
const REPO = "~/Documents/projects-m3.nosync/studio";
const PLANS = "~/claude.nosync/plans";
const ARTIFACTS = "~/claude.nosync/agents";

// ---- Setup: fetch issue, then worktree (slow) overlapped with explore + plan ----
phase("Setup");
log(`Fetching ${issueId} from Linear`);

const issue = await agent(
  `Fetch Linear issue ${issueId} (WordPress Studio, team "Studio App & CLI").
Use ToolSearch to load mcp__claude_ai_Linear__get_issue and mcp__claude_ai_Linear__list_comments (fall back to the context-a8c linear provider if unavailable).
Read the description, all comments, and any linked PRs/attachments mentioned.
Return: fetched=true plus title; summary (self-contained problem statement including key detail from comments — the reader has NO other context); acceptance (explicit or inferred "done means" criteria); branchName following the convention lowercase-issue-id-plus-verb-slug, e.g. "stu-1234-fix-login-crash".
If you CANNOT read the issue for any reason (tools unavailable, auth failure, issue not found, empty description) do NOT guess or invent content — return fetched=false and put the exact reason in error.`,
  {
    label: `fetch:${issueId}`,
    phase: "Setup",
    model: "haiku",
    schema: {
      type: "object",
      required: [
        "fetched",
        "title",
        "summary",
        "acceptance",
        "branchName",
        "error",
      ],
      properties: {
        fetched: { type: "boolean" },
        title: { type: "string" },
        summary: { type: "string" },
        acceptance: { type: "array", items: { type: "string" } },
        branchName: { type: "string" },
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
    `STOPPING: could not read Linear issue ${issueId}: ${issue.error || "empty issue content"}. Nothing was created — no worktree, no branch, no plan. Fix access to the issue and retry.`,
  );
}
log(`Issue: ${issue.title} → branch ${issue.branchName}`);

// Worktree creation copies node_modules (slow). Start it, don't await —
// explore + plan run while it copies.
const wtPromise = agent(
  `Create a git worktree of the Studio repo at ${REPO} for NEW branch "${issue.branchName}" based on origin/trunk (fetch first). Place it at ~/worktrees.nosync/${issue.branchName} and copy node_modules per the usual worktree conventions. Return the absolute worktree path and branch name.`,
  {
    label: "worktree",
    phase: "Setup",
    model: "sonnet",
    agentType: "worktree-creator",
    schema: {
      type: "object",
      required: ["path", "branch"],
      properties: { path: { type: "string" }, branch: { type: "string" } },
    },
  },
);

const map = await agent(
  `Read-only exploration of the WordPress Studio repo at ${REPO} (Electron app: main process apps/studio/src, renderer components/hooks/stores, CLI apps/cli, agentic UI apps/ui, shared packages/common).
Task context — Linear issue ${issueId}: ${issue.title}
${issue.summary}
Find and return: the files most relevant to this issue (path + one line why), the existing patterns/conventions the fix should follow, similar prior implementations to imitate, and risks/gotchas (IPC boundaries, config-file locking, dark-mode token rules, main-vs-renderer context separation).`,
  {
    label: "explore",
    phase: "Setup",
    agentType: "Explore",
    schema: {
      type: "object",
      required: ["files", "patterns", "risks"],
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
      },
    },
  },
);

// ---- Plan ----
phase("Plan");
const plan = await agent(
  `Write an implementation plan for Linear issue ${issueId} in the WordPress Studio repo (${REPO}).

Issue: ${issue.title}
${issue.summary}
Acceptance criteria: ${JSON.stringify(issue.acceptance)}

Codebase map from exploration (verify anything you rely on by reading the files):
${JSON.stringify(map, null, 2)}

Run \`date +%F\` for today's date and save the plan to ${PLANS}/<date>-${issue.branchName}.md with sections:
# <title>  |  ## Problem  |  ## Approach (and alternatives rejected, one line each)  |  ## Steps (each: files to touch, what changes)  |  ## Done means (testable acceptance criteria)  |  ## Verification plan (exact commands: eslint, typecheck, which tests; whether UI screenshots apply — apps/ui is screenshotable via "npm run cli:build:ui && node apps/cli/dist/cli/main.mjs ui --no-open" at http://localhost:8081, apps/studio is NOT headless-verifiable).
Prefer the smallest change that resolves the issue; no speculative abstractions. Return the plan path and a 3-line approach summary.`,
  {
    label: "plan",
    phase: "Plan",
    model: "fable",
    schema: {
      type: "object",
      required: ["planPath", "approach"],
      properties: {
        planPath: { type: "string" },
        approach: { type: "string" },
      },
    },
  },
);

const wt = await wtPromise;
if (!wt || !wt.path)
  throw new Error("Worktree creation failed — check worktree agent output");
log(`Worktree ready: ${wt.path} | Plan: ${plan.planPath}`);

// ---- Implement ----
phase("Implement");
const impl = await agent(
  `Implement Linear issue ${issueId} in the git worktree at ${wt.path} (branch ${wt.branch}). Work ONLY inside this worktree.

First read the full plan at ${plan.planPath} and follow it. Issue summary for reference:
${issue.title} — ${issue.summary}
Done means: ${JSON.stringify(issue.acceptance)}

Rules: follow AGENTS.md conventions (dark-mode color tokens per app, config-file locking, async IPC handlers, i18n). Smallest diff that satisfies the acceptance criteria. Add/extend a test when the change is non-trivial logic.
Before committing: npx eslint --fix <modified files>, npm run typecheck, npm test -- <affected test paths>.
You ARE authorized to commit in this worktree (this workflow's explicit purpose). Single-line message: "fix: ${issueId} <what and why>". Do NOT push.
Return commit hash(es), changed files, and notes on any deviation from the plan and why.`,
  {
    label: "implement",
    phase: "Implement",
    model: "opus",
    schema: {
      type: "object",
      required: ["commits", "filesChanged", "notes"],
      properties: {
        commits: { type: "array", items: { type: "string" } },
        filesChanged: { type: "array", items: { type: "string" } },
        notes: { type: "string" },
      },
    },
  },
);
log(
  `Implemented: ${impl.filesChanged.length} files, commits ${impl.commits.join(", ")}`,
);

// ---- Review ----
phase("Review");
const review = await agent(
  `Senior review of the changes for Linear issue ${issueId} in worktree ${wt.path} (branch ${wt.branch}). The plan is at ${plan.planPath}; implementer notes: ${impl.notes}

Review \`git diff origin/trunk...HEAD\` for: bugs and logic errors; violations of AGENTS.md conventions (especially --color-frame-* vs --wpds-color-* token rules per app, config locking, async IPC); over-engineering — simplify aggressively where behavior is preserved (delete unneeded abstractions, prefer the shorter equivalent); comment cleanup — rewrite comments to be concise, delete any comment that narrates what the code does or why the change was made (keep only non-obvious rationale/gotchas, matching surrounding density).

APPLY the improvements directly (don't just report). Then npx eslint --fix on touched files, npm run typecheck, and commit "fix: ${issueId} review simplifications" (only if you changed something). Do NOT push.
Return whether you changed anything, the list of improvements applied, and any remaining concerns you chose not to fix (with reasons).`,
  {
    label: "review",
    phase: "Review",
    model: "fable",
    schema: {
      type: "object",
      required: ["changed", "improvements", "concerns"],
      properties: {
        changed: { type: "boolean" },
        improvements: { type: "array", items: { type: "string" } },
        concerns: { type: "array", items: { type: "string" } },
      },
    },
  },
);
log(
  `Review: ${review.improvements.length} improvements, ${review.concerns.length} open concerns`,
);

// ---- Verify (test-runner fixes failures itself; 2 rounds max) ----
phase("Verify");
let verify = null;
for (let round = 1; round <= 2; round++) {
  verify = await agent(
    `Verification round ${round} for Linear issue ${issueId} in worktree ${wt.path}.
Changed files (git diff origin/trunk...HEAD --name-only is the source of truth): ${JSON.stringify(impl.filesChanged)}

1. npx eslint <changed files> — must be clean.
2. npm run typecheck — must pass.
3. npm test -- <test paths covering the changed files> — must pass.
4. Screenshots, only if the diff touches apps/ui: run "npm run cli:build:ui && node apps/cli/dist/cli/main.mjs ui --no-open", open http://localhost:8081 with Playwright (load tools via ToolSearch), capture the changed screens in BOTH light and dark themes, save PNGs to ${ARTIFACTS}/${issue.branchName}/, then stop the server. If the diff touches apps/studio UI instead, do NOT attempt screenshots (Electron, not headless-verifiable) — report "needs human visual review in light + dark".
If anything fails: fix it, re-run, and commit fixes as "fix: ${issueId} test fixes". Do NOT push.
Return passed (true only if 1–3 all green), a summary, screenshot paths (empty array if none), and remaining failures.`,
    {
      label: `verify:round${round}`,
      phase: "Verify",
      agentType: "test-runner",
      schema: {
        type: "object",
        required: ["passed", "summary", "screenshots", "failures"],
        properties: {
          passed: { type: "boolean" },
          summary: { type: "string" },
          screenshots: { type: "array", items: { type: "string" } },
          failures: { type: "array", items: { type: "string" } },
        },
      },
    },
  );
  if (verify && verify.passed) break;
  log(
    `Verify round ${round} failed: ${verify ? verify.failures.join("; ") : "agent died"}`,
  );
}

// ---- Finalize ----
phase("Finalize");
const finalReport = await agent(
  `Finalize Linear issue ${issueId}. Worktree: ${wt.path}, branch ${wt.branch}.

1. Update the plan at ${plan.planPath}: append an "## Implementation notes" section written for a human reader — what was ACTUALLY built (vs planned, per these notes: ${impl.notes}), tradeoffs taken, review improvements (${JSON.stringify(review.improvements)}), open concerns (${JSON.stringify(review.concerns)}), verification results (${verify ? verify.summary : "verification agent failed"}; passed: ${verify ? verify.passed : false}), and screenshot paths ${JSON.stringify(verify ? verify.screenshots : [])}. Plain prose, no jargon, no file-by-file listing.
${push ? `2. Push branch ${wt.branch} to origin and create a DRAFT PR against trunk with gh, following .github/PULL_REQUEST_TEMPLATE.md (Related issues: link ${issueId}; Proposed Changes: intent and user impact only; Testing Instructions from the plan's verification section). Assign the PR to the repo owner. If verification did not pass, say so prominently in the PR body. If the diff touches apps/studio UI add the line: "> ⚠️ Visual change: needs human review in light + dark mode." Return the PR URL.` : "2. Do NOT push or create a PR (not requested). Return prUrl as empty string."}`,
  {
    label: "finalize",
    phase: "Finalize",
    model: "fable",
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
  worktree: wt.path,
  branch: wt.branch,
  plan: plan.planPath,
  commits: impl.commits,
  reviewImprovements: review.improvements,
  openConcerns: review.concerns,
  verificationPassed: verify ? verify.passed : false,
  verificationSummary: verify ? verify.summary : "verify agent failed",
  screenshots: verify ? verify.screenshots : [],
  pr: finalReport ? finalReport.prUrl : "",
};
