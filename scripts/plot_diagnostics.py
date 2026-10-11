#!/usr/bin/env python3
"""Diagnostic figures for the datum-offset lane: does the detector sit on real shorelines?

Produces (a) a whole-region hillshade with the detected shoreline segments, the extended traces
and the known catalogue overplotted, and (b) zoom panels on the strongest loci, so a human can
check the claim instead of trusting the numbers.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import datum  # noqa: E402


def hillshade(z, az=315.0, alt=45.0):
    dy, dx = np.gradient(z.astype(np.float32))
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    azr = np.radians(360.0 - az + 90.0); altr = np.radians(alt)
    shaded = (np.sin(altr) * np.sin(slope) + np.cos(altr) * np.cos(slope)
              * np.cos(azr - aspect))
    fin = np.isfinite(shaded)
    lo, hi = np.nanpercentile(shaded[fin], [2, 98]) if fin.any() else (0, 1)
    out = np.clip((shaded - lo) / max(hi - lo, 1e-6), 0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--emission")
    ap.add_argument("--catalogue")
    ap.add_argument("--out-dir", default="docs/assets")
    ap.add_argument("--name", default="lane")
    args = ap.parse_args()

    import rasterio
    from PIL import Image, ImageDraw

    out = pathlib.Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    src = rasterio.open(args.dem)
    H, W = src.height, src.width
    dec = max(1, H // 1400)
    z = src.read(1)[::dec, ::dec].astype(np.float32) * 0.1
    z[z <= -3200] = np.nan
    hs = hillshade(z)
    rgb = np.stack([hs, hs, hs], -1)
    rgb = np.where(np.isfinite(rgb), rgb, 0.25)
    img = Image.fromarray((rgb * 255).astype(np.uint8))
    dr = ImageDraw.Draw(img)
    im_w, im_h = img.size

    def to_px(r, c):
        return (c / dec * (im_w / (W / dec)), r / dec * (im_h / (H / dec)))

    if args.catalogue:
        with rasterio.open(args.catalogue) as s:
            known = s.read(1) == 1
        kr, kc = np.nonzero(known)
        cm = np.zeros_like(known)
        # the catalogue is on the 100 m grid: map its rows/cols into DEM coordinates
        for r, c in zip(kr[::3], kc[::3]):
            x = 243350.0 + (c + 0.5) * 100.0
            y = 4508550.0 - (r + 0.5) * 100.0
            dc = (x - src.transform.c) / 25.0; drr = (src.transform.f - y) / 25.0
            if 0 <= drr < H and 0 <= dc < W:
                px = to_px(drr, dc)
                dr.ellipse([px[0] - 1, px[1] - 1, px[0] + 1, px[1] + 1], fill=(90, 160, 255))
    traces = json.loads(pathlib.Path(args.traces).read_text())["traces"]
    for t in traces:
        pts = [to_px(r - 0.5, c - 0.5) for r, c in t["rowcol"]]
        dr.line(pts, fill=(255, 60, 30), width=2)
        dr.ellipse([pts[0][0] - 3, pts[0][1] - 3, pts[0][0] + 3, pts[0][1] + 3], fill=(255, 230, 0))
    img.save(out / f"{args.name}_overview.png")
    print("wrote", out / f"{args.name}_overview.png", "traces:", len(traces))

    # zoom panel: strongest 4 traces, +/- 8 km
    order = sorted(range(len(traces)), key=lambda i: -traces[i].get("evidence", 0))[:4]
    panels = []
    for i in order:
        t = traces[i]
        r0, c0 = t["rowcol"][0]
        half = int(8000 / 25)
        rr0 = max(0, int(r0) - half); cc0 = max(0, int(c0) - half)
        zz = src.read(1, window=((rr0, min(H, int(r0) + half)), (cc0, min(W, int(c0) + half)))).astype(np.float32) * 0.1
        zz[zz <= -3200] = np.nan
        if not np.isfinite(zz).any():
            continue
        zz = np.where(np.isfinite(zz), zz, np.nanmean(zz))
        hzp = hillshade(zz)
        p = np.stack([hzp, hzp, hzp], -1)
        pan = Image.fromarray((p * 255).astype(np.uint8)).resize((520, 520))
        pdr = ImageDraw.Draw(pan)
        for r, c in t["rowcol"]:
            px = ((c - cc0) * 520 // (min(H, int(r0) + half) - rr0 if False else zz.shape[1]),
                  (r - rr0) * 520 // zz.shape[0])
            pdr.ellipse([px[0] - 2, px[1] - 2, px[0] + 2, px[1] + 2], fill=(255, 60, 30))
        pan.save(out / f"{args.name}_zoom{i}.png")
        panels.append(pan)
    if panels:
        sheet = Image.new("RGB", (520 * len(panels), 520), (0, 0, 0))
        for k, p in enumerate(panels):
            sheet.paste(p, (520 * k, 0))
        sheet.save(out / f"{args.name}_zooms.png")
        print("wrote", out / f"{args.name}_zooms.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
