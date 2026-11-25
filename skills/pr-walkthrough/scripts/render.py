#!/usr/bin/env python3
"""Render a PR walkthrough page from hunks.json + walkthrough.json.

Usage: render.py <hunks.json> <walkthrough.json> <out.html> [--allow-uncovered]

If findings.json (written by quick-pr-review) sits next to walkthrough.json,
its findings are merged: a step's `"finding": "f1"` becomes that step's
comment + risk, and findings without a file anchor land on the wrap-up page.

If screenshots.json sits there too, every shot with a `before` and/or `after`
image file (paths relative to the work dir) is embedded as a data URI and shown
on the overview's Before / after card. Shots with neither file are listed with
their `skip` reason, so the plan stays visible until the images exist.

Fails (exit 1) on structural problems: no `approach`, unknown hunks/lines, uncovered changed
lines, unplaced findings, >3 lessons, a probe without a watch/concern risk.
Prints warnings (exit 0) when a text field is over its word budget.
"""

import base64
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "template.html")

# Word budgets: concise beats complete. Over budget = warning, not failure.
BUDGET = {"title": 8, "why": 15, "more": 40, "risk": 20, "probe": 20, "lesson": 20,
          "note": 15, "tldr": 30, "verdict": 25, "question": 15, "comment": 80,
          "problem": 20, "approach why": 25, "alternative": 25,
          "blast summary": 25, "surface": 15, "untouched": 15}
MAX_SURFACES = 8
MAX_NOTES = 2
MAX_LESSONS = 3


def words(text):
    prose = re.sub(r"```.*?```", " ", text or "", flags=re.S)  # code doesn't count
    return len(prose.split())


def anchor_url(pr_url, path, line, end_line=None, side="new"):
    """GitHub Files-tab anchor: #diff-<sha256(path)>R<line>[-R<end>] (L for the base side)."""
    s = "L" if side == "old" else "R"
    tail = f"-{s}{end_line}" if end_line and end_line != line else ""
    return f"{pr_url.rstrip('/')}/files#diff-{hashlib.sha256(path.encode()).hexdigest()}{s}{line}{tail}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 3:
        sys.exit(__doc__)
    data = json.load(open(args[0], encoding="utf-8"))
    wt = json.load(open(args[1], encoding="utf-8"))
    fpath = os.path.join(os.path.dirname(os.path.abspath(args[1])), "findings.json")
    findings = json.load(open(fpath, encoding="utf-8")).get("findings", []) if os.path.exists(fpath) else []

    hunks = {h["id"]: h for h in data["hunks"]}
    F = {f["id"]: f for f in findings}
    errors, warns = [], []
    covered = {hid: set() for hid in hunks}
    placed = set()
    lessons = 0
    pr_url = (wt.get("pr") or {}).get("url", "")

    def budget(field, text, where):
        n = words(text)
        if text and n > BUDGET[field]:
            warns.append(f"{where}: {field} is {n} words (budget {BUDGET[field]})")

    # First question of every review: is this the right approach for the problem?
    ap = wt.get("approach") or {}
    if ap.get("fit") not in ("right", "unsure", "wrong"):
        errors.append("top: approach.fit must be right|unsure|wrong (is this the right approach for the problem?)")
    for key in ("problem", "why"):
        if not ap.get(key):
            errors.append(f"top: approach.{key} is required")
    if ap.get("fit") in ("unsure", "wrong") and not ap.get("alternative"):
        errors.append(f"top: approach.fit is {ap['fit']}, so approach.alternative is required")
    budget("problem", ap.get("problem"), "approach")
    budget("approach why", ap.get("why"), "approach")
    budget("alternative", ap.get("alternative"), "approach")

    # Blast range: what else in the codebase and app this change reaches.
    bl = wt.get("blast") or {}
    if bl.get("level") not in ("contained", "moderate", "wide"):
        errors.append("top: blast.level must be contained|moderate|wide (what does this change reach?)")
    if not bl.get("summary"):
        errors.append("top: blast.summary is required")
    surfaces = bl.get("surfaces") or []
    if not surfaces:
        errors.append("top: blast.surfaces needs at least one entry (screen, component, route, API, package)")
    if len(surfaces) > MAX_SURFACES:
        warns.append(f"top: blast has {len(surfaces)} surfaces (max {MAX_SURFACES}); group them")
    for i, sf in enumerate(surfaces):
        if sf.get("kind") not in ("screen", "component", "hook", "api", "data", "package", "config", "other"):
            errors.append(f"blast.surfaces[{i}]: kind must be screen|component|hook|api|data|package|config|other")
        if not sf.get("name") or not sf.get("how"):
            errors.append(f"blast.surfaces[{i}]: name and how are required")
        budget("surface", sf.get("how"), f"blast.surfaces[{i}]")
    budget("blast summary", bl.get("summary"), "blast")
    budget("untouched", bl.get("untouched"), "blast")

    budget("tldr", wt.get("tldr"), "top")
    budget("verdict", wt.get("verdict"), "top")
    for q in wt.get("questions", []):
        budget("question", q, "questions")
    if len(wt.get("questions", [])) > 3:
        warns.append("top: more than 3 questions")

    for ci, chapter in enumerate(wt.get("chapters", [])):
        for si, step in enumerate(chapter.get("steps", [])):
            where = f"step {ci + 1}.{si + 1} ({step.get('title', '?')})"
            shown = {r.get("id") for r in step.get("hunks", [])}
            if not step.get("title"):
                errors.append(f"{where}: needs a title")
            for field in ("title", "why", "more", "probe", "lesson"):
                budget(field, step.get(field), where)

            # Findings from quick-pr-review become the step's comment + default risk.
            if step.get("finding"):
                f = F.get(step["finding"])
                if not f:
                    errors.append(f"{where}: unknown finding {step['finding']}")
                else:
                    placed.add(f["id"])
                    step.setdefault("comment", {k: f.get(k) for k in ("path", "line", "endLine", "side", "body")})
                    step["comment"]["severity"] = f.get("severity", "suggestion")
                    step.setdefault("risk", {"level": "concern" if f.get("severity") == "blocker" else "watch",
                                             "text": f.get("title", "")})

            risk = step.get("risk")
            if risk:
                if risk.get("level") not in ("watch", "concern"):
                    errors.append(f"{where}: risk level must be watch|concern (make an info risk a note)")
                budget("risk", risk.get("text"), where)
            if step.get("probe") and not risk:
                errors.append(f"{where}: a probe needs a watch/concern risk to reveal")
            if step.get("lesson"):
                lessons += 1

            for ref in step.get("hunks", []):
                h = hunks.get(ref.get("id"))
                if not h:
                    errors.append(f"{where}: unknown hunk {ref.get('id')}")
                    continue
                start, end = ref.get("slice", [0, len(h["lines"])])
                if not (0 <= start < end <= len(h["lines"])):
                    errors.append(f"{where}: slice {start}:{end} outside {h['id']} (0:{len(h['lines'])})")
                    continue
                covered[h["id"]].update(range(start, end))

            notes = step.get("notes", [])
            if len(notes) > MAX_NOTES:
                warns.append(f"{where}: {len(notes)} notes (budget {MAX_NOTES})")
            for note in notes:
                h = hunks.get(note.get("hunk"))
                key = "o" if note.get("side") == "old" else "n"
                if not h or not any(l.get(key) == note.get("line") for l in h["lines"]):
                    errors.append(f"{where}: note line {note.get('line')} not found in {note.get('hunk')}")
                elif note.get("hunk") not in shown:
                    errors.append(f"{where}: note on {note.get('hunk')} but the step does not show that hunk")
                budget("note", note.get("text"), where)

            c = step.get("comment")
            if c:
                budget("comment", c.get("body"), where)
                side_key = "o" if c.get("side") == "old" else "n"
                lines_needed = range(c.get("line", -1), (c.get("endLine") or c.get("line", -1)) + 1)
                match = None
                for hid in shown:
                    h = hunks.get(hid)
                    if not h or (c.get("hunk") and c["hunk"] != hid) or (c.get("path") and c["path"] != h["file"]):
                        continue
                    nums = {l.get(side_key) for l in h["lines"] if (l["t"] == "del") == (side_key == "o")}
                    if all(n in nums for n in lines_needed):
                        match = h
                        break
                if not match:
                    errors.append(f"{where}: comment line {c.get('line')} is not a commentable line of a hunk this step shows")
                elif match["collapsed"]:
                    errors.append(f"{where}: comment on a collapsed (generated) file; GitHub hides it")
                else:
                    c["path"] = match["file"]
                    c["hunk"] = match["id"]
                    c["url"] = anchor_url(pr_url, match["file"], c["line"], c.get("endLine"), c.get("side", "new"))
                if "```suggestion" in (c.get("body") or ""):
                    fence = re.search(r"```suggestion\n(.*?)```", c["body"], re.S)
                    if fence and fence.group(1).count("\n") > 12:
                        warns.append(f"{where}: suggestion block over 12 lines; use a plain code fence")

    if lessons > MAX_LESSONS:
        errors.append(f"{lessons} lessons (max {MAX_LESSONS}); keep only the most transferable")

    # Anchored findings must live in a step; unanchored ones go to the wrap-up.
    wt["general"] = []
    for f in findings:
        if f.get("path"):
            if f["id"] not in placed:
                errors.append(f"finding {f['id']} ({f.get('title')}) is anchored to {f['path']} but no step uses it")
        else:
            wt["general"].append({"title": f.get("title", ""), "body": f.get("body", ""),
                                  "severity": f.get("severity", "comment")})

    if "--allow-uncovered" not in sys.argv:
        for hid, h in hunks.items():
            if h["collapsed"]:
                continue
            missing = {i for i, l in enumerate(h["lines"]) if l["t"] != "ctx"} - covered[hid]
            if missing:
                errors.append(f"{hid} ({h['file']}:{h['newStart']}) has {len(missing)} changed lines in no step")

    if errors:
        print("walkthrough.json has problems:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    spath = os.path.join(os.path.dirname(os.path.abspath(args[1])), "screenshots.json")
    if os.path.exists(spath):
        plan = json.load(open(spath, encoding="utf-8"))
        base = os.path.dirname(spath)
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        shots = []
        for shot in plan.get("shots", []):
            out = {k: shot.get(k, "") for k in ("id", "title", "route", "step", "skip", "note")}
            for side in ("before", "after"):
                f = shot.get(side)
                if not f:
                    continue
                fp = os.path.join(base, f)
                ext = os.path.splitext(fp)[1].lower()
                if not os.path.exists(fp) or ext not in mime:
                    errors.append(f"screenshot {shot.get('id')}: {side} file {f} missing or not png/jpg/webp")
                    continue
                out[side] = f"data:{mime[ext]};base64," + base64.b64encode(open(fp, "rb").read()).decode()
            shots.append(out)
        wt["screens"] = {"before": plan.get("before", {}), "after": plan.get("after", {}), "shots": shots}
        if errors:
            print("screenshots.json has problems:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)

    payload = json.dumps({"diff": data, "walkthrough": wt}, ensure_ascii=False).replace("</", "<\\/")
    html = open(TEMPLATE, encoding="utf-8").read()
    title = wt.get("title", "PR walkthrough").replace("<", "&lt;")
    with open(args[2], "w", encoding="utf-8") as fh:
        fh.write(html.replace("__TITLE__", title).replace("__DATA__", payload))
    steps = sum(len(c.get("steps", [])) for c in wt.get("chapters", []))
    for w in warns:
        print(f"  ! {w}")
    shots = (wt.get("screens") or {}).get("shots", [])
    with_img = sum(1 for s in shots if s.get("before") or s.get("after"))
    print(f"wrote {args[2]} — {steps} steps, {len(data['hunks'])} hunks, "
          f"{len(findings)} findings, {lessons} lessons, {len(warns)} budget warnings"
          + (f", {with_img}/{len(shots)} screenshots" if shots else ""))


if __name__ == "__main__":
    main()
