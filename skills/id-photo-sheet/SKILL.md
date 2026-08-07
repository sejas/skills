---
name: id-photo-sheet
description: Use when the user needs ID/passport/carnet photos (foto carnet, foto de carné, DNI, visa) at an exact mm size (e.g. 23x32, 26x32, 35x45 mm) tiled on photo paper (10x15 cm / A6, 13x18, A4) as a print-ready PDF, from a phone selfie or portrait photo.
---

# ID Photo Sheet

## Overview

Crop a portrait to exact ID-photo proportions (face-centered, head ~75% of height) and tile copies on a photo-paper-sized PDF with cut guides. Pure PIL, no ImageMagick/reportlab needed.

## Workflow

1. **Check orientation.** iPhone photos often have NO EXIF orientation tag (`sips -g orientation` → `<nil>`) yet the pixels are sideways. Save a small rotated preview and LOOK at it (Read tool) — don't trust metadata:
   ```bash
   python3 -c "from PIL import Image; Image.open('IMG.jpeg').rotate(-90, expand=True).resize((450,600)).save('rot.jpg')"
   ```
   `rotate(-90)` = clockwise. If the face is upside down, try `90` or `180`.

2. **Measure landmarks visually** on the 600px-tall preview: crown (top of hair) Y, chin Y, face center X. Eyeball precision is fine (±10px).

3. **Generate:**
   ```bash
   python3 ~/.claude/skills/id-photo-sheet/make_id_sheet.py IMG.jpeg \
     --rotate cw --crown 35 --chin 420 --cx 245 \
     --photo-mm 23x32 --paper-mm 100x150 \
     -o foto-carnet.pdf --preview-out sheet.jpg
   ```
   Grid auto-fits (23x32 on 10x15 → 3x4 = 12 photos). Script prints verified PDF page size in mm and exits nonzero on mismatch.

4. **Verify visually.** Read the sheet preview JPG: head fills ~3/4 of each photo, small gap above hair, no black bars, grid centered.

5. **Tell the user the print settings** — this is where it fails in practice: print at **100% scale / actual size** (never "fit to page"), borderless, on the exact paper size used for `--paper-mm`.

## Defaults that match Spanish "fotografía de carnet" specs

- `--head-frac 0.75` (spec: face 70–80% of photo height)
- `--top-margin-frac 0.07`
- 600 DPI, 2mm gaps, light-gray cut guides

## Common sizes

| Use | --photo-mm |
|---|---|
| Spain oposiciones/carné variants | 23x32 |
| Spain DNI/passport | 26x32 |
| Schengen visa, most EU | 35x45 |
| US visa | 51x51 |

## Gotchas

- **Out-of-bounds crop → black bars.** If the crown is near the image edge, a zoomed-out crop (`head-frac` < ~0.7) can exceed the source. Script clamps automatically, but re-check the preview and the printed "head fraction" line; the WARNING outside 0.60–0.85 means reshoot or adjust landmarks.
- **PIL PDF page size** comes from `resolution=` in `save()` — pixel size ÷ DPI. Script cross-checks the MediaBox; trust its printed mm values.
- Cream/off-white wall backgrounds usually pass; if the authority demands pure white, warn the user before printing.
