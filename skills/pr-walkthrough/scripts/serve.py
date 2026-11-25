#!/usr/bin/env python3
"""Serve a rendered walkthrough with an "Ask" endpoint backed by `claude -p`.

Usage: serve.py <workdir> <walkthrough.html> [--port N] [--open] [--idle-minutes 30]

- Binds 127.0.0.1 only. Requests must carry the right Host header (blocks DNS
  rebinding) and /ask needs the per-run token injected into the page plus a
  same-origin Origin (blocks other websites posting to localhost).
- Each question runs `claude -p` with NO tools, no MCP servers and no hooks, so
  text inside the PR can't make it run anything. The first question of a thread
  carries the PR context; follow-ups resume the same session.
- Questions and answers are appended to <workdir>/questions.jsonl, so future
  walkthroughs can pre-explain what confused the reader.
- Exits after --idle-minutes without requests; an open page pings /ping every 5 minutes.
"""

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_DIFF_CHARS = 80_000
STYLE = (
    "You answer questions from a developer reading a step-by-step walkthrough of a pull request. "
    "Lead with the answer. Keep it under 120 words unless asked for more. Plain language; define jargon "
    "and acronyms in a few words. Point at code as `file:line`. Markdown: short paragraphs, `code`, short "
    "lists, fenced code only when it helps. You have no tools: answer from the PR context provided and "
    "general knowledge, and say so when something isn't visible in the diff."
)


def load(workdir, name, default=None):
    path = os.path.join(workdir, name)
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def diff_text(hunks):
    out, size = [], 0
    for h in hunks["hunks"]:
        if h["collapsed"]:
            continue
        block = [f"--- {h['file']} {h['header']}"]
        for l in h["lines"]:
            sign = {"add": "+", "del": "-"}.get(l["t"], " ")
            block.append(f"{l.get('n', '') or '':>5} {sign} {l['s']}")
        chunk = "\n".join(block)
        if size + len(chunk) > MAX_DIFF_CHARS:
            out.append("[diff truncated]")
            break
        out.append(chunk)
        size += len(chunk)
    return "\n\n".join(out)


def context_prompt(wt, hunks, findings):
    pr = wt.get("pr", {})
    steps = [s for c in wt.get("chapters", []) for s in c.get("steps", [])]

    def step_text(i, s):
        # The walkthrough's notes carry facts checked outside the diff (other repos, callers);
        # include them so answers don't contradict the page.
        lines = [f"{i + 1}. {s['title']} — {s.get('why', '')}"]
        lines += [f"   more: {s['more']}"] if s.get("more") else []
        lines += [f"   risk: {s['risk']['text']}"] if s.get("risk") else []
        lines += [f"   note on line {n['line']}: {n['text']}" for n in s.get("notes", [])]
        return "\n".join(lines)

    outline = "\n".join(step_text(i, s) for i, s in enumerate(steps))
    found = "\n".join(f"- {f.get('title')} ({f.get('path', 'general')}:{f.get('line', '')})"
                      for f in (findings or {}).get("findings", []))
    return (f"# PR: {wt.get('title')} ({pr.get('url', '')})\n\n{wt.get('tldr', '')}\n\n{wt.get('context', '')}\n\n"
            f"## Is this the right approach for the problem?\n{json.dumps(wt.get('approach') or {}, ensure_ascii=False)}\n\n"
            f"## Walkthrough steps (verified by the reviewer, including facts from outside this diff)\n{outline}\n\n"
            f"## Review findings\n{found or '(none)'}\n\n"
            f"## Diff (new-file line numbers on the left)\n{diff_text(hunks)}\n\n"
            "Wait for the reader's question below; context above is reference only.\n\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    workdir, html_path = os.path.abspath(args[0]), os.path.abspath(args[1])
    opt = lambda name, d: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else d
    port, idle = int(opt("--port", 0)), float(opt("--idle-minutes", 30))
    token = secrets.token_urlsafe(24)
    wt = load(workdir, "walkthrough.json")
    hunks = load(workdir, "hunks.json")
    findings = load(workdir, "findings.json", {})
    steps = [s for c in wt.get("chapters", []) for s in c.get("steps", [])]
    threads = set()
    lock = threading.Lock()
    state = {"last": time.time()}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def host_ok(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def send_plain(self, code, body):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            state["last"] = time.time()
            if not self.host_ok():
                return self.send_plain(403, "bad host")
            if self.path == "/ping":  # keep-alive from an open page
                return self.send_plain(200, "ok")
            if self.path.split("?")[0] not in ("/", "/index.html"):
                return self.send_plain(404, "not found")
            html = open(html_path, encoding="utf-8").read()
            inject = f"<script>window.__ASK__ = {json.dumps({'token': token})};</script>"
            data = html.replace("</head>", inject + "\n</head>", 1).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def chunk(self, text):
            data = text.encode()
            if data:
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

        def do_POST(self):
            state["last"] = time.time()
            origin = self.headers.get("Origin", "")
            if (not self.host_ok() or self.path != "/ask" or self.headers.get("X-Ask-Token") != token
                    or origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")):
                return self.send_plain(403, "forbidden")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0))
            except ValueError:
                return self.send_plain(400, "bad json")
            question = str(body.get("question", "")).strip()[:4000]
            selection = str(body.get("selection", "")).strip()[:4000]
            thread = str(body.get("thread", ""))
            if not question or not re.fullmatch(r"[0-9a-f-]{36}", thread):
                return self.send_plain(400, "question and thread required")
            step_i = body.get("step")
            step = steps[step_i] if isinstance(step_i, int) and 0 <= step_i < len(steps) else None

            ask = ""
            with lock:
                first = thread not in threads
                threads.add(thread)
            if first:
                ask += context_prompt(wt, hunks, findings)
            if step:
                ask += f"The reader is on step {step_i + 1}: \"{step['title']}\".\n"
            if selection:
                ask += f"They selected:\n```\n{selection}\n```\n"
            ask += f"Question: {question}"

            cmd = ["claude", "-p", "--tools", "", "--strict-mcp-config", "--settings", '{"disableAllHooks":true}',
                   "--output-format", "stream-json", "--include-partial-messages", "--verbose",
                   "--append-system-prompt", STYLE]
            cmd += ["--session-id", thread] if first else ["--resume", thread]
            if os.environ.get("PRW_MODEL"):
                cmd += ["--model", os.environ["PRW_MODEL"]]

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            answer, error = [], None
            try:
                proc = subprocess.Popen(cmd, cwd=workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True)
                proc.stdin.write(ask)
                proc.stdin.close()
                for line in proc.stdout:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    ev = e.get("event") or {}
                    if e.get("type") == "stream_event" and ev.get("type") == "content_block_delta":
                        text = (ev.get("delta") or {}).get("text", "")
                        answer.append(text)
                        self.chunk(text)
                    elif e.get("type") == "result" and e.get("is_error"):
                        error = e.get("result") or "claude returned an error"
                proc.wait()
                if proc.returncode and not error:
                    error = f"claude exited with code {proc.returncode}"
                if error:
                    if first:  # no session was created; let the next question start fresh
                        with lock:
                            threads.discard(thread)
                    self.chunk(f"\n\n⚠️ {error}")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                state["last"] = time.time()
                with open(os.path.join(workdir, "questions.jsonl"), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "step": step["title"] if step else None,
                                         "selection": selection, "question": question,
                                         "answer": "".join(answer), "error": error}, ensure_ascii=False) + "\n")

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{httpd.server_port}/"
    print(f"walkthrough with Ask: {url}  (stops after {idle:g} idle minutes)", flush=True)

    def watchdog():
        while time.time() - state["last"] < idle * 60:
            time.sleep(15)
        print("idle, shutting down", flush=True)
        httpd.shutdown()

    threading.Thread(target=watchdog, daemon=True).start()
    if "--open" in sys.argv:
        subprocess.Popen(["open", "-a", "Google Chrome", url])
    httpd.serve_forever()


if __name__ == "__main__":
    main()
