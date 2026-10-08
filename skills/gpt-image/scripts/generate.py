#!/usr/bin/env python3
"""Generate or edit images via fal.ai openai/gpt-image-2.5 (queue API).

Covers all four endpoints:

    openai/gpt-image-2.5/flare/text-to-image     (default generation)
    openai/gpt-image-2.5/flare/edit              (default editing)
    openai/gpt-image-2.5/sunburst/text-to-image  (premium detail, slower)
    openai/gpt-image-2.5/sunburst/edit           (tightest edit control)

Tier is chosen with --tier (flare|sunburst). Mode is implicit: passing
--image switches from text-to-image to edit.

Stdlib only — no pip install required. Reads FAL_KEY from env or
~/.config/fal/key.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

QUEUE_ROOT = "https://queue.fal.run"
MODEL_ROOT = "openai/gpt-image-2.5"
POLL_INTERVAL_SECONDS = 1.5
POLL_TIMEOUT_SECONDS = 900  # sunburst/max can be slow

TIERS = ("flare", "sunburst")
QUALITIES = ("auto", "low", "medium", "high", "xhigh", "max")
BACKGROUNDS = ("auto", "transparent", "opaque")
FORMATS = ("jpeg", "png", "webp")

PRESETS = (
    "square_hd",
    "square",
    "portrait_4_3",
    "portrait_16_9",
    "landscape_4_3",
    "landscape_16_9",
    "auto",
)

MAX_REFERENCE_IMAGES = 16

# Documented constraints for custom WxH on this model family. The server is
# the final authority; these checks just turn a remote 422 into a local error.
SIZE_MULTIPLE = 16
SIZE_MAX_EDGE = 3840
SIZE_MAX_RATIO = 3.0
SIZE_MIN_PIXELS = 655_360
SIZE_MAX_PIXELS = 8_294_400


def get_key() -> str:
    key = os.environ.get("FAL_KEY")
    if not key:
        cfg = Path.home() / ".config" / "fal" / "key"
        if cfg.exists():
            key = cfg.read_text().strip()
    if not key:
        sys.exit(
            "ERROR: FAL_KEY not set.\n"
            "  Either: export FAL_KEY=your_key\n"
            "  Or:     mkdir -p ~/.config/fal && echo your_key > ~/.config/fal/key"
        )
    return key


def http(method: str, url: str, key: str, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Key {key}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {e.reason}\n{e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error: {e.reason}")


def parse_size(size_str: str):
    """Parse --size: preset name, 'auto', or WxH like 1792x1024."""
    if size_str in PRESETS:
        return size_str
    m = re.fullmatch(r"(\d+)x(\d+)", size_str.lower())
    if not m:
        sys.exit(
            f"Invalid size '{size_str}'. Use a preset "
            f"({', '.join(PRESETS)}) or WxH like 1792x1024."
        )
    w, h = int(m.group(1)), int(m.group(2))
    if w % SIZE_MULTIPLE or h % SIZE_MULTIPLE:
        sys.exit(f"Width/height must be multiples of {SIZE_MULTIPLE} (got {w}x{h}).")
    if max(w, h) > SIZE_MAX_EDGE:
        sys.exit(f"Max edge is {SIZE_MAX_EDGE}px (got {w}x{h}).")
    ratio = max(w, h) / min(w, h)
    if ratio > SIZE_MAX_RATIO:
        sys.exit(f"Aspect ratio must be <= 3:1 (got {ratio:.2f}:1).")
    pixels = w * h
    if not SIZE_MIN_PIXELS <= pixels <= SIZE_MAX_PIXELS:
        sys.exit(
            f"Total pixels must be between {SIZE_MIN_PIXELS:,} and "
            f"{SIZE_MAX_PIXELS:,} (got {pixels:,})."
        )
    return {"width": w, "height": h}


# ---------- input images (edit mode) ----------


def resolve_image_ref(source: str) -> str:
    """Local path or URL -> value for image_urls.

    URLs pass through. Local files become base64 data URIs, which this
    endpoint accepts directly — no storage upload hop, no extra host to
    resolve. Large files make large request bodies; downscale references you
    do not need at full resolution.
    """
    if source.startswith(("http://", "https://")):
        return source
    path = Path(source).expanduser()
    if not path.exists():
        sys.exit(f"Input file not found: {path}")
    ctype, _ = mimetypes.guess_type(path.name)
    if not (ctype or "").startswith("image/"):
        ctype = "image/png"
    data = path.read_bytes()
    print(f"  inlining {path.name} ({len(data):,} bytes)...", file=sys.stderr)
    return f"data:{ctype};base64,{base64.b64encode(data).decode()}"


# ---------- queue ----------


def submit(key: str, endpoint: str, body: dict) -> tuple[str, str]:
    url = f"{QUEUE_ROOT}/{endpoint}"
    print(f"Submitting to {endpoint} ...", file=sys.stderr)
    r = http("POST", url, key, body)
    rid = r.get("request_id")
    if not rid:
        sys.exit(f"No request_id in response: {r}")
    status_url = r.get("status_url") or f"{QUEUE_ROOT}/{MODEL_ROOT}/requests/{rid}/status"
    response_url = r.get("response_url") or f"{QUEUE_ROOT}/{MODEL_ROOT}/requests/{rid}"
    print(f"  request_id: {rid}", file=sys.stderr)
    return status_url, response_url


def wait_for_completion(key: str, status_url: str) -> None:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last = None
    while time.time() < deadline:
        s = http("GET", status_url, key)
        st = s.get("status")
        if st != last:
            qp = s.get("queue_position")
            extra = f" (queue {qp})" if qp is not None else ""
            print(f"  {st}{extra}", file=sys.stderr)
            last = st
        if st == "COMPLETED":
            return
        if st in ("FAILED", "ERROR", "CANCELLED"):
            sys.exit(f"Generation {st}: {s}")
        time.sleep(POLL_INTERVAL_SECONDS)
    sys.exit("Timed out waiting for fal.ai result")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        f.write(r.read())


# ---------- cli ----------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Generate or edit images with fal.ai openai/gpt-image-2.5. "
            "Passing --image switches from text-to-image to edit."
        ),
    )
    p.add_argument("--prompt", required=True, help="Prompt or editing instruction.")
    p.add_argument(
        "--output",
        required=True,
        help="Local output file path. Parent dirs auto-created.",
    )
    p.add_argument(
        "--tier",
        default="flare",
        choices=TIERS,
        help=(
            "flare = fast default. sunburst = premium fidelity on intricate "
            "detail / tightest edit control, slower."
        ),
    )
    p.add_argument(
        "--image",
        action="append",
        dest="image_sources",
        metavar="PATH_OR_URL",
        help=(
            "Input image for edit mode: local file path or public URL. "
            f"Repeat for up to {MAX_REFERENCE_IMAGES} references. "
            "Local files are inlined as base64 automatically."
        ),
    )
    p.add_argument(
        "--mask",
        metavar="PATH_OR_URL",
        help="Optional mask (edit mode only): confines changes to a region.",
    )
    p.add_argument(
        "--size",
        default=None,
        help=(
            "Preset (" + ", ".join(PRESETS) + ") or WxH like 1792x1024. "
            "Default landscape_4_3 for generation, auto for edit."
        ),
    )
    p.add_argument("--quality", default="high", choices=QUALITIES)
    p.add_argument(
        "--background",
        default="auto",
        choices=BACKGROUNDS,
        help="transparent needs --output-format png or webp.",
    )
    p.add_argument(
        "--num-images",
        type=int,
        default=1,
        help="1-10. >1 suffixes filenames -1, -2, ...",
    )
    p.add_argument("--output-format", default="png", choices=FORMATS)
    p.add_argument(
        "--compression",
        type=int,
        default=None,
        metavar="0-100",
        help="Output compression for jpeg/webp only.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.prompt.strip():
        sys.exit("Prompt must not be empty.")
    if not 1 <= args.num_images <= 10:
        sys.exit(f"--num-images must be 1-10 (got {args.num_images}).")
    if args.compression is not None:
        if not 0 <= args.compression <= 100:
            sys.exit("--compression must be 0-100.")
        if args.output_format == "png":
            sys.exit("--compression applies to jpeg/webp only, not png.")
    if args.background == "transparent" and args.output_format == "jpeg":
        sys.exit("--background transparent needs --output-format png or webp.")

    editing = bool(args.image_sources)
    if args.mask and not editing:
        sys.exit("--mask only applies in edit mode (pass --image too).")
    if editing and len(args.image_sources) > MAX_REFERENCE_IMAGES:
        sys.exit(
            f"At most {MAX_REFERENCE_IMAGES} input images "
            f"(got {len(args.image_sources)})."
        )

    key = get_key()

    body: dict = {
        "prompt": args.prompt,
        "quality": args.quality,
        "background": args.background,
        "num_images": args.num_images,
        "output_format": args.output_format,
    }
    if args.compression is not None:
        body["output_compression"] = args.compression

    size = args.size if args.size is not None else ("auto" if editing else "landscape_4_3")
    body["image_size"] = parse_size(size)

    if editing:
        body["image_urls"] = [resolve_image_ref(s) for s in args.image_sources]
        if args.mask:
            body["mask_url"] = resolve_image_ref(args.mask)

    mode = "edit" if editing else "text-to-image"
    endpoint = f"{MODEL_ROOT}/{args.tier}/{mode}"

    status_url, response_url = submit(key, endpoint, body)
    wait_for_completion(key, status_url)
    res = http("GET", response_url, key)

    images = res.get("images") or []
    if not images:
        sys.exit(f"No images in result: {res}")

    out = Path(args.output).expanduser()
    if len(images) == 1:
        download(images[0]["url"], out)
        print(f"Saved: {out}")
    else:
        for i, img in enumerate(images, start=1):
            sub = out.with_name(f"{out.stem}-{i}{out.suffix}")
            download(img["url"], sub)
            print(f"Saved: {sub}")


if __name__ == "__main__":
    main()
