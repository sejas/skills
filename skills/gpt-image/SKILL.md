---
name: gpt-image
description: Generate and edit images with OpenAI GPT Image 2.5 via fal.ai. Use when the user wants an image from a text prompt, or wants an existing image edited while keeping subject, composition and background intact. Covers all four endpoints — flare (fast default) and sunburst (premium detail / tightest edit control), each in text-to-image and edit form. Supports transparent backgrounds, preset or custom sizes (e.g. 1792×1024 for 16:9 slides), quality up to max, up to 10 images per request, masks, and up to 16 reference images. Stdlib-only Python; no pip install required.
---

# GPT Image 2.5 (fal.ai)

One script drives all four `openai/gpt-image-2.5` endpoints on fal.ai's queue API.

| Endpoint | Reach it with | Best for |
|---|---|---|
| `flare/text-to-image` | *(default)* | **Start here for any new image.** Fast, high quality. Natural lighting, rich textures, complex layouts, transparent backgrounds. |
| `flare/edit` | `--image` | **Start here for any edit.** Changes only what's asked; subject, composition and background survive. References stay recognisable across styles and successive edits. |
| `sunburst/text-to-image` | `--tier sunburst` | Premium hero images. Extra fidelity on intricate detail — fine typography, ornament, texture, product shots. Slower; pay the wait only when detail is the point. |
| `sunburst/edit` | `--tier sunburst --image` | Tightest control. Edits scoped precisely to the instruction, subject and composition preserved across many revision rounds. Reach for it when `flare/edit` drifts. |

Rule of thumb: **flare until it fails you, then sunburst.** Flare is the default for most
work; sunburst buys detail and obedience at the cost of time.

### Choosing between this and the other image skills

- **This skill** — OpenAI-style prompting, transparent backgrounds, masked edits, strong
  in-image typography, sizes pinned to exact pixel dimensions.
- **`fal-image-edit`** (nano-banana-pro / Gemini 3 Pro on fal) — better when composing
  **many references** (up to 14), when you need **web-search grounding** for factual
  content, **4K** output, a **seed** for reproducibility, or aspect-ratio-by-name control.
- **`nano-banana-image-editor`** — same model family through a direct Google key rather
  than fal billing.

## Prerequisites

A fal.ai API key. Set once:

```bash
export FAL_KEY=your_key_here
# or persist:
mkdir -p ~/.config/fal && echo your_key_here > ~/.config/fal/key
```

Get a key at https://fal.ai/dashboard/keys.

## Usage

Mode is implicit: **no `--image` means text-to-image, `--image` means edit.**

```bash
SKILL=${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}/skills/gpt-image/scripts/generate.py

# Generate (flare, the default)
python3 $SKILL \
  --prompt "A serene minimalist illustration of a lighthouse at sunrise, warm cream palette" \
  --output ~/out.png
```

### Premium detail

```bash
python3 $SKILL --tier sunburst --quality xhigh \
  --prompt "Art-nouveau poster, intricate gold filigree border, letterpress texture" \
  --output ~/hero.png
```

### Edit an existing image

`--image` takes a **local path or a URL**. Local files upload to fal storage automatically.

```bash
python3 $SKILL \
  --image ~/photo.jpg \
  --prompt "Make it night-time, add neon signs in the background" \
  --output ~/out.png
```

### Edit with tightest control, across revision rounds

```bash
python3 $SKILL --tier sunburst \
  --image ~/poster.png \
  --prompt "Replace only the date line with '11-13 December 2026'. Leave everything else untouched." \
  --output ~/poster-v2.png
```

### Masked edit — confine changes to a region

```bash
python3 $SKILL --image ~/room.png --mask ~/room-mask.png \
  --prompt "Put a large window here" --output ~/room-window.png
```

### Transparent background (logos, stickers, overlays)

```bash
python3 $SKILL --background transparent --output-format png \
  --prompt "A flat vector capoeira berimbau icon, single colour, no background" \
  --output ~/icon.png
```

### 16:9 for presentation slides

```bash
python3 $SKILL --size 1792x1024 --quality high \
  --prompt "..." --output ~/slide.png
```

### Batch variations

```bash
python3 $SKILL --num-images 4 --prompt "..." --output ~/out.png
# saves ~/out-1.png … ~/out-4.png
```

### All flags

| Flag | Default | Notes |
|---|---|---|
| `--prompt` | required | Prompt, or the editing instruction |
| `--output` | required | Local path; parent dirs auto-created |
| `--tier` | `flare` | `flare` or `sunburst` |
| `--image` | — | Local path or URL. Repeatable, up to **16**. Presence switches to edit mode |
| `--mask` | — | Edit mode only; confines changes to a region |
| `--size` | `landscape_4_3` generating, `auto` editing | Preset, `auto`, or `WxH` |
| `--quality` | `high` | `auto`, `low`, `medium`, `high`, `xhigh`, `max` |
| `--background` | `auto` | `auto`, `transparent`, `opaque` |
| `--num-images` | `1` | **1–10**. >1 suffixes filenames `-1`, `-2`, … |
| `--output-format` | `png` | `jpeg`, `png`, `webp` |
| `--compression` | — | `0–100`, jpeg/webp only |

### Size presets

`square_hd`, `square`, `portrait_4_3`, `portrait_16_9`, `landscape_4_3`,
`landscape_16_9`, `auto` (model picks).

### Custom size constraints

When passing `WxH`: multiples of **16**, max edge **3840**, aspect ratio **≤ 3:1**,
total pixels **655,360–8,294,400**. The script checks these locally so you get a clear
error instead of a remote 422; the server remains the authority.

Useful sizes: `1792x1024` 16:9 slide · `1920x1080` Full HD · `2048x1152` 16:9 hi-res ·
`1024x1792` vertical 9:16 · `2048x2048` square hi-res.

## How it works

1. `POST https://queue.fal.run/openai/gpt-image-2.5/{tier}/{text-to-image|edit}` with
   `Authorization: Key $FAL_KEY`. Response carries `request_id`, `status_url`,
   `response_url`.
2. Poll `status_url` until `COMPLETED`.
3. `GET response_url` — result has `images: [{url, content_type, width, height, …}]`.
4. Download each URL to the local output path.

Local `--image` / `--mask` files are uploaded to fal storage first
(`POST https://fal.media/files/upload`) and the returned `access_url` is sent.

Pure stdlib — `urllib.request`, `json`, `argparse`, `mimetypes`, `re`. No `fal-client`,
no `requests`, no venv.

## Request body reference

Both text-to-image endpoints take `prompt` (required), `image_size`, `quality`,
`background`, `num_images`, `output_format`, `output_compression`, `sync_mode`.

Both edit endpoints take the same plus **`image_urls`** (array, required) and
**`mask_url`** — note the names: it is *not* `image`/`mask` in the API body.

OpenAPI: `https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=openai/gpt-image-2.5/flare/text-to-image`
(swap the endpoint id for the other three).

## Limitations

- **No seed.** Generations are stochastic. For a cohesive set, repeat shared style
  language (palette, illustration style, mood, lighting) in every prompt — or generate
  one image and use `flare/edit` to derive the rest, which holds style far better.
- **Synchronous polling.** Blocks until done, 15 min timeout. Sunburst at `max` is slow.
- **Cost scales with reference resolution** in edit mode: roughly +$0.008 per 1024×1024
  reference, +$0.012 at 3840×2160. Downscale references you don't need at full size.

## Troubleshooting

- `HTTP 401` → key missing or wrong. Check `echo $FAL_KEY` or `cat ~/.config/fal/key`.
- `HTTP 422` → body validation failed; the error JSON names the field. Usually an
  `image_size` constraint or a missing `image_urls`.
- `Generation FAILED` → safety filter or model error. Soften the prompt or change size.
- **Edit changed too much** → say what must not change: *"keep the exact pose, palette and
  background; change only X."* Then escalate to `--tier sunburst`.
- **Detail mushy on intricate work** → `--tier sunburst` with `--quality xhigh` or `max`.
- **Transparent background came out white** → needs `--background transparent` *and*
  `--output-format png` or `webp`.
- Slow → fal queue; status lines show queue position.
