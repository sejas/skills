#!/usr/bin/env python3
"""Markdown -> publication-quality PDF.

Run through uv so the dependencies live in an ephemeral, cached env:

    uv run --with weasyprint --with markdown --with pygments md2pdf.py IN.md [-o OUT.pdf]

Everything that makes the output look printed rather than exported — 1in margins,
running headers, page numbers, cover page, watermark — is done with @page CSS,
which is why this uses WeasyPrint instead of headless Chrome (Chrome ignores
@page margin boxes and their counters).
"""

import argparse
import datetime
import html
import pathlib
import re
import sys

import markdown
from weasyprint import CSS, HTML

# ponytail: one stylesheet, no theme system. Fork the string if you need a second look.
STYLESHEET = """
@page {
    size: A4;
    margin: 1in;

    @top-left   { content: string(doctitle); font: 8pt/1 "Helvetica Neue", sans-serif;
                  color: #8a8a8a; letter-spacing: .04em; padding-bottom: 6pt; }
    @top-right  { content: string(section); font: 8pt/1 "Helvetica Neue", sans-serif;
                  color: #8a8a8a; letter-spacing: .04em; padding-bottom: 6pt; }
    @bottom-center { content: counter(page) " / " counter(pages);
                     font: 8pt/1 "Helvetica Neue", sans-serif; color: #8a8a8a;
                     padding-top: 8pt; }
}

/* The cover carries no header or page number; the TOC keeps the title only.
   Keyed on the named page, not :first — with --no-cover, page 1 is real content
   and must keep its header. */
@page cover { @top-left { content: none } @top-right { content: none }
              @bottom-center { content: none } }
@page toc   { @top-right { content: none } }

html { font-size: 11pt; }
body {
    font-family: "Charter", "Georgia", "Iowan Old Style", serif;
    line-height: 1.58; color: #1b1b1b; hyphens: auto;
    text-align: justify; text-justify: inter-word;
}

h1, h2, h3, h4 {
    font-family: "Helvetica Neue", "Inter", sans-serif;
    font-weight: 600; color: #111; text-align: left; hyphens: none;
    break-after: avoid;               /* never strand a heading at a page foot */
}
h1 { font-size: 20pt; margin: 0 0 .6em; string-set: section content(); }
h2 { font-size: 15pt; margin: 1.6em 0 .5em; string-set: section content(); }
h3 { font-size: 12.5pt; margin: 1.3em 0 .4em; }
h4 { font-size: 11pt; margin: 1.2em 0 .3em; color: #444; }

p { margin: 0 0 .75em; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 .8em 1.2em; padding: 0; }
li { margin: .2em 0; break-inside: avoid; }

a { color: #14507d; text-decoration: none; }

blockquote {
    margin: 1em 0; padding: .2em 0 .2em 1em;
    border-left: 2.5pt solid #d8d8d8; color: #444; font-style: italic;
    break-inside: avoid;
}

code, pre { font-family: "SF Mono", "Menlo", monospace; font-size: 9pt; }
code { background: #f4f4f4; padding: .1em .3em; border-radius: 2pt; }
pre {
    background: #f7f7f7; border: .5pt solid #e4e4e4; border-radius: 3pt;
    padding: .7em .9em; line-height: 1.35; white-space: pre-wrap;
    word-wrap: break-word; break-inside: avoid; margin: 0 0 1em;
}
pre code { background: none; padding: 0; }

table {
    border-collapse: collapse; width: 100%; margin: 0 0 1em;
    font-size: 9.5pt; break-inside: avoid;
}
th, td { border: .5pt solid #ddd; padding: .35em .55em; text-align: left; }
th { background: #f4f4f4; font-family: "Helvetica Neue", sans-serif; font-weight: 600; }

img { max-width: 100%; }
hr { border: none; border-top: .5pt solid #ddd; margin: 1.6em 0; }

/* ---- cover ---- */
.cover { page: cover; break-after: page; text-align: left; }
.cover-rule { border-top: 3pt solid #1b1b1b; width: 3.2cm; margin: 0 0 1.6cm; }
.cover h1 {
    font-size: 32pt; line-height: 1.15; margin: 7cm 0 .5cm;
    string-set: doctitle content();   /* feeds the running header */
}
.cover .subtitle { font-family: "Helvetica Neue", sans-serif; font-size: 12pt;
                   color: #666; margin: 0 0 4cm; }
.cover .meta { font-family: "Helvetica Neue", sans-serif; font-size: 9.5pt;
               color: #8a8a8a; letter-spacing: .04em; }

/* ---- table of contents ---- */
nav.toc { page: toc; break-after: page; }
nav.toc > h2 { font-size: 13pt; margin: 0 0 1em; text-transform: uppercase;
               letter-spacing: .08em; color: #666; }
nav.toc ul { list-style: none; margin: 0; padding: 0; }
nav.toc ul ul { margin-left: 1.1em; }
nav.toc li { margin: .35em 0; font-family: "Helvetica Neue", sans-serif; font-size: 10pt; }
nav.toc a { color: #1b1b1b; }
nav.toc a::after { content: " · " target-counter(attr(href), page); color: #9a9a9a; }

/* ---- draft watermark ---- */
.watermark {
    position: fixed; top: 42%; left: 0; width: 100%;
    transform: rotate(-32deg); transform-origin: center;
    font-family: "Helvetica Neue", sans-serif; font-size: 96pt; font-weight: 700;
    color: rgba(200, 40, 40, .10); text-align: center; letter-spacing: .1em;
}
"""

MD_EXTENSIONS = [
    "extra",          # tables, fenced code, footnotes, def lists
    "toc",
    "smarty",         # curly quotes, em dashes, ellipses
    "sane_lists",
    "admonition",
    "codehilite",
]
MD_CONFIG = {
    "toc": {"permalink": False, "toc_depth": "2-3"},
    "codehilite": {"guess_lang": False, "noclasses": True, "pygments_style": "friendly"},
    "smarty": {"smart_dashes": True, "smart_quotes": True, "smart_ellipses": True},
}


def split_front_matter(text):
    """Return (metadata, body). Supports a leading YAML-ish --- block."""
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                if ":" in line and not line.lstrip().startswith("#"):
                    k, _, v = line.partition(":")
                    meta[k.strip().lower()] = v.strip().strip("\"'")
            text = text[end + 4:].lstrip("\n")
    return meta, text


def derive_title(meta, body, path):
    for key in ("title", "name"):
        if meta.get(key):
            return meta[key]
    m = re.search(r"^#\s+(.+)$", body, re.M)
    if m:
        return m.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def strip_leading_h1(body, title):
    """Drop the document's own H1 when the cover already shows it."""
    m = re.match(r"^#\s+(.+?)\s*$", body, re.M)
    if m and m.group(1).strip() == title:
        return body[m.end():].lstrip("\n")
    return body


def build_html(md_path, args):
    raw = md_path.read_text(encoding="utf-8")
    meta, body = split_front_matter(raw)
    title = args.title or derive_title(meta, body, md_path)
    subtitle = args.subtitle or meta.get("subtitle") or meta.get("description") or ""
    author = args.author or meta.get("author") or ""

    if not args.no_cover:
        body = strip_leading_h1(body, title)

    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG)
    content = md.convert(body)
    toc = getattr(md, "toc", "")

    date = meta.get("date") or datetime.date.today().isoformat()
    parts = []

    if args.draft:
        parts.append('<div class="watermark">DRAFT</div>')

    if not args.no_cover:
        meta_line = " · ".join(x for x in (author, date) if x)
        parts.append(
            '<section class="cover">'
            '<div class="cover-rule"></div>'
            f"<h1>{html.escape(title)}</h1>"
            + (f'<p class="subtitle">{html.escape(subtitle)}</p>' if subtitle else "")
            + (f'<p class="meta">{html.escape(meta_line)}</p>' if meta_line else "")
            + "</section>"
        )
    # Without a cover nothing sets `doctitle`, so the header's left slot stays empty
    # and the current section (right slot) carries the context on its own. Setting it
    # here would just print the same string twice on every page.

    if args.toc and toc.strip():
        parts.append(f'<nav class="toc"><h2>Contents</h2>{toc}</nav>')

    parts.append(f"<main>{content}</main>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title></head><body>"
        + "".join(parts)
        + "</body></html>"
    )


def main():
    ap = argparse.ArgumentParser(description="Markdown -> publication-quality PDF")
    ap.add_argument("input", type=pathlib.Path)
    ap.add_argument("-o", "--output", type=pathlib.Path)
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--author")
    ap.add_argument("--draft", action="store_true", help="diagonal DRAFT watermark")
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--no-toc", dest="toc", action="store_false", default=True)
    args = ap.parse_args()

    if not args.input.is_file():
        sys.exit(f"not a file: {args.input}")

    out = args.output or args.input.with_suffix(".pdf")
    doc = build_html(args.input, args)

    # base_url lets relative image paths in the markdown resolve.
    HTML(string=doc, base_url=str(args.input.parent)).write_pdf(
        out, stylesheets=[CSS(string=STYLESHEET)]
    )
    print(out)


if __name__ == "__main__":
    main()
