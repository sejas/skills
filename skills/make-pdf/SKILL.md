---
name: make-pdf
description: Turn a markdown file into a publication-quality PDF — cover page, clickable table of contents with page numbers, running headers, page numbers, curly quotes, syntax-highlighted code, optional DRAFT watermark. Use when asked to "make a PDF", "export to PDF", "turn this markdown into a PDF", or "generate a document".
allowed-tools: Bash, Read, AskUserQuestion
---

# make-pdf

```bash
uv run --quiet --with weasyprint --with markdown --with pygments \
  ~/.claude/skills/make-pdf/md2pdf.py INPUT.md
```

Writes `INPUT.pdf` next to the input and prints the path. Then `open` it, or read it
back with the Read tool to check the result before handing it over.

## Options

| Flag | Effect |
|---|---|
| `-o OUT.pdf` | Output path (default: input path with `.pdf`) |
| `--title` / `--subtitle` / `--author` | Override the cover; otherwise taken from YAML front matter, then the first `# H1`, then the filename |
| `--draft` | Diagonal DRAFT watermark on every page |
| `--no-cover` | Skip the cover page |
| `--no-toc` | Skip the table of contents |

Front matter (`title`, `subtitle`/`description`, `author`, `date`) is consumed for the
cover and stripped from the body. A leading `# H1` that repeats the title is dropped so
the cover doesn't say it twice.

## Gotchas

- **Needs `uv` and Homebrew `pango`.** WeasyPrint links against pango at runtime; without
  it the import fails with a `libgobject`/`libpango` load error — fix with `brew install pango`.
  `uv run --with` builds a cached ephemeral env, so nothing is installed globally and the
  first run takes ~10s, later ones ~2s.
- **WeasyPrint, not headless Chrome, on purpose.** Running headers, `counter(page)`, and
  the TOC's page numbers are `@page` margin boxes and `target-counter()`. Chrome ignores
  both, so a Chrome-based pipeline silently drops exactly the features that make the
  output look printed.
- **Relative image paths resolve against the markdown file's directory.** Images from
  elsewhere need absolute paths.
- **Mermaid and other JS-rendered diagrams don't render** — there is no JS engine in the
  pipeline. Convert them to SVG/PNG first and reference the image.
- Everything visual lives in one `STYLESHEET` string at the top of `md2pdf.py`. For a
  different look, edit it there — there is no theme system and no config file.

## Vault note

For a note out of the Obsidian vault, wikilinks (`[[slug]]`) pass through as literal text —
strip or expand them first if the PDF is going to someone outside the vault.
