#!/usr/bin/env python3
"""Compose an ID-photo sheet PDF: N copies of a face-cropped photo tiled on photo paper.

Landmarks (crown, chin, face-center-x) are pixel coords measured on a preview
whose HEIGHT is --preview-h (default 600). The agent reads the preview image
visually and estimates them; the script scales to full resolution.

Example:
  python3 make_id_sheet.py IMG.jpeg --rotate cw --crown 35 --chin 420 --cx 245 \
      --photo-mm 23x32 --paper-mm 100x150 -o out.pdf
"""
import argparse
import re
import sys

from PIL import Image, ImageDraw


def parse_mm(s):
    w, h = s.lower().split("x")
    return float(w), float(h)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    p.add_argument("-o", "--output", required=True, help="output PDF path")
    p.add_argument("--rotate", choices=["none", "cw", "ccw", "180"], default="none",
                   help="rotation to make the face upright (iPhone photos often lack EXIF)")
    p.add_argument("--crown", type=float, required=True, help="top-of-head Y on preview")
    p.add_argument("--chin", type=float, required=True, help="chin Y on preview")
    p.add_argument("--cx", type=float, required=True, help="face center X on preview")
    p.add_argument("--preview-h", type=float, default=600)
    p.add_argument("--photo-mm", default="23x32", help="single photo WxH in mm")
    p.add_argument("--paper-mm", default="100x150", help="sheet WxH in mm (10x15cm=100x150)")
    p.add_argument("--head-frac", type=float, default=0.75,
                   help="head height as fraction of photo height (ID standard ~0.70-0.80)")
    p.add_argument("--top-margin-frac", type=float, default=0.07,
                   help="space above crown as fraction of photo height")
    p.add_argument("--dpi", type=int, default=600)
    p.add_argument("--gap-mm", type=float, default=2.0)
    p.add_argument("--edge-margin-mm", type=float, default=4.0,
                   help="min blank border; borderless printers overscan ~2-3mm")
    p.add_argument("--preview-out", help="optional JPG preview of the sheet")
    args = p.parse_args()

    im = Image.open(args.image)
    rot = {"none": 0, "cw": -90, "ccw": 90, "180": 180}[args.rotate]
    if rot:
        im = im.rotate(rot, expand=True)

    s = im.height / args.preview_h
    crown, chin, cx = int(args.crown * s), int(args.chin * s), int(args.cx * s)
    head = chin - crown
    if head <= 0:
        sys.exit("chin must be below crown in preview coords")

    pw_mm, ph_mm = parse_mm(args.photo_mm)
    # Clamp crop to image bounds — never let it go negative (black bars).
    H = min(int(head / args.head_frac), im.height)
    W = int(H * pw_mm / ph_mm)
    if W > im.width:
        W = im.width
        H = int(W * ph_mm / pw_mm)
    top = max(0, min(crown - int(args.top_margin_frac * H), im.height - H))
    x0 = min(max(0, cx - W // 2), im.width - W)
    crop = im.crop((x0, top, x0 + W, top + H))
    eff = head / H
    print(f"crop {crop.size} at ({x0},{top}); head fraction {eff:.2f}")
    if not 0.60 <= eff <= 0.85:
        print("WARNING: head fraction outside 0.60-0.85 — check landmarks/source framing")

    mm = args.dpi / 25.4
    tpw, tph = round(pw_mm * mm), round(ph_mm * mm)
    tile = crop.resize((tpw, tph), Image.LANCZOS)

    sw_mm, sh_mm = parse_mm(args.paper_mm)
    SW, SH = round(sw_mm * mm), round(sh_mm * mm)
    gap = round(args.gap_mm * mm)
    edge = round(args.edge_margin_mm * mm)
    cols = int((SW - 2 * edge + gap) // (tpw + gap))
    rows = int((SH - 2 * edge + gap) // (tph + gap))
    if cols < 1 or rows < 1:
        sys.exit("photo does not fit on paper")

    sheet = Image.new("RGB", (SW, SH), "white")
    d = ImageDraw.Draw(sheet)
    ox = (SW - (cols * tpw + (cols - 1) * gap)) // 2
    oy = (SH - (rows * tph + (rows - 1) * gap)) // 2
    for r in range(rows):
        for c in range(cols):
            x, y = ox + c * (tpw + gap), oy + r * (tph + gap)
            sheet.paste(tile, (x, y))
            d.rectangle([x - 2, y - 2, x + tpw + 1, y + tph + 1],
                        outline=(180, 180, 180), width=2)

    sheet.save(args.output, "PDF", resolution=args.dpi)
    if args.preview_out:
        pv_h = 750
        sheet.resize((round(SW * pv_h / SH), pv_h)).save(args.preview_out, quality=88)

    data = open(args.output, "rb").read()
    m = re.search(rb"MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", data)
    w_mm, h_mm = float(m.group(3)) / 72 * 25.4, float(m.group(4)) / 72 * 25.4
    print(f"{args.output}: page {w_mm:.1f}x{h_mm:.1f} mm, {cols}x{rows}={cols*rows} photos "
          f"of {pw_mm:g}x{ph_mm:g} mm")
    if abs(w_mm - sw_mm) > 0.5 or abs(h_mm - sh_mm) > 0.5:
        sys.exit("PDF page size mismatch — check dpi/resolution handling")


if __name__ == "__main__":
    main()
