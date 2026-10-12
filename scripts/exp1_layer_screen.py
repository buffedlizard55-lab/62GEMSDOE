#!/usr/bin/env python3
"""EXPERIMENT 1 — layer screen: lineament response of every available band.

Question the experiment answers, per band:

1. Does the band carry **lineament structure at all** (a structure-tensor line
   response, not a brightness), and over what fraction of the grid?
2. Does that structure line up with the **mapped catalogue** (``labels.tif``)?
   That is the leakage canary: a rank-AUC above 0.90 against catalogue pixels means
   the layer probably encodes the catalogue rather than an independent physical field.
3. Does it line up with the **off-catalogue compilation** (SGMC 1:750 k minus the
   competition catalogue) — i.e. with *unmapped-by-the-competition* faults?
4. Is it **already inside the incumbent lane**? Measured as the fraction of the
   band's top-k line pixels that fall within 3 px of a dot of the never-copied,
   never-submitted reference field (the 0.2778 champion and the group's
   highest-credit detector). High overlap = re-deriving a prior submission.

Outputs a JSON table plus uint8 rank-quantile images on disk so that the consensus
builder (experiment 2) can re-read them without recomputing.

Operator (deliberately NOT the incumbent's Hessian vesselness):
    a **structure-tensor edge-line response**  L = sqrt(l1) * (l1 - l2)/(l1 + l2)
    i.e. edge energy x anisotropy, both polarities by construction, with the
    per-band rank transform making the layers comparable ("each physics votes with
    its own top quantiles").  Scale-matched to the published 300 m kernel:
    derivative sigma 1.2 / 2.4 px (= 120 m / 240 m), tensor sigma 1.6x that.

Usage:  python3 scripts/exp1_layer_screen.py [--dest build/feat] [--names a,b,c]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid  # noqa: E402

EXT = HERE / "build" / "ext"
REG = HERE / "build" / "registry"

# ----------------------------------------------------------------------------- layer inventory
# every layer is (label, file, band-index, physical family) with the band names read
# from the file's OWN metadata, not from a document.
OFFICIAL = EXT / "gems-geodawn-numerical-features.tif"
LAYERS: list[tuple[str, pathlib.Path, int, str]] = []

OFFICIAL_FAMILY = {
    "mag_anom": "magnetic", "rtp": "magnetic", "tmi_hg": "magnetic", "tmi_vg": "magnetic",
    "tmi": "magnetic", "tc": "magnetic",
    "iso_grav_anom": "gravity", "iso_grav_anom_slope": "gravity",
    "iso_grav_anom_vg": "gravity", "iso_grav_anom_hg": "gravity",
    "geod_2ndinv": "geodetic", "geod_shearrate": "geodetic", "geod_dilaterate": "geodetic",
    "det_elev": "topographic", "det_elev_slope": "topographic",
    "depth_to_base_surf": "subsurface", "cond_surf": "subsurface",
    "deq_n100a15": "seismic", "ieq_n100a15": "seismic",
}


def official_layers() -> list[tuple[str, pathlib.Path, int, str]]:
    """Official 19-band stack, in the file's own band order and with its own names."""
    import rasterio
    out = []
    with rasterio.open(OFFICIAL) as src:
        for i in range(1, src.count + 1):
            name = src.tags(i).get("band_name") or f"band{i}"
            out.append((f"off:{name}", OFFICIAL, i, OFFICIAL_FAMILY.get(name, "official")))
    return out


def other_layers() -> list[tuple[str, pathlib.Path, int, str]]:
    spec = [
        ("topo_10m_derived_100m_u8.tif", "topo10", "topographic"),
        ("lidar_scarp_features_u8.tif", "lidar", "lidar-scarp"),
        ("geodawn_rad_u8.tif", "rad", "radiometric"),
        ("geodawn_extensions_u8.tif", "radext", "radiometric"),
        ("dem10_chi_100m_i16.tif", "chi10", "topographic-10m"),
    ]
    out = []
    import rasterio
    for fname, prefix, family in spec:
        p = EXT / fname
        if not p.exists():
            continue
        with rasterio.open(p) as src:
            for i in range(1, src.count + 1):
                nm = src.descriptions[i - 1] or f"band{i}"
                out.append((f"{prefix}:{nm}", p, i, family))
    out.append(("dem:z", EXT / "geodawn_dem_a2_100m.tif", 1, "topographic"))
    return out


# ----------------------------------------------------------------------------- the operator
def load_band(path: pathlib.Path, idx: int) -> tuple[np.ndarray, dict]:
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(idx).astype(np.float32)
        nodata = src.nodata
        tag = src.tags(idx)
    if nodata is not None:
        a[a == np.float32(nodata)] = np.nan
    a[~np.isfinite(a)] = np.nan
    # uint8 quantised layers: q=0 is nodata by their own tag; nothing sane equals 0 otherwise
    if tag.get("q_rule") or (np.nanmin(a[np.isfinite(a)]) == 0.0 and a.dtype == np.uint8):
        pass
    return a, tag


def line_response(a: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """Structure-tensor edge-line response and line orientation (radians).

    L = sqrt(l1) * (l1-l2)/(l1+l2)  -- edge energy x anisotropy, both polarities.
    Orientation returned is the **line** direction (gradient + 90 deg).
    """
    valid = np.isfinite(a)
    fill = np.where(valid, a, np.nanmean(a[valid]) if valid.any() else 0.0).astype(np.float32)
    # normalize amplitude locally so that a weak regional field and a strong one are comparable
    gx = ndi.gaussian_filter(fill, sigma, order=(0, 1), mode="nearest")
    gy = ndi.gaussian_filter(fill, sigma, order=(1, 0), mode="nearest")
    rho = 1.6 * sigma
    jxx = ndi.gaussian_filter(gx * gx, rho, mode="nearest")
    jxy = ndi.gaussian_filter(gx * gy, rho, mode="nearest")
    jyy = ndi.gaussian_filter(gy * gy, rho, mode="nearest")
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr * 0.25 - det, 0.0))
    l1 = tr * 0.5 + disc
    l2 = tr * 0.5 - disc
    l1 = np.maximum(l1, 0.0)
    l2 = np.maximum(l2, 0.0)
    resp = np.sqrt(l1) * (l1 - l2) / (l1 + l2 + 1e-20)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi * 0.5   # line direction
    resp[~valid] = np.nan
    theta[~valid] = np.nan
    return resp.astype(np.float32), theta.astype(np.float32)


def rank_quantile(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """uint8 rank of ``a`` among its finite values (1..255); 0 where invalid."""
    x = a[valid]
    order = np.argsort(x, kind="stable")
    ranks = np.empty(x.size, np.float64)
    ranks[order] = np.arange(1, x.size + 1)
    q = np.zeros(a.shape, np.uint8)
    q[valid] = np.clip(np.round(ranks / x.size * 254.0) + 1.0, 1, 255).astype(np.uint8)
    return q


def rank_auc(score: np.ndarray, pos: np.ndarray, mask: np.ndarray) -> float:
    x = score[mask]
    y = pos[mask]
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]
    npos, nneg = int(y.sum()), int((~y).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(x.size, np.float64)
    ranks[order] = np.arange(1, x.size + 1, dtype=np.float64)
    return float((ranks[y].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def read_mask(path: pathlib.Path, footprint: np.ndarray) -> np.ndarray | None:
    import rasterio
    with rasterio.open(path) as src:
        if src.shape != footprint.shape:
            return None
        arr = src.read(1)
    if not np.isfinite(arr).all():
        arr = np.where(np.isfinite(arr), arr, 0.0)
    return (arr > 0) & footprint


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="build/feat")
    ap.add_argument("--sigma", type=float, nargs="+", default=[1.2, 2.4])
    ap.add_argument("--topk", type=int, default=38000,
                    help="k for the overlap-vs-incumbent test (champion dot count)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--names", default=None)
    args = ap.parse_args()

    dest = HERE / args.dest
    dest.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    print(f"[e1] footprint {int(footprint.sum()):,}  catalogue {int((known & footprint).sum()):,}")

    # SGMC off-catalogue truth (independent compilation minus the competition catalogue)
    sgmc = read_mask(EXT / "derived_sgmc_faults_100m.tif", footprint)
    offcat_truth = None
    if sgmc is not None:
        offcat_truth = sgmc & ~ndi.binary_dilation(known, iterations=3)
        print(f"[e1] SGMC off-catalogue truth {int(offcat_truth.sum()):,} px")

    # incumbent reference fields (never copied, never submitted by us; used as detectors HERE)
    refs = {}
    for nm, f in (("champion_h33", REG / "champion_h33_2_b2_02778.tif"),
                  ("bayesopt_d28", REG / "bayesopt_dilation_scarp_d28.tif")):
        if f.exists():
            m = read_mask(f, footprint)
            refs[nm] = ndi.binary_dilation(m, iterations=3)
            print(f"[e1] reference {nm}: {int(np.asarray(m).sum() if m is not None else 0):,} dots")

    # annotated (not dilated) catalogue for the leakage canary with a buffer
    cat_buf = ndi.binary_dilation(known, iterations=3)
    far_from_cat = footprint & ~cat_buf

    # metric-shaped figures of merit need distance fields; compute each ONCE as float32
    from scipy.ndimage import distance_transform_edt as edt
    dist = {}
    dist["cat"] = edt(~(known & footprint)).astype(np.float32)
    if offcat_truth is not None:
        dist["sgmc"] = edt(~offcat_truth).astype(np.float32)
    for nm, m in (("champ", read_mask(REG / "champion_h33_2_b2_02778.tif", footprint)),
                  ("bayes", read_mask(REG / "bayesopt_dilation_scarp_d28.tif", footprint))):
        if m is not None:
            dist[nm] = edt(~m).astype(np.float32)
    print("[e1] distance fields:", {k: f"{v.mean():.1f}" for k, v in dist.items()})

    layers = official_layers() + other_layers()
    if args.names:
        want = set(args.names.split(","))
        layers = [l for l in layers if l[0] in want]
    if args.limit:
        layers = layers[: args.limit]
    print(f"[e1] {len(layers)} layers x {len(args.sigma)} scales -> {dest}")

    rows = []
    q_accum: dict[str, dict[str, np.ndarray]] = {}
    for label, path, idx, family in layers:
        try:
            a, tag = load_band(path, idx)
        except Exception as exc:                                     # pragma: no cover
            print(f"[e1] SKIP {label}: {exc}")
            continue
        valid = np.isfinite(a)
        cov = float(valid.mean())
        if valid.sum() < 1000:
            print(f"[e1] SKIP {label}: coverage {cov:.4f}")
            continue
        row = dict(layer=label, family=family, file=str(path.relative_to(HERE)), band=idx,
                   coverage=cov, q_rule=tag.get("q_rule"))
        for s in args.sigma:
            resp, theta = line_response(a, s)
            v = np.isfinite(resp)
            q = rank_quantile(resp, v)
            key = f"s{s:g}"
            np.save(dest / f"{label.replace(':', '_')}__{key}__q.npy", q)
            np.save(dest / f"{label.replace(':', '_')}__{key}__th.npy",
                    np.clip(np.round(np.nan_to_num(theta, nan=0.0) / np.pi * 128.0), -127, 127).astype(np.int8))
            # leakage canary: catalogue pixels vs the rest of the footprint
            row[f"{key}_auc_catalogue"] = rank_auc(q.astype(np.float32), known & footprint,
                                                  footprint)
            row[f"{key}_auc_catalogue_far"] = rank_auc(q.astype(np.float32), known & footprint,
                                                       far_from_cat | (known & footprint))
            if offcat_truth is not None and offcat_truth.sum() > 500:
                row[f"{key}_auc_sgmc_offcat"] = rank_auc(q.astype(np.float32), offcat_truth,
                                                         footprint & ~cat_buf)
            # top-k pixels of this layer, by exact rank, then metric-shaped figures of merit:
            #   credit_X  = mean 300 m triangular kernel credit of those pixels against truth X
            #   frac3px_X = fraction within 3 px of prior field X (lane-drift / redundancy)
            cand = np.nonzero((q > 0) & footprint)
            kk = min(args.topk, cand[0].size)
            if kk > 0:
                rq = q[cand]
                sel = np.argpartition(-rq, kk - 1)[:kk]
                yy, xx = cand[0][sel], cand[1][sel]
                row[f"{key}_topk_n"] = int(kk)
                for nm, d in dist.items():
                    dd = d[yy, xx]
                    kerr = np.maximum(1.0 - dd / 3.0, 0.0)
                    if nm in ("cat", "sgmc"):
                        row[f"{key}_credit_{nm}"] = float(kerr.mean())
                        row[f"{key}_hit3px_{nm}"] = float((dd <= 3.0).mean())
                    else:
                        row[f"{key}_frac3px_{nm}"] = float((dd <= 3.0).mean())
        rows.append(row)
        pfx = f"s{args.sigma[0]:g}"
        print(f"[e1] {label:34s} cov={cov:.3f}  "
              f"credit_cat={row.get(f'{pfx}_credit_cat', float('nan')):.4f}  "
              f"credit_sgmc={row.get(f'{pfx}_credit_sgmc', float('nan')):.4f}  "
              f"AUCcat={row.get(f'{pfx}_auc_catalogue', float('nan')):.3f}  "
              f"ovl_champ={row.get(f'{pfx}_frac3px_champ', float('nan')):.3f}  "
              f"ovl_bayes={row.get(f'{pfx}_frac3px_bayes', float('nan')):.3f}  "
              f"({time.time() - t0:.0f}s)", flush=True)

    out = dict(
        experiment="E1 layer screen",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        operator="structure-tensor edge-line response L = sqrt(l1)*(l1-l2)/(l1+l2), "
                 "rank-quantised per layer; line orientation = gradient + 90 deg",
        sigma_px=args.sigma,
        scales_note="derivative sigma 1.2 / 2.4 px = 120 / 240 m on the 100 m grid",
        figures_of_merit=dict(
            auc_catalogue="rank-AUC of the layer's line response against labels.tif "
                          "(canary: >0.90 = the layer probably encodes the catalogue)",
            auc_catalogue_far="same, with a 3 px buffer around the catalogue excluded, so "
                              "neighbour-credit cannot create the AUC",
            auc_sgmc_offcat="rank-AUC against SGMC 1:750k traces minus the catalogue: "
                            "an independent, public, OFF-catalogue fault compilation",
            frac3px_prior="fraction of the layer's top-k line pixels within 3 px of the "
                          "named prior field: high = this layer re-derives that field's lane"),
        footprint_cells=int(footprint.sum()),
        catalogue_cells=int((known & footprint).sum()),
        sgmc_offcat_cells=(int(offcat_truth.sum()) if offcat_truth is not None else None),
        rows=rows,
    )
    (HERE / "evidence").mkdir(exist_ok=True)
    p = HERE / "evidence" / "e1_layer_screen_20261011b.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(f"[e1] wrote {p}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
