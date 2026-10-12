#!/usr/bin/env python3
"""H63M — write, certify and describe the submission raster.

The emission decided by ``evidence/h63_policy.json``:
  belief  = dem3  = rank-average of {dem_scarp_curvature, dem_local_relief_tpi3,
                                     dem_direction_line}   (all catalogue-free)
  NMS     = radius 1 (peaks in a 3x3 window -> dots ~200-300 m apart along a lineament)
  mass    = 90,000 cells, the arg-max of the *pessimistic* projection
  domain  = cells >= 300 m from the USGS/INGENIOUS catalogue (which is masked from
            scoring, so mass spent on it is mass wasted)
  value   = 1.0 on emitted cells, 0.0 elsewhere, 0.0 outside the footprint, no nodata tag
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.grid import (  # noqa: E402
    write_submission, check_submission, HEIGHT, WIDTH, PIXEL_M, sha256,
)
from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.validate import validate_submission  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
DL = HERE / "lane62-h63m" / "docs" / "downloads"

FIELD = "dem3"
RADIUS_PX = 1
MASS = 90_000
OFFCAT_M = 300
NAME = "gems62-h63m-multiline-corroborated-90000"


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def nms_peaks(p, radius_px, valid):
    if radius_px <= 0:
        return valid & np.isfinite(p) & (p > 0)
    size = 2 * int(radius_px) + 1
    mx = ndi.maximum_filter(np.where(valid, p, -np.inf), size=size, mode="constant", cval=-np.inf)
    return valid & np.isfinite(p) & (p >= mx) & (p > 0)


def topk(mask, p, k):
    idx = np.flatnonzero(mask.ravel())
    if idx.size <= k:
        return mask
    v = p.ravel()[idx]
    keep = idx[np.argpartition(-v, k - 1)[:k]]
    o = np.zeros(mask.size, bool)
    o[keep] = True
    return o.reshape(mask.shape)


def main() -> int:
    t0 = time.time()
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    belief = np.load(OUT / f"h63_belief_{FIELD}.npy")

    dcat = (ndi.distance_transform_edt(~cat) * PIXEL_M).astype(np.float32)
    offcat = usable & (dcat >= OFFCAT_M)
    pk = nms_peaks(np.where(offcat, belief, -np.inf), RADIUS_PX, offcat)
    dots = topk(pk, belief, MASS) & usable
    log(f"emitted {int(dots.sum())} cells")

    arr = np.zeros((HEIGHT, WIDTH), np.float32)
    arr[dots] = 1.0
    # everything outside `usable` stays 0.0 -> all-finite, no nodata tag, values in [0,1].

    DL.mkdir(parents=True, exist_ok=True)
    path = DL / f"{NAME}-zeros.tif"
    rec = write_submission(path, arr)
    log("format receipt: " + json.dumps({k: rec[k] for k in
        ("file", "bytes", "sha256", "dtype", "crs_match", "transform_match", "all_finite",
         "min", "max", "n_outside_0_1", "n_positive", "nodata", "legal")}))

    with __import__("rasterio").open(path) as s:
        back = s.read(1)
    rep = validate_submission(path, usable)
    log("validator: passed=%s failures=%s" % (rep.passed, rep.failures))

    # ---- measured statistics of the shipped raster ------------------------------
    S = float(arr.sum())
    stats = {"mass": S, "n_dots": int(dots.sum())}
    for tn, t in (("proxy_off", pro), ("catalogue", cat)):
        c = dti_components(arr, t, valid=usable, pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
        stats[tn] = {"tp_w": round(c.tp_w, 2), "fp_w": round(c.fp_w, 2),
                     "K": round(c.tp_w + c.fn_w, 1), "dti": round(c.dti, 5),
                     "credit_per_mass": round(c.tp_w / S, 5)}
    dcat_m = dcat[dots]
    stats["geometry"] = {
        "median_dcat_m": float(np.median(dcat_m)),
        "frac_dcat_ge1000": float((dcat_m >= 1000).mean()),
        "frac_dcat_ge300": float((dcat_m >= 300).mean()),
        "mean_self_kernel": None,
    }
    # self-kernel redundancy (share of dots with another dot inside the 300 m kernel)
    best = np.zeros((HEIGHT, WIDTH), np.float32)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if (dy, dx) == (0, 0):
                continue
            d = np.hypot(dy, dx)
            if d > 3.0:
                continue
            best = np.maximum(best, np.roll(np.roll(arr, dy, 0), dx, 1) * (1 - d / 3.0))
    stats["geometry"]["mean_self_kernel"] = round(float(best[dots].mean()), 4)
    stats["geometry"]["redundancy_fraction"] = round(float((best[dots] > 0).mean()), 4)
    yy, xx = np.nonzero(dots)
    H, W = HEIGHT, WIDTH
    nb = 40
    hy = np.histogram2d(yy, xx, bins=[nb, nb], range=[[0, H], [0, W]])[0]
    p = hy.ravel() / hy.sum()
    p = p[p > 0]
    stats["spatial_entropy_nats"] = round(float(-(p * np.log(p)).sum()), 4)
    stats["blocks_occupied_of_1600"] = int((hy > 0).sum())

    # ---- quicklook PNG ---------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7.2, 8.2), dpi=110)
        ax.imshow(np.where(usable, 1.0, np.nan), cmap="Greys", vmin=0, vmax=2,
                  interpolation="nearest")
        ax.imshow(np.where(dots, 1.0, np.nan), cmap="autumn_r", interpolation="nearest")
        ax.set_title(f"{NAME}\n{int(dots.sum())} dots, >= {OFFCAT_M} m off the catalogue",
                     fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        png = DL.parent / "assets" / "h63_map.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png)
        plt.close(fig)
        log(f"quicklook -> {png}")
    except Exception as exc:                                     # pragma: no cover
        log(f"quicklook skipped: {exc}")

    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "submission": {"name": NAME, "path": str(path.relative_to(HERE)),
                       "sha256": rec["sha256"], "bytes": rec["bytes"]},
        "policy": {"field": FIELD, "nms_radius_px": RADIUS_PX, "mass_target": MASS,
                   "off_catalogue_m": OFFCAT_M, "value": 1.0},
        "format_receipt": rec,
        "validator": {"passed": rep.passed, "failures": rep.failures,
                      "unique_positive_values": rep.unique_positive_values,
                      "positive_cells": rep.positive_cells,
                      "outside_encoding": rep.outside_encoding,
                      "nan_inside_footprint": rep.nan_inside_footprint},
        "measured": stats,
        "evidence_class": ("MEASURED for every 'measured' key (exact 300 m kernel on the "
                           "two free truth proxies); the DTI columns are PROXY values, not "
                           "organiser scores"),
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_final.json").write_text(json.dumps(res, indent=1))
    log("wrote " + str(EV / "h63_final.json"))
    log("measured: " + json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
