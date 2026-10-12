#!/usr/bin/env python3
"""H63M — catalogue-free lineament detectors, measured on two free truth proxies.

Why catalogue-free: a detector that never reads the catalogue cannot leak it, so the
whole catalogue (and the whole SGMC off-catalogue set) can be used as the instrument
instead of a held-out slice.  This is the direct consequence of `h63_train.py`: a
*supervised* pixel classifier on the 19-band stack reaches AUC 0.50 on held-out
spatial blocks, i.e. no spatially transferable signal (evidence/h63a_emission.json).

Truth proxies (both free and official):
  ``proxy_off``  USGS SGMC faults absent from the competition catalogue (61,664 px).
                 This is the population the competition actually scores.
  ``catalogue``  the competition's own training labels (60,988 px).

Measured statistic: **credit per unit emitted mass**, T/S, at matched mass, with the
exact 300 m triangular kernel.  DTI = T / (alpha*S + beta*K) for an emission whose
kernel mass equals its credit, so T/S at fixed K is the whole ranking.
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

from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
MASSES = [20_000, 40_000, 60_000, 90_000]


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


def robust(a, valid):
    v = a[valid & np.isfinite(a)]
    lo, hi = np.percentile(v, [2, 98])
    return np.clip(a, lo, hi)


# ------------------------------------------------------------------ detectors
def frangi_like(z, valid, scales=(1.0, 2.0, 4.0)):
    """Multiscale ridge AND valley strength from the DEM Hessian.

    For each scale: Hessian H of the smoothed elevation; let |l1| <= |l2| be the
    eigenvalues.  Ridge strength = -l2 where l2 < 0 (elongated crest);
    valley strength =  l1 where l1 > 0 (elongated trough).  Lineament strength is
    the larger of the two, which is what a fault scarp, a shutter ridge, a beheaded
    drainage and a shoreline bench all share.
    """
    from skimage.feature import hessian_matrix, hessian_matrix_eigvals
    zf = np.where(valid, z, 0.0).astype(np.float32)
    ridge = np.zeros(zf.shape, np.float32)
    valley = np.zeros(zf.shape, np.float32)
    for s in scales:
        H = hessian_matrix(zf, sigma=s, mode="nearest", order="rc")
        l1, l2 = hessian_matrix_eigvals(H)
        # hessian_matrix_eigvals returns (i0, i1) with |i0| <= |i1|
        r = np.where(l2 < 0, -l2, 0.0).astype(np.float32)
        v = np.where(l1 > 0, l1, 0.0).astype(np.float32)
        np.maximum(ridge, r, out=ridge)
        np.maximum(valley, v, out=valley)
    return ridge, valley


def directional_line(z, valid, n_angles=8, half=6, sigma=1.5):
    """Max response over orientations of an elongated 2nd-derivative (matched) filter.

    Classic lineament mapper: smooth along a line, differentiate across it.  Taking the
    maximum over orientations makes it rotation-invariant and picks out straight
    features, which is the geometric signature a fault trace has and a drainage divide
    does not.
    """
    zs = ndi.gaussian_filter(np.where(valid, z, 0.0).astype(np.float32), sigma, mode="nearest")
    out = np.zeros(zs.shape, np.float32)
    for k in range(n_angles):
        th = np.pi * k / n_angles
        c, s = np.cos(th), np.sin(th)
        # unit vector along the line
        t = np.array([c, s])
        n = np.array([-s, c])
        # build a separable-ish kernel by rotating: sample zs along t and n
        offs = np.arange(-half, half + 1)
        # second derivative across the line (n), average along the line (t)
        acc = np.zeros(zs.shape, np.float32)
        wsum = 0.0
        for dt in offs:
            sh = (int(round(n[0] * 0)), 0)
        # implement by explicit shifted sums (small kernel, 8 orientations)
        for dn in (-2, -1, 0, 1, 2):
            wn = (-2.0, 1.0, 2.0, 1.0, -2.0)[dn + 2]
            for dt in (-2, -1, 0, 1, 2):
                wt = (1.0, 2.0, 3.0, 2.0, 1.0)[dt + 2]
                dy = int(round(dn * n[0] + dt * t[0]))
                dx = int(round(dn * n[1] + dt * t[1]))
                acc += wn * wt * np.roll(np.roll(zs, dy, axis=0), dx, axis=1)
                wsum += abs(wn * wt) if dn == 0 else 0.0
        np.maximum(out, np.abs(acc), out=out)
    return out


def build_fields(dem, stack_by_name, usable):
    """Return {name: (H, W) float32 field, higher = more fault-like}."""
    valid = usable
    ridge, valley = frangi_like(dem, valid)
    fields = {
        "dem_ridge_frangi": ridge,
        "dem_valley_frangi": valley,
        "dem_lineament_max": np.maximum(ridge, valley),
    }
    gy, gx = np.gradient(np.where(valid, dem, 0.0).astype(np.float32))
    fields["dem_slope"] = np.hypot(gx, gy).astype(np.float32)
    lap = ndi.laplace(np.where(valid, dem, 0.0).astype(np.float32), mode="nearest")
    fields["dem_abs_laplacian"] = np.abs(lap).astype(np.float32)
    for r in (3, 9, 21):
        tpi = np.where(valid, dem, 0.0).astype(np.float32) - ndi.uniform_filter(
            np.where(valid, dem, 0.0).astype(np.float32), size=2 * r + 1, mode="nearest")
        fields[f"dem_abs_tpi{r}"] = np.abs(tpi).astype(np.float32)
    fields["dem_direction_line"] = directional_line(dem, valid)

    for nm in ("tmi_hg", "tc", "iso_grav_anom_hg", "det_elev_slope", "tmi_vg",
               "iso_grav_anom_vg", "geod_2ndinv", "geod_shearrate"):
        a = stack_by_name.get(nm)
        if a is None:
            continue
        b = np.where(valid, a, np.nan).astype(np.float32)
        fields[f"stack_{nm}"] = np.nan_to_num(np.abs(np.nan_to_num(b)), nan=0.0)
    return fields


# ------------------------------------------------------------------ main
def main() -> int:
    t0 = time.time()
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    names = json.loads((OUT / "feature_names.json").read_text())
    _shape = json.loads((OUT / "design_shape.json").read_text())
    n, nf = _shape["n_rows"], _shape["n_cols"]
    X = np.memmap(OUT / "design.f32", dtype=np.float32, mode="r", shape=(n, nf))

    dem = np.full((HEIGHT, WIDTH), np.nan, np.float32)
    stack_by_name = {}
    for j, nm in enumerate(names):
        g = np.full((HEIGHT, WIDTH), np.nan, np.float32)
        g[usable] = X[:, j]
        stack_by_name[nm] = g
    dem = stack_by_name["dem_elev"].copy()
    log("DEM + bands loaded")

    fields = build_fields(dem, stack_by_name, usable)
    log("fields: " + ", ".join(sorted(fields)))

    # ---------------- where do NEW faults live, relative to the catalogue? ----------
    dcat = ndi.distance_transform_edt(~cat) * PIXEL_M
    geo = {}
    for nm, t in (("proxy_off", pro), ("catalogue", cat)):
        geo[nm] = {
            "n": int(t.sum()),
            "frac_dcat_lt300": float((dcat[t] < 300).mean()),
            "frac_dcat_300_1000": float(((dcat[t] >= 300) & (dcat[t] < 1000)).mean()),
            "frac_dcat_ge1000": float((dcat[t] >= 1000).mean()),
            "median_dcat_m": float(np.median(dcat[t])),
        }
    log("distance-to-catalogue distribution of the two truth populations: " + json.dumps(geo))

    truths = {"proxy_off": pro, "catalogue": cat}
    rows = []
    # random control at matched mass
    rng = np.random.default_rng(62)
    valid_flat = np.flatnonzero(usable.ravel())

    def measure(field_name, m):
        m = m & usable
        S = float(m.sum())
        rec = {"field": field_name, "mass": S}
        for tn, t in truths.items():
            c = dti_components(m.astype(np.float32), t, valid=usable,
                               pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
            rec[tn] = {"tp": round(c.tp_w, 2), "fp": round(c.fp_w, 2), "fn": round(c.fn_w, 2),
                       "K": round(c.tp_w + c.fn_w, 1),
                       "dti": round(c.dti, 5),
                       "credit_per_mass": round(c.tp_w / S, 5) if S else 0.0}
        return rec

    for M in MASSES:
        ctrl = np.zeros(usable.size, bool)
        ctrl[rng.choice(valid_flat.size, size=M, replace=False)] = True
        rows.append(measure("RANDOM_CONTROL", ctrl.reshape(usable.shape)))

    for fname, f in sorted(fields.items()):
        fv = np.where(usable, f, -np.inf).astype(np.float32)
        for r in (2, 3):
            peaks = nms_peaks(fv, r, usable)
            for M in MASSES:
                m = topk(peaks, fv, M)
                if int(m.sum()) < 100:
                    continue
                rec = measure(f"{fname}|nms{r}", m)
                rows.append(rec)
        log(f"  {fname:24s} " + "  ".join(
            f"M={r['mass']:.0f}:proxy_cm={r['proxy_off']['credit_per_mass']:.4f}"
            f"/cat_cm={r['catalogue']['credit_per_mass']:.4f}"
            for r in rows if r["field"].startswith(fname + "|nms3")))

    ctrl_rows = [r for r in rows if r["field"] == "RANDOM_CONTROL"]
    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("MEASURED (catalogue-free detectors, exact 300 m kernel, "
                           "src/gems62/metric.py; truth = USGS SGMC off-catalogue faults and "
                           "the competition catalogue). NOT an organiser score."),
        "truth_geometry_vs_catalogue": geo,
        "random_control": ctrl_rows,
        "rows": rows,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_lineament.json").write_text(json.dumps(res, indent=1))
    log("wrote " + str(EV / "h63_lineament.json"))

    # leaderboard
    best = {}
    for r in rows:
        if r["field"] == "RANDOM_CONTROL":
            continue
        key = (r["field"], round(r["mass"]))
        best[key] = r
    ranked = sorted((r for r in rows if r["field"] != "RANDOM_CONTROL"),
                    key=lambda d: -d["proxy_off"]["credit_per_mass"])
    log("\nTOP by proxy_off credit/mass:")
    for r in ranked[:15]:
        log(f"  {r['field']:32s} M={r['mass']:7.0f}  cm={r['proxy_off']['credit_per_mass']:.4f}"
            f"  dti={r['proxy_off']['dti']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
