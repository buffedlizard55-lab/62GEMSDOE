#!/usr/bin/env python3
"""H63M — the final lane-63 emission: multi-channel lineament corroboration, measured.

Physical basis
--------------
A fault that is absent from the USGS/INGENIOUS catalogue is still a *structure*, and a
structure has three expressions that a smooth background does not:

1. a **break in slope / scarp** on the land surface                 (DEM curvature, TPI);
2. an **elongated ridge or trough** -- a shutter ridge, a beheaded spur, a linear
   drainage offset, a shoreline bench trimmed by a strand             (multiscale Hessian,
   orientation-maximised matched filter);
3. an **edge in the potential fields** where the fault offsets magnetic or dense
   basement                                                          (TMI horizontal and
   vertical gradient, tilt angle, isostatic-gravity gradients).

Each channel is computed without reading the catalogue, so nothing can leak.  The
channels are combined by **rank average** (not by weighted sum of raw amplitudes: the
amplitudes are on incomparable scales and the tails are wildly non-Gaussian), which is
equivalent to requiring that several physically independent expressions corroborate the
same cell.  That is the "corroboration" design the group's own best-scoring family
(``h19-5 multiline corroborated``, 0.26) reports using.

Selection statistic
-------------------
`evidence/h63_calibration.json`: across nine score-anchored registry rasters spanning
0.1563 - 0.2778, credit-per-unit-mass measured against the USGS SGMC *off-catalogue*
fault set, ``cm_proxy``, tracks the owner-reported live score almost monotonically, and
the implied transfer ratio ``r = cm_hidden / cm_proxy`` has median 0.775
(IQR 0.764 - 0.790).  Both facts are used here, and both are labelled MODEL.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
K_PLAN = 9400.0
R_TRANSFER = 0.775           # MODEL, from evidence/h63_calibration.json


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def nms_peaks(p, radius_px, valid):
    size = 2 * int(radius_px) + 1
    mx = ndi.maximum_filter(np.where(valid, p, -np.inf), size=size, mode="constant", cval=-np.inf)
    return valid & np.isfinite(p) & (p >= mx) & (p > 0)


def topk(mask, p, k):
    idx = np.flatnonzero(mask.ravel())
    if idx.size <= k:
        return mask
    v = p.ravel()[idx]
    keep = idx[np.argpartition(-v, k - 1)[:k]]
    o = np.zeros(mask.size, dtype=bool)
    o[keep] = True
    return o.reshape(mask.shape)


def rank01(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Average-rank normalisation to [0, 1] inside `valid`; 0 outside."""
    out = np.zeros(a.shape, np.float32)
    v = a[valid]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, np.float64)
    r[order] = np.arange(1, v.size + 1, dtype=np.float64)
    u, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        s = np.zeros(u.size)
        np.add.at(s, inv, r)
        r = (s / cnt)[inv]
    out[valid] = (r / r.size).astype(np.float32)
    out[~valid] = 0.0
    return out


def frangi_like(z, valid, scales=(1.0, 2.0, 4.0)):
    from skimage.feature import hessian_matrix, hessian_matrix_eigvals
    zf = np.where(valid, z, 0.0).astype(np.float32)
    ridge = np.zeros(zf.shape, np.float32)
    valley = np.zeros(zf.shape, np.float32)
    for s in scales:
        H = hessian_matrix(zf, sigma=s, mode="nearest", order="rc")
        l1, l2 = hessian_matrix_eigvals(H)
        np.maximum(ridge, np.where(l2 < 0, -l2, 0.0).astype(np.float32), out=ridge)
        np.maximum(valley, np.where(l1 > 0, l1, 0.0).astype(np.float32), out=valley)
    return ridge, valley


def directional_line(z, valid, n_angles=8, sigma=1.5):
    zs = ndi.gaussian_filter(np.where(valid, z, 0.0).astype(np.float32), sigma, mode="nearest")
    out = np.zeros(zs.shape, np.float32)
    wn5 = (-2.0, 1.0, 2.0, 1.0, -2.0)
    wt5 = (1.0, 2.0, 3.0, 2.0, 1.0)
    for k in range(n_angles):
        th = np.pi * k / n_angles
        c, s = np.cos(th), np.sin(th)
        acc = np.zeros(zs.shape, np.float32)
        for dn in (-2, -1, 0, 1, 2):
            for dt in (-2, -1, 0, 1, 2):
                dy = int(round(dn * (-s) + dt * c))
                dx = int(round(dn * c + dt * s))
                acc += wn5[dn + 2] * wt5[dt + 2] * np.roll(np.roll(zs, dy, 0), dx, 1)
        np.maximum(out, np.abs(acc), out=out)
    return out


def build_channels(dem, bands, usable):
    """bands: dict name -> (H, W) float32 grid (NaN outside)."""
    ch = {}
    ridge, valley = frangi_like(dem, usable)
    ch["dem_scarp_curvature"] = np.abs(ndi.laplace(
        np.where(usable, dem, 0.0).astype(np.float32), mode="nearest")).astype(np.float32)
    ch["dem_local_relief_tpi3"] = np.abs(
        np.where(usable, dem, 0.0).astype(np.float32)
        - ndi.uniform_filter(np.where(usable, dem, 0.0).astype(np.float32), 7, mode="nearest")
    ).astype(np.float32)
    ch["dem_local_relief_tpi9"] = np.abs(
        np.where(usable, dem, 0.0).astype(np.float32)
        - ndi.uniform_filter(np.where(usable, dem, 0.0).astype(np.float32), 19, mode="nearest")
    ).astype(np.float32)
    ch["dem_ridge_hessian"] = ridge
    ch["dem_valley_hessian"] = valley
    ch["dem_direction_line"] = directional_line(dem, usable)
    gy, gx = np.gradient(np.where(usable, dem, 0.0).astype(np.float32))
    ch["dem_slope"] = np.hypot(gx, gy).astype(np.float32)
    for nm in ("stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg", "stack_tmi_vg",
               "stack_iso_grav_anom_vg", "stack_det_elev_slope", "stack_geod_2ndinv",
               "stack_geod_shearrate", "stack_mag_anom", "stack_rtp", "stack_tmi"):
        a = bands.get(nm)
        if a is None:
            continue
        b = np.where(usable, a, 0.0).astype(np.float32)
        ch[nm] = np.abs(np.nan_to_num(b, nan=0.0, posinf=0.0, neginf=0.0)).astype(np.float32)
    for k, v in ch.items():
        v[~usable] = 0.0
    return ch


def band_grid(X, usable, names, nm):
    """Materialise one design column as a (H, W) float32 grid, NaN outside."""
    g = np.full((HEIGHT, WIDTH), np.nan, np.float32)
    g[usable] = X[:, names.index(nm)]
    return g


def iter_channels(usable, X, names):
    """Yield (name, (H, W) float32 channel) one at a time -- peak memory stays low."""
    dem = band_grid(X, usable, names, "dem_elev")
    ridge, valley = frangi_like(dem, usable)
    yield "dem_ridge_hessian", ridge
    del ridge
    yield "dem_valley_hessian", valley
    del valley
    a = np.where(usable, dem, 0.0).astype(np.float32)
    yield "dem_scarp_curvature", np.abs(ndi.laplace(a, mode="nearest")).astype(np.float32)
    for r in (3, 9):
        yield f"dem_local_relief_tpi{r}", np.abs(
            a - ndi.uniform_filter(a, size=2 * r + 1, mode="nearest")).astype(np.float32)
    yield "dem_direction_line", directional_line(dem, usable)
    del a, dem
    for nm in ("stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg", "stack_tmi_vg",
               "stack_iso_grav_anom_vg", "stack_det_elev_slope", "stack_geod_2ndinv"):
        b = np.where(usable, band_grid(X, usable, names, nm), 0.0).astype(np.float32)
        yield nm, np.abs(np.nan_to_num(b, nan=0.0, posinf=0.0, neginf=0.0)).astype(np.float32)
        del b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="measure", choices=["measure", "emit"])
    ap.add_argument("--channels", default="")
    ap.add_argument("--mass", type=int, default=40000)
    ap.add_argument("--nms", type=int, default=2)
    ap.add_argument("--offcat-m", type=int, default=300)
    ap.add_argument("--out-name", default="gems62-h63-multiline-corroborated")
    args = ap.parse_args()

    t0 = time.time()
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    names = json.loads((OUT / "feature_names.json").read_text())
    sh = json.loads((OUT / "design_shape.json").read_text())
    n, nf = sh["n_rows"], sh["n_cols"]
    X = np.memmap(OUT / "design.f32", dtype=np.float32, mode="r", shape=(n, nf))
    log("data loaded")

    dcat = (ndi.distance_transform_edt(~cat) * PIXEL_M).astype(np.float32)
    offcat = usable & (dcat >= args.offcat_m)

    def measure(mask, tag, extra=None):
        m = mask & usable
        S = float(m.sum())
        rec = {"tag": tag, "mass": S}
        for tn, t in (("proxy_off", pro), ("catalogue", cat)):
            c = dti_components(m.astype(np.float32), t, valid=usable,
                               pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
            rec[tn] = {"tp": round(c.tp_w, 2), "fp": round(c.fp_w, 2), "K": round(c.tp_w + c.fn_w, 1),
                       "dti": round(c.dti, 5), "cm": round(c.tp_w / S, 5) if S else 0.0}
        # MODEL projection through the calibrated transfer (never a score)
        if S:
            cmh = R_TRANSFER * rec["proxy_off"]["cm"]
            rec["model"] = {"cm_hidden": round(cmh, 5),
                            "projected_dti": round(cmh / (ALPHA + BETA * K_PLAN / S), 4),
                            "class": "MODEL (r=0.775, K=9400)"}
        if extra:
            rec.update(extra)
        return rec

    rows = []
    rng = np.random.default_rng(62)
    flat = np.flatnonzero(offcat.ravel())
    for M in (20000, 40000, 60000, 90000):
        c = np.zeros(offcat.size, bool)
        c[flat[rng.choice(flat.size, size=min(M, flat.size), replace=False)]] = True
        rows.append(measure(c.reshape(offcat.shape), f"CONTROL_random_offcat{M//1000}k"))

    combos = {
        "geo3": ["stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg"],
        "geo5": ["stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg", "stack_tmi_vg",
                 "stack_iso_grav_anom_vg"],
        "dem3": ["dem_scarp_curvature", "dem_local_relief_tpi3", "dem_direction_line"],
        "dem5": ["dem_scarp_curvature", "dem_local_relief_tpi3", "dem_local_relief_tpi9",
                 "dem_ridge_hessian", "dem_direction_line"],
        "geo5+dem5": ["stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg", "stack_tmi_vg",
                      "stack_iso_grav_anom_vg", "dem_scarp_curvature", "dem_local_relief_tpi3",
                      "dem_local_relief_tpi9", "dem_ridge_hessian", "dem_direction_line"],
        "geo3+dem3": ["stack_tmi_hg", "stack_tc", "stack_iso_grav_anom_hg",
                      "dem_scarp_curvature", "dem_local_relief_tpi3", "dem_direction_line"],
        "all": None,
    }
    acc = {k: np.zeros((HEIGHT, WIDTH), np.float32) for k in combos}
    cnt = {k: 0 for k in combos}
    seen = []

    def measure_channel(nm, rk):
        for nmsr in (2, 4):
            pk = nms_peaks(np.where(offcat, rk, -np.inf), nmsr, offcat)
            m = topk(pk, rk, 40000)
            if int(m.sum()) >= 100:
                rows.append(measure(m, f"{nm}|nms{nmsr}"))
        last = rows[-1]
        log(f"  {nm:26s} cm_proxy={last['proxy_off']['cm']:.4f} "
            f"cm_cat={last['catalogue']['cm']:.4f}")

    for nm, chan in iter_channels(usable, X, names):
        chan[~usable] = 0.0
        rk = rank01(chan, usable)
        del chan
        seen.append(nm)
        if args.stage == "measure":
            measure_channel(nm, rk)
        for cn, ks in combos.items():
            if ks is None or nm in ks:
                acc[cn] += rk
                cnt[cn] += 1
        del rk

    log("channels: " + ", ".join(seen))
    for cn in combos:
        if cnt[cn] == 0:
            continue
        a = acc[cn] / cnt[cn]
        np.save(OUT / f"h63_belief_{cn.replace('+', '_')}.npy", a.astype(np.float32))
        for nmsr in (2, 4):
            pk = nms_peaks(np.where(offcat, a, -np.inf), nmsr, offcat)
            for M in (20000, 40000, 60000, 90000):
                m = topk(pk, a, M)
                if int(m.sum()) < 100:
                    continue
                rows.append(measure(m, f"{cn}|nms{nmsr}"))
        best = max((r for r in rows if r["tag"].startswith(cn + "|")),
                   key=lambda r: r["model"]["projected_dti"])
        log(f"  {cn:12s}({cnt[cn]} ch) best M={best['mass']:.0f} "
            f"cm_proxy={best['proxy_off']['cm']:.4f} cm_cat={best['catalogue']['cm']:.4f} "
            f"proj_dti={best['model']['projected_dti']:.4f}")
    combos_used = {k: (v if v is not None else seen) for k, v in combos.items()}

    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("MEASURED (cm vs USGS SGMC off-catalogue faults and vs the "
                           "competition catalogue; exact 300 m kernel, src/gems62/metric.py) "
                           "+ MODEL (the r=0.775 transfer and K=9400 projection; never a score)"),
        "offcat_m": args.offcat_m,
        "channels": seen,
        "combos": {k: v for k, v in combos_used.items()},
        "rows": rows,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_emit_measure.json").write_text(json.dumps(res, indent=1))
    log("wrote " + str(EV / "h63_emit_measure.json"))

    ranked = sorted((r for r in rows if r["tag"] != "CONTROL"),
                    key=lambda d: -d["model"]["projected_dti"])
    log("\nTOP 12 by MODEL projected DTI:")
    for r in ranked[:12]:
        log(f"  {r['tag']:28s} M={r['mass']:7.0f} cm_proxy={r['proxy_off']['cm']:.4f} "
            f"cm_cat={r['catalogue']['cm']:.4f} proj={r['model']['projected_dti']:.4f}")
    log("\nCONTROLS (random, off-catalogue >= %d m):" % args.offcat_m)
    for r in rows:
        if r["tag"].startswith("CONTROL"):
            log(f"  {r['tag']:28s} M={r['mass']:7.0f} cm_proxy={r['proxy_off']['cm']:.4f} "
                f"cm_cat={r['catalogue']['cm']:.4f} proj={r['model']['projected_dti']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
