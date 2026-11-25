#!/usr/bin/env python3
"""Parse a unified diff into numbered hunks for a PR walkthrough.

Usage: parse_diff.py <diff-file> <out-hunks.json>

Prints a compact index (one line per hunk) so the author of walkthrough.json
can reference hunk ids without reading the JSON.
"""

import json
import re
import sys

GENERATED_PATTERNS = [
    r"(^|/)drizzle/meta/.*snapshot\.json$",
    r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|composer\.lock|Cargo\.lock|poetry\.lock|Gemfile\.lock)$",
    r"\.min\.(js|css)$",
    r"(^|/)(dist|build|vendor)/",
    r"\.snap$",
    r"(^|/)__generated__/",
    r"\.generated\.",
]
HUGE_FILE_LINES = 1500
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")


def is_generated(path, changed_lines):
    if any(re.search(p, path) for p in GENERATED_PATTERNS):
        return "generated"
    if changed_lines > HUGE_FILE_LINES:
        return "huge"
    return None


def parse(text):
    files = []
    current = None
    hunk = None
    old_no = new_no = 0
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", raw)
            current = {"path": m.group(2) if m else raw[11:], "oldPath": m.group(1) if m else None,
                       "status": "modified", "hunks": [], "binary": False}
            files.append(current)
            hunk = None
            continue
        if current is None:
            continue
        if hunk is None:
            if raw.startswith("new file mode"):
                current["status"] = "added"
            elif raw.startswith("deleted file mode"):
                current["status"] = "deleted"
            elif raw.startswith("rename from"):
                current["status"] = "renamed"
            elif raw.startswith("Binary files"):
                current["binary"] = True
        m = HUNK_HEADER.match(raw)
        if m:
            old_no, new_no = int(m.group(1)), int(m.group(3))
            hunk = {"header": raw, "context": m.group(5).strip(), "oldStart": old_no,
                    "newStart": new_no, "lines": []}
            current["hunks"].append(hunk)
            continue
        if hunk is None:
            continue  # file header lines (index, ---, +++) come before the first hunk
        if raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        kind = {"+": "add", "-": "del"}.get(raw[:1], "ctx")
        line = {"t": kind, "s": raw[1:] if raw else ""}
        if kind != "add":
            line["o"] = old_no
            old_no += 1
        if kind != "del":
            line["n"] = new_no
            new_no += 1
        hunk["lines"].append(line)
    return files


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    files = parse(open(sys.argv[1], encoding="utf-8", errors="replace").read())
    hunks = []
    out_files = []
    for f in files:
        changed = sum(1 for h in f["hunks"] for l in h["lines"] if l["t"] != "ctx")
        adds = sum(1 for h in f["hunks"] for l in h["lines"] if l["t"] == "add")
        dels = changed - adds
        collapsed = is_generated(f["path"], changed)
        ids = []
        for h in f["hunks"]:
            hid = f"h{len(hunks) + 1}"
            ids.append(hid)
            hunks.append({"id": hid, "file": f["path"], "collapsed": collapsed, **h})
        out_files.append({"path": f["path"], "oldPath": f["oldPath"], "status": f["status"],
                          "binary": f["binary"], "additions": adds, "deletions": dels,
                          "collapsed": collapsed, "hunks": ids})
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump({"files": out_files, "hunks": hunks}, fh)

    for h in hunks:
        n = len(h["lines"])
        adds = sum(1 for l in h["lines"] if l["t"] == "add")
        dels = sum(1 for l in h["lines"] if l["t"] == "del")
        tag = f" [{h['collapsed']}: auto-collapsed]" if h["collapsed"] else ""
        print(f"{h['id']}\t{h['file']}:{h['newStart']}\t+{adds} -{dels} ({n} lines)\t{h['context'][:60]}{tag}")


if __name__ == "__main__":
    main()
