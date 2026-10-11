"""Diagnostic figures for the datum-offset lane.

IR-62-11 FIX (2026-10-11).  ``tests/test_lane_instruments.py`` and
``scripts/make_figures.py`` both call ``run_lane.save_map_png`` /
``run_lane.save_profile_png``, but a later rewrite of ``scripts/run_lane.py`` replaced the
v99 pipeline and dropped those two writers, so the map-writer regression test failed with
``AttributeError`` on a clean checkout.  The writers are the same code the test was written
against (extracted verbatim from ``scripts/run_lane_v99_superseded.py``), moved here so that
*every* lane script shares one implementation instead of each keeping a private copy, and
re-exported from ``scripts/run_lane.py``.

Both writers are dependency-optional: if Pillow is not installed they return without
writing, because a figure is never load-bearing for a submission.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .grid import TRANSFORM


def save_profile_png(rows: list[dict], out: Path, title: str,
                     label: str = "", *, flags: list[dict] | None = None,
                     radius_m: dict | None = None) -> None:
    """Render the first deliverable: datum elevation and residual vs distance.

    Two panels, because the two questions are different:

    * top -- the datum elevation itself, against the smooth isobase.  The
      y-limits are set from the published deformed-highstand window and the
      2nd/98th percentile of the plotted values, **not** from the raw min/max:
      a single poorly-supported bench must not be able to set the scale.
    * bottom -- the residual (elevation minus isobase), which is where a step
      actually shows.  The +-3 m constructional band is drawn, and every
      flagged location is marked with its jump.

    The isobase is drawn as a broken polyline: consecutive benches in track
    order are only joined when they are genuinely adjacent along the track, so
    the curve shows the isobase rather than the gaps between distant benches.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return
    W, H = 1400, 860
    img = Image.new("RGB", (W, H), (12, 14, 20))
    d = ImageDraw.Draw(img)
    L, R = 96, W - 250
    d.text((14, 14), title, fill=(235, 240, 250))
    if label:
        d.text((14, 34), label, fill=(150, 160, 175))
    if not rows:
        d.text((L, 90), "no benches survived the datum filters", fill=(230, 120, 120))
        img.save(out)
        return

    xs = np.array([r["distance_track_m"] for r in rows], dtype=float)
    zs = np.array([r["elevation_m"] for r in rows], dtype=float)
    ib = np.array([r["isobase_m"] for r in rows], dtype=float)
    res = np.array([r["residual_m"] for r in rows], dtype=float)
    x0, x1 = 0.0, max(xs.max(), 1.0)
    flag_x = np.array([f["distance_track_m"] for f in (flags or [])], dtype=float)
    flag_j = np.array([f["residual_jump_m"] for f in (flags or [])], dtype=float)

    # Highstand window from the literature, widened to include the 2-98 pct of
    # what is actually plotted, so a single outlier cannot set the scale.
    lo_z = min(np.percentile(zs, 2), float(np.percentile(ib, 2))) - 2.0
    hi_z = max(np.percentile(zs, 98), float(np.percentile(ib, 98))) + 2.0
    panel_h = 250
    T1, B1 = 78, 78 + panel_h
    T2, B2 = B1 + 96, B1 + 96 + panel_h
    lo_r = min(float(np.percentile(res, 2)), -6.0) - 1.0
    hi_r = max(float(np.percentile(res, 98)), 14.0) + 1.0

    def px(v):
        return L + (v - x0) / max(x1 - x0, 1e-9) * (R - L)

    def clamp(v, lo, hi):
        return float(min(max(v, lo), hi))

    for (T, B, lo, hi, lbl) in ((T1, B1, lo_z, hi_z, "elevation (m)"),
                                (T2, B2, lo_r, hi_r, "residual (m)")):
        def py(v, T=T, B=B, lo=lo, hi=hi):
            return B - (clamp(v, lo, hi) - lo) / max(hi - lo, 1e-9) * (B - T)
        for i in range(5):
            v = lo + (hi - lo) * i / 4
            y = py(v)
            d.line([(L, y), (R, y)], fill=(38, 42, 54))
            d.text((12, y - 6), f"{v:8.1f}", fill=(150, 160, 175))
        d.text((12, T - 20), lbl, fill=(170, 180, 195))
    n_ticks = 8
    for i in range(n_ticks + 1):
        v = x0 + (x1 - x0) * i / n_ticks
        x = px(v)
        d.line([(x, T1), (x, B2)], fill=(28, 32, 42))
        d.text((x - 20, B2 + 8), f"{v/1000:5.1f}", fill=(150, 160, 175))
    d.text(((L + R) / 2 - 80, B2 + 34), "along-shoreline distance (km)", fill=(200, 208, 220))

    def py1(v):
        return B1 - (clamp(v, lo_z, hi_z) - lo_z) / max(hi_z - lo_z, 1e-9) * (B1 - T1)

    def py2(v):
        return B2 - (clamp(v, lo_r, hi_r) - lo_r) / max(hi_r - lo_r, 1e-9) * (B2 - T2)

    order = np.argsort(xs)
    # broken polyline: only join benches that are adjacent along the track
    seg: list[tuple[float, float]] = []
    for k, i in enumerate(order):
        gap_track = xs[i] - xs[order[k - 1]]
        gap_plan = np.hypot(rows[i]["x"] - rows[order[k - 1]]["x"],
                            rows[i]["y"] - rows[order[k - 1]]["y"]) if k else 0.0
        if k and (gap_track > 3000.0 or gap_plan > 6000.0):
            if len(seg) > 1:
                d.line(seg, fill=(88, 132, 190))
            seg = []
        seg.append((px(xs[i]), py1(ib[i])))
    if len(seg) > 1:
        d.line(seg, fill=(88, 132, 190))
    for k, i in enumerate(order):
        col = (240, 200, 90) if abs(res[i]) >= lahontan.ELEVATION_RESOLUTION_M else (120, 210, 150)
        d.ellipse([px(xs[i]) - 3, py1(zs[i]) - 3, px(xs[i]) + 3, py1(zs[i]) + 3], fill=col)
        d.ellipse([px(xs[i]) - 2, py2(res[i]) - 2, px(xs[i]) + 2, py2(res[i]) + 2],
                  fill=(120, 160, 210))
    # +-3 m constructional band on the residual panel
    for v in (3.0, -3.0):
        y = py2(v)
        for x in range(int(L), int(R), 12):
            d.line([(x, y), (x + 6, y)], fill=(90, 96, 110))
    d.line([(L, py2(0.0)), (R, py2(0.0))], fill=(60, 66, 80))
    for k in range(flag_x.size):
        x = px(flag_x[k])
        y = py2(flag_j[k])
        d.line([(x, T2), (x, B2)], fill=(150, 110, 60))
        d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(240, 200, 90), width=2)
    cols = [((120, 210, 150), "datum, |res| < 3 m"),
            ((240, 200, 90), "datum, |res| >= 3 m"),
            ((88, 132, 190), "local isobase (z - res)"),
            ((120, 160, 210), "residual (z - isobase)"),
            ((240, 200, 90), "FLAGGED step (circled)")]
    for i, ((r, g, b), txt) in enumerate(cols):
        y = 52 + 14 * i
        d.text((R + 12, y), txt, fill=(r, g, b))
    if radius_m:
        d.text((R + 12, 52 + 14 * len(cols) + 6),
               f"step gate {radius_m.get('significance_gate_m', 0):.2f} m",
               fill=(150, 160, 175))
        d.text((R + 12, 52 + 14 * len(cols) + 20),
               f"resolution {radius_m.get('resolution_gate_m', 0):.0f} m",
               fill=(150, 160, 175))
        d.text((R + 12, 52 + 14 * len(cols) + 34),
               f"accepted {radius_m.get('pairs_accepted', 0)}"
               f" / borderline {radius_m.get('pairs_rejected_as_borderline', 0)}",
               fill=(150, 160, 175))
    img.save(out)


def save_map_png(dem, footprint, catalogue, band, dots, out: Path, *,
                 flags: list[dict] | None = None) -> None:
    """Spatial context figure: relief, the datum band, the catalogue, the dots.

    Drawn in two stages on purpose.  The context layers are rasterised at full
    grid resolution and then downsampled; the *markers* are drawn afterwards in
    output-pixel coordinates, because a one-pixel dot bleached out completely by
    a 4x bilinear reduction is invisible -- which is exactly what happened on the
    first version of this figure.  A reader must be able to see what was emitted.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return
    import rasterio

    H, W = dem.shape
    scale = 4
    dw, dh = W // scale, H // scale

    def norm(a, lo, hi):
        a = np.asarray(a, dtype=float)
        o = np.clip((a - lo) / (hi - lo), 0, 1)
        o[~np.isfinite(a)] = 0.0
        return o

    shade = norm(dem, 1050, 2200)
    rgb = np.stack([shade, shade, shade], axis=-1)
    sel = band & footprint
    rgb[sel] = rgb[sel] * 0.35 + np.array([0.15, 0.45, 0.85]) * 0.65
    rgb[catalogue] = np.array([0.95, 0.25, 0.25])
    base = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).resize(
        (dw, dh), Image.BILINEAR)

    # margin for the title, legend and scale bar
    pad_l, pad_t, pad_r, pad_b = 16, 54, 268, 54
    img = Image.new("RGB", (dw + pad_l + pad_r, dh + pad_t + pad_b), (12, 14, 20))
    img.paste(base, (pad_l, pad_t))
    d = ImageDraw.Draw(img)
    d.rectangle([pad_l, pad_t, pad_l + dw, pad_t + dh], outline=(60, 66, 80))

    def to_px(col, row):
        """Grid (col, row) -> output pixel.  Everything drawn goes through here."""
        return (pad_l + col / scale, pad_t + row / scale)

    def world_to_grid(X, Y):
        """Projected metres -> fractional (col, row) on this grid."""
        col = (X - TRANSFORM[2]) / TRANSFORM[0]
        row = (Y - TRANSFORM[5]) / TRANSFORM[4]
        return col, row

    def check_inside(x, y, what):
        # A silently off-canvas marker is indistinguishable from "nothing was
        # found"; the first version of this figure drew its step circle
        # 100,000 px away because world metres were fed to the grid helper.
        # x, y are image pixels, so the pad has to come off before comparing.
        if not (0.0 <= x - pad_l <= dw and 0.0 <= y - pad_t <= dh):
            raise ValueError(f"{what} drew at ({x - pad_l:.0f}, {y - pad_t:.0f}), outside "
                             f"the {dw}x{dh} map area -- wrong coordinate units?")

    dot_rows, dot_cols = np.nonzero(dots)
    for r, c in zip(dot_rows, dot_cols):
        x, y = to_px(c, r)
        d.ellipse([x - 2.0, y - 2.0, x + 2.0, y + 2.0], fill=(255, 216, 26))
    for f in flags or []:
        col, row = world_to_grid(f["x"], f["y"])
        x, y = to_px(col, row)
        check_inside(x, y, "step location")
        d.ellipse([x - 15, y - 15, x + 15, y + 15], outline=(255, 216, 26), width=3)
        d.text((x + 18, y - 6), f"STEP {f['jump_m']:+.1f} m", fill=(255, 216, 26))

    d.text((pad_l, 16), "Lake Lahontan highstand datum: mapped benches, catalogue and emitted dots",
           fill=(235, 240, 250))
    d.text((pad_l, 34), f"{int(sel.sum()):,} datum cells · {int(catalogue.sum()):,} catalogue cells · "
                        f"{int(dots.sum()):,} emitted dots", fill=(150, 160, 175))

    legend = [((150, 190, 240), "highstand datum band (1313.5-1345.8 m)"),
              ((242, 64, 64), "USGS / INGENIOUS catalogue"),
              ((255, 216, 26), "emitted dots"),
              ((255, 216, 26), "circled: surviving step location")]
    for i, (col, txt) in enumerate(legend):
        y = pad_t + 8 + 20 * i
        d.rectangle([pad_l + dw + 14, y + 4, pad_l + dw + 26, y + 14], fill=col)
        d.text((pad_l + dw + 32, y), txt, fill=(200, 208, 220))

    # scale bar: 50 km = 500 cells / scale px
    bar_px = 50_000 / 100.0 / scale
    y = pad_t + dh - 22
    d.line([(pad_l + 20, y), (pad_l + 20 + bar_px, y)], fill=(235, 240, 250), width=4)
    d.text((pad_l + 20, y - 18), "50 km", fill=(235, 240, 250))
    # north arrow (north is -row)
    ax, ay = pad_l + dw - 34, pad_t + 34
    d.line([(ax, ay + 18), (ax, ay - 10)], fill=(235, 240, 250), width=3)
    d.polygon([(ax, ay - 18), (ax - 6, ay - 6), (ax + 6, ay - 6)], fill=(235, 240, 250))
    d.text((ax - 4, ay + 22), "N", fill=(235, 240, 250))
    img.save(out)


