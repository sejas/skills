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
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?([^\n]*)$")


def is_generated(path, changed_lines):
    if any(re.search(p, path) for p in GENERATED_PATTERNS):
        return "generated"
    if changed_lines > HUGE_FILE_LINES:
        return "huge"
    return None


class DiffError(ValueError):
    pass


def unquote(name):
    r"""Decode git's C-style quoted path ("a/caf\\303\\251") and drop the tab git adds after names with spaces."""
    if not name.startswith('"'):
        return name.split("\t", 1)[0]
    body, out, i = name[1:name.rindex('"')], bytearray(), 0
    simple = {"n": 10, "t": 9, "r": 13, "a": 7, "b": 8, "f": 12, "v": 11, '"': 34, "\\": 92}
    while i < len(body):
        if body[i] != "\\":
            out += body[i].encode()
            i += 1
        elif body[i + 1] in simple:
            out.append(simple[body[i + 1]])
            i += 2
        else:
            out.append(int(body[i + 1:i + 4], 8))
            i += 4
    return out.decode("utf-8", "replace")


def header_paths(rest):
    """Paths from `diff --git a/X b/X`. Ambiguous with odd names, so ---/+++/rename lines override it."""
    half = len(rest) // 2
    if len(rest) % 2 and rest[half] == " " and unquote(rest[:half])[2:] == unquote(rest[half + 1:])[2:]:
        path = unquote(rest[:half])[2:]
        return path, path
    m = re.match(r"a/(.*) b/(.*)$", rest)
    return (m.group(1), m.group(2)) if m else (None, rest)


def parse(text):
    r"""The text comes from the PR author, so it must not be able to fake file or hunk headers:
    split on \n only (splitlines() also breaks on U+2028, \f, \r ...) and let each hunk
    header's line counts decide what is content."""
    files = []
    current = None
    hunk = None
    old_no = new_no = old_left = new_left = 0
    for raw in text.split("\n"):
        if old_left or new_left:
            kind = {"+": "add", "-": "del", " ": "ctx", "": "ctx", "\r": "ctx"}.get(raw[:1])
            if raw.startswith("\\"):
                continue  # "\ No newline at end of file" between the two sides
            if kind is None:
                raise DiffError(f"{current['path']}: unexpected line inside hunk {hunk['header']!r}: {raw[:80]!r}")
            line = {"t": kind, "s": raw[1:]}
            if kind != "add":
                line["o"] = old_no
                old_no += 1
                old_left -= 1
            if kind != "del":
                line["n"] = new_no
                new_no += 1
                new_left -= 1
            if old_left < 0 or new_left < 0:
                raise DiffError(f"{current['path']}: more lines than hunk header {hunk['header']!r} declares")
            hunk["lines"].append(line)
            continue
        if raw.startswith("diff --git "):
            old, new = header_paths(raw[11:])
            current = {"path": new, "oldPath": old, "status": "modified", "hunks": [], "binary": False}
            files.append(current)
            hunk = None
            continue
        m = HUNK_HEADER.match(raw)
        if m:
            if current is None:
                raise DiffError("hunk before any file header")
            old_no, new_no = int(m.group(1)), int(m.group(3))
            old_left, new_left = (int(m.group(k)) if m.group(k) is not None else 1 for k in (2, 4))
            hunk = {"header": raw, "context": m.group(5).strip(), "oldStart": old_no,
                    "newStart": new_no, "lines": []}
            current["hunks"].append(hunk)
            continue
        if hunk is not None:
            if raw and not raw.startswith("\\"):
                raise DiffError(f"{current['path']}: unexpected line after hunk {hunk['header']!r}: {raw[:80]!r}")
            continue
        if current is None:
            if raw:
                raise DiffError(f"unexpected line before the first file: {raw[:80]!r}")
        elif raw.startswith("new file mode"):
            current["status"] = "added"
        elif raw.startswith("deleted file mode"):
            current["status"] = "deleted"
        elif raw.startswith("rename from "):
            current["status"], current["oldPath"] = "renamed", unquote(raw[12:])
        elif raw.startswith("rename to "):
            current["path"] = unquote(raw[10:])
        elif raw.startswith("Binary files"):
            current["binary"] = True
        elif raw.startswith("--- ") and raw != "--- /dev/null":
            current["oldPath"] = unquote(raw[4:])[2:]
            if current["status"] == "deleted":
                current["path"] = current["oldPath"]
        elif raw.startswith("+++ ") and raw != "+++ /dev/null":
            current["path"] = unquote(raw[4:])[2:]
    if old_left or new_left:
        raise DiffError(f"{current['path']}: diff ends inside hunk {hunk['header']!r}")
    return files


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8", errors="replace", newline="") as fh:
        text = fh.read()
    try:
        files = parse(text)
    except DiffError as e:
        sys.exit(f"parse_diff: {e}")
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
