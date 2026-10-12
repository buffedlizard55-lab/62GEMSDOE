#!/usr/bin/env python3
"""H62-J -- the datum lane measured as a SURFACE, with the axis conventions fixed and the mass
chosen by the metric's own economics.

LANE (verbatim from the brief, unchanged)
    "Map shoreline benches in the DEM and fit a smooth isobase, allowing for post-pluvial
     isostatic rebound.  Flag abrupt steps or lateral deflections along strike, seed a trace at
     each, extend it while DEM-ridge evidence supports it, and emit dotted lines."

WHAT IS NEW, AND WHY -- each item is measured in ``evidence/h62j/``, not asserted:

  1. Corrected axis convention (IR-62-J-01, IR-62-J-02).  v8 measured the datum offset along a
     direction reflected about the NE-SW diagonal, and its walker used a strike mirrored about the
     E-W axis: N-S and E-W structures measured ~0 offset (structurally blind) and traces ran up to
     90 deg off.  Both now route through ``gems62.geom``, with regressions in tests/test_geom_axes.py.
  2. Paired-bench ("doublet") gate: a step counts only if BOTH flanks sit on the isobase within
     ``--flank-tol-m`` and the two flank surfaces agree in shape (``corr``).  "There is a scarp
     here" is not "the 15 ka datum is displaced here".
  3. Isobase-excess step: the jump is compared against what the smooth isobase itself changes over
     the same 500 m baseline, so a steep regional warp cannot manufacture a "step".
  4. The detector is a continuous surface pooled onto the 100 m submission grid; a "trace" is the
     ridge-connected component grown from a strong seed, instead of <=300 loci with a 2 km
     suppression radius and a 5-heading walker.  Mass therefore comes from evidence, not a cap.
  5. Emission obeys the two rules measured across 87 score-anchored registry rasters: single-pixel
     ISOLATED dots (300 m hard-core, so mean self-kernel = 0 by construction) and mass set by the
     marginal rule (a dot pays iff its credit exceeds alpha*DTI), with catalogue pixels plus a
     collar excluded (they are masked out of the organiser's truth).

Usage
  python3 scripts/run_h62j.py --dem evidence/dem/lahontan_dem_utm11.tif \
      --catalogue data/labels.tif --sample data/sample_submission.tif \
      --ext data/external --out docs/downloads/gems62-h62j-<slug>.tif --evdir evidence/h62j
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import datum, grid as G, metric as MT, score_model as SM  # noqa: E402

BENCH_KW = dict(flat_slope=0.035, riser_slope=0.10)          # same windows v8 used


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def read_z(src, window) -> np.ndarray:
    """Decode the transport GeoTIFF (int16 decimetres, -32768 family) to metres, NaN = nodata."""
    z = src.read(1, window=window).astype(np.float32)
    z[z <= -32000.0] = np.nan
    return z * 0.1


def _linear_interp(values: np.ndarray, frac: np.ndarray) -> np.ndarray:
    """Linear interpolation of the rows of a 2-D surface at fractional row positions `frac`."""
    n = values.shape[0] - 1
    f = np.clip(frac, 0.0, n)
    i0 = np.floor(f).astype(np.int64)
    i1 = np.minimum(i0 + 1, values.shape[0] - 1)
    w = (f - i0).astype(np.float32)
    return (values[i0] * (1.0 - w)[:, None] + values[i1] * w[:, None]).astype(np.float32)


def tile_to_grid(surf_tile: np.ndarray, rows0: int, nrows: int, ncols: int, t: int) -> np.ndarray:
    """Upsample a tile surface to a ``(nrows, ncols)`` DEM-pixel block, bilinear, separably."""
    s = surf_tile.copy()
    if np.isnan(s).any():
        good = ~np.isnan(s)
        idx = ndimage.distance_transform_edt(~good, return_distances=False, return_indices=True)
        s = s[tuple(idx)]
    s = ndimage.gaussian_filter(s.astype(np.float32), 1.5)
    # fractional tile coordinates of every pixel centre in this block
    fr = (np.arange(rows0, rows0 + nrows) + 0.5) / t - 0.5
    fc = np.clip((np.arange(ncols) + 0.5) / t - 0.5, 0.0, s.shape[1] - 1.001)
    tmp = _linear_interp(s, fr)                                # (nrows, tc) along rows
    j0 = np.floor(fc).astype(np.int64)
    j1 = np.minimum(j0 + 1, s.shape[1] - 1)
    wj = (fc - j0).astype(np.float32)
    return (tmp[:, j0] * (1.0 - wj)[None, :] + tmp[:, j1] * wj[None, :]).astype(np.float32)


def scatter_max(a25: np.ndarray, rr: np.ndarray, cc: np.ndarray, shape: tuple[int, int]
                ) -> np.ndarray:
    """Max of a 25 m block inside each 100 m cell that contains any of its pixels."""
    hh, ww = shape
    ok_r = (rr >= 0) & (rr < hh)
    ok_c = (cc >= 0) & (cc < ww)
    keep = ok_r[:, None] & ok_c[None, :]
    idx = (rr[:, None] * ww + cc[None, :])[keep]
    out = np.zeros(shape, np.float32)
    np.maximum.at(out.ravel(), idx, a25[keep])
    return out


# ---------------------------------------------------------------------------------------------
# pass 1: benches -> tile-wise robust modal bench elevation = the smooth isobase
# ---------------------------------------------------------------------------------------------
def pass1_isobase(dem_path, *, band_lo, band_hi, tile_m, z_lo, z_hi, fine, block_rows):
    src = rasterio.open(dem_path)
    H, W = src.height, src.width
    res = float(src.res[0])
    t = int(round(tile_m / res))
    tr, tc = int(np.ceil(H / t)), int(np.ceil(W / t))
    nbins = int(round((z_hi - z_lo) / fine))
    hist = np.zeros((tr, tc, nbins), np.int32)
    counts = np.zeros((tr, tc), np.int32)
    valid = np.zeros((tr, tc), np.int32)
    t0 = time.time()
    for r0 in range(0, H, block_rows):
        r1 = min(H, r0 + block_rows)
        z = read_z(src, ((r0, r1), (0, W)))
        b = datum.bench_response(np.nan_to_num(z, nan=0.0), res, **BENCH_KW)
        m = (b["score"] >= 0.25) & np.isfinite(z) & (z >= band_lo) & (z <= band_hi)
        for i in range(r0 // t, (r1 - 1) // t + 1):
            lo, hi = max(r0, i * t) - r0, min(r1, (i + 1) * t) - r0
            if hi <= lo:
                continue
            for j in range(tc):
                c0, c1 = j * t, min(W, (j + 1) * t)
                zz = z[lo:hi, c0:c1]
                mm = m[lo:hi, c0:c1]
                counts[i, j] += int(mm.sum())
                valid[i, j] += int(np.isfinite(zz).sum())
                if int(mm.sum()) < 5:
                    continue
                k = np.clip(((zz[mm] - z_lo) / fine).astype(np.int32), 0, nbins - 1)
                hist[i, j] += np.bincount(k, minlength=nbins)[:nbins].astype(np.int32)
        del z, b, m
    src.close()
    group = max(1, int(round(2.0 / fine)))
    ng = nbins // group
    agg = hist[:, :, :ng * group].reshape(tr, tc, ng, group).sum(axis=3)
    best = np.argmax(agg, axis=2)
    okc = (np.max(agg, axis=2) >= 10) & (counts >= 25)
    surf = np.full((tr, tc), np.nan, np.float32)
    ii, jj = np.nonzero(okc)
    for i, j in zip(ii, jj):
        g = int(best[i, j])
        h = hist[i, j, g * group:(g + 1) * group].astype(np.int64)
        cum = np.cumsum(h)
        kk = int(np.searchsorted(cum, (int(cum[-1]) + 1) // 2))
        surf[i, j] = z_lo + (g * group + kk + 0.5) * fine
    meta = dict(res=res, tile_m=tile_m, t=t, tr=tr, tc=tc, tiles=int(tr * tc),
                tiles_ok=int(okc.sum()), bench_px=int(counts.sum()), valid_px=int(valid.sum()),
                z_lo=z_lo, z_hi=z_hi, fine=fine, band=[band_lo, band_hi],
                seconds=round(time.time() - t0, 1),
                surf_min=None if not np.isfinite(surf).any() else float(np.nanmin(surf)),
                surf_max=None if not np.isfinite(surf).any() else float(np.nanmax(surf)))
    return surf, meta


# ---------------------------------------------------------------------------------------------
# pass 2: the doublet surfaces on the DEM grid, pooled to the submission grid
# ---------------------------------------------------------------------------------------------
def pass2_fields(dem_path, surf_tile, iso_meta, *, block_rows, gates, out_shape, x0, y0):
    with rasterio.open(dem_path) as d:
        H, W = d.shape
        res = float(d.res[0])
        t = iso_meta["t"]
        keys = ("score", "evid", "step", "corr", "doublet_frac", "bench", "valid")
        acc = {k: np.zeros(out_shape, np.float32) for k in keys}
        cc = np.floor(((np.arange(W) + 0.5) * res + x0 - G.TRANSFORM[2]) / G.PIXEL_M).astype(np.int64)
        rr = np.floor((G.TRANSFORM[5] - ((np.arange(H) + 0.5) * res + y0)) / G.PIXEL_M).astype(np.int64)
        nb = 0
        t0 = time.time()
        for r0 in range(0, H, block_rows):
            r1 = min(H, r0 + block_rows)
            z = read_z(d, ((r0, r1), (0, W)))
            pad = 60
            zp = np.pad(z, ((pad, pad), (0, 0)), mode="edge")
            b = datum.bench_response(np.nan_to_num(zp, nan=0.0), res, **BENCH_KW)
            iso = tile_to_grid(surf_tile, r0 - pad, zp.shape[0], W, t)
            sl = slice(pad, pad + z.shape[0])
            bench_score = b["score"][sl]
            su = datum.doublet_surfaces(z, iso[sl], bench_score, res, **gates)
            core = np.isfinite(z)
            fields = dict(evid=su["evid"], step=su["step"], corr=su["corr"], score=su["score"],
                          doublet_frac=su["doublet_ok"].astype(np.float32),
                          bench=bench_score, valid=core.astype(np.float32))
            for k, a in fields.items():
                a = np.where(core, np.nan_to_num(np.asarray(a, np.float32), nan=0.0,
                                                  posinf=0.0, neginf=0.0), 0.0)
                # max-pool: a 100 m cell carries the best 25 m evidence inside it
                acc[k] = np.maximum(acc[k], scatter_max(a, rr[r0:r1], cc, out_shape))
            nb += 1
            del z, zp, b, iso, su, core, fields
        log(f"pass 2 done in {time.time() - t0:.0f} s, {nb} blocks")
    return acc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True)
    ap.add_argument("--catalogue", default="data/labels.tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--ext", default="data/external")
    ap.add_argument("--out", required=True)
    ap.add_argument("--evdir", default="evidence/h62j")
    ap.add_argument("--band-lo", type=float, default=1157.0)
    ap.add_argument("--band-hi", type=float, default=1455.0)
    ap.add_argument("--block-rows", type=int, default=700)
    ap.add_argument("--flank-tol-m", type=float, default=6.0)
    ap.add_argument("--min-step-m", type=float, default=2.0)
    ap.add_argument("--min-corr", type=float, default=0.35)
    ap.add_argument("--min-cross-deg", type=float, default=30.0)
    ap.add_argument("--max-shore-m", type=float, default=1500.0)
    ap.add_argument("--min-evid", type=float, default=0.10)
    ap.add_argument("--seed-evid", type=float, default=0.35)
    ap.add_argument("--min-trace-cells", type=int, default=4)
    ap.add_argument("--sep-m", type=float, default=300.0)
    ap.add_argument("--cat-collar-m", type=float, default=250.0)
    ap.add_argument("--masses", default="2000,5000,10000,15000,20000,30000,40000,50000")
    ap.add_argument("--n-truth", type=float, default=12000.0,
                    help="MODEL planning input: hidden truth mass in 100 m cells")
    ap.add_argument("--target-dti", type=float, default=0.2778,
                    help="the incumbent score the marginal bar is evaluated against (OWNER-REPORTED)")
    args = ap.parse_args()

    ev = pathlib.Path(args.evdir)
    ev.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    known, _ = G.load_catalogue(args.catalogue)
    with rasterio.open(args.sample) as s:
        footprint = np.isfinite(s.read(1))
    H, W = footprint.shape
    with rasterio.open(args.dem) as d:
        dem_meta = dict(crs=str(d.crs), transform=[float(v) for v in d.transform][:6],
                        shape=list(d.shape), res=float(d.res[0]), nodata=d.nodata,
                        bytes=d.shape[0] * d.shape[1] * 2)
    assert dem_meta["crs"] == G.CRS, dem_meta
    res = dem_meta["res"]
    x0, y0 = dem_meta["transform"][2], dem_meta["transform"][5]

    log("pass 1: benches + tile isobase")
    surf_tile, iso_meta = pass1_isobase(pathlib.Path(args.dem), band_lo=args.band_lo,
                                        band_hi=args.band_hi, tile_m=4000.0, z_lo=1150.0,
                                        z_hi=1460.0, fine=0.1, block_rows=args.block_rows)
    log(f"isobase tiles ok {iso_meta['tiles_ok']}/{iso_meta['tiles']}  "
        f"bench px {iso_meta['bench_px']:,}  surf {iso_meta['surf_min']}..{iso_meta['surf_max']} m")
    json.dump(iso_meta, open(ev / "isobase.json", "w"), indent=1)

    log("pass 2: datum-doublet surfaces")
    gates = dict(smooth_m=120.0, scarp_sigma_m=100.0, offset_half_m=250.0,
                 min_step_m=args.min_step_m, flank_tol_m=args.flank_tol_m, corr_sigma_m=300.0,
                 min_corr=args.min_corr, max_shore_distance_m=1e12,
                 min_cross_angle_deg=args.min_cross_deg, excess_step=True, legacy_axis_swap=False)
    F = pass2_fields(pathlib.Path(args.dem), surf_tile, iso_meta, block_rows=args.block_rows,
                     gates=gates, out_shape=(H, W), x0=x0, y0=y0)

    # ---------------- global stage: shore gate, ridge growth, collar, isolation -----------------
    bench_ok = F["bench"] >= 0.25
    d_shore = (ndimage.distance_transform_edt(~bench_ok, sampling=(G.PIXEL_M, G.PIXEL_M))
               if bench_ok.any() else np.full((H, W), np.inf, np.float32))
    shore_ok = d_shore <= args.max_shore_m
    collar = ndimage.binary_dilation(known, iterations=max(1, int(round(args.cat_collar_m / G.PIXEL_M))))
    ladder = dict(footprint_cells=int(footprint.sum()), dem_valid=int((F["valid"] > 0).sum()),
                  bench_cells=int(bench_ok.sum()),
                  evid_ge_min=int((F["evid"] >= args.min_evid).sum()),
                  score_positive=int((F["score"] > 0).sum()),
                  score_and_shore=int(((F["score"] > 0) & shore_ok & footprint).sum()),
                  score_and_shore_offcat=int(((F["score"] > 0) & shore_ok & footprint & ~collar).sum()))
    ridge = (F["evid"] >= args.min_evid) & (F["score"] > 0) & shore_ok & footprint
    seed = ridge & (F["evid"] >= args.seed_evid) & ~collar
    lab, n_lab = ndimage.label(ridge, structure=np.ones((3, 3), int))
    if n_lab:
        have = np.zeros(n_lab + 1, bool)
        have[np.unique(lab[seed])] = True
        have[0] = False
        traced = have[lab] & ridge
        sizes = np.bincount(lab.ravel())
        traced &= sizes[lab] >= args.min_trace_cells
    else:
        traced = np.zeros_like(ridge)
    cand = traced & ~collar & footprint
    log(f"components {n_lab:,}  seeds {int(seed.sum()):,}  traced {int(traced.sum()):,}  "
        f"candidate cells {int(cand.sum()):,}")
    log("gate ladder " + json.dumps(ladder))

    ys, xs = np.nonzero(cand)
    vals = F["score"][ys, xs]
    order = np.argsort(-vals, kind="mergesort")
    ys, xs, vals = ys[order], xs[order], vals[order]
    cap = 400_000                       # the greedy walk below is O(candidates) in python
    if ys.size > cap:
        log(f"ranking the top {cap:,} of {ys.size:,} candidates by score (the rest cannot be "
            f"reached inside the hard-core budget anyway)")
        ys, xs, vals = ys[:cap], xs[:cap], vals[:cap]
    sep_px = args.sep_m / G.PIXEL_M
    pts = np.column_stack([ys, xs]).astype(np.float32)
    tree = cKDTree(pts)
    banned = np.zeros(ys.size, bool)
    keep: list[int] = []
    for i in range(ys.size):
        if banned[i]:
            continue
        keep.append(i)
        banned[tree.query_ball_point(pts[i], sep_px)] = True
        if len(keep) >= 250_000:
            break
    keep = np.asarray(keep, np.int64)
    ky, kx = ys[keep], xs[keep]
    log(f"isolated dots available {keep.size:,} (from {ys.size:,} candidates)")

    # ---------------- instruments ---------------------------------------------------------------
    sgmc = pathlib.Path(args.ext) / "derived_sgmc_faults_100m.tif"
    dB = None
    if sgmc.exists():
        with rasterio.open(sgmc) as d:
            a = d.read(1)
        sg = np.where(np.isfinite(a), a, 0) > 0
        truthB = sg & footprint & ~known
        if truthB.any():
            dB = ndimage.distance_transform_edt(~truthB, sampling=(G.PIXEL_M, G.PIXEL_M))
            log(f"instrument B truth cells {int(truthB.sum()):,}")
    if dB is None:
        log("WARNING instrument B unavailable; credit columns will be null")

    def credit_of(sel: np.ndarray) -> float | None:
        if dB is None or sel.size == 0:
            return 0.0 if dB is not None else None
        return float(MT.kernel(dB[ky[sel], kx[sel]], MT.RADIUS_M).mean())

    def control_credit(M: int, seed_: int) -> float | None:
        """Mass-matched ISOLATED-random field over the same allowed domain (footprint - collar)."""
        if dB is None:
            return None
        rng = np.random.default_rng(7000 + seed_)
        dom = np.nonzero(footprint & ~collar & (F["valid"] > 0))
        o = rng.permutation(dom[0].size)
        py, px = dom[0][o].astype(np.float32), dom[1][o].astype(np.float32)
        t2 = cKDTree(np.column_stack([py, px]))
        ban = np.zeros(py.size, bool)
        kp: list[int] = []
        for i in range(py.size):
            if ban[i]:
                continue
            kp.append(i)
            ban[t2.query_ball_point((py[i], px[i]), sep_px)] = True
            if len(kp) >= M:
                break
        kp = np.asarray(kp)
        # credit of the control set, same estimator as the emission
        yy, xx = py[kp].astype(np.int64), px[kp].astype(np.int64)
        return float(MT.kernel(dB[yy, xx], MT.RADIUS_M).mean())

    curve = []
    masses = sorted(set([int(v) for v in args.masses.split(",") if v.strip()] + [int(keep.size)]))
    for M in masses:
        if M <= 0 or M > keep.size:
            continue
        sel = np.arange(M)
        c = credit_of(sel)
        tail = np.arange(max(0, M - min(1000, max(1, M // 2))), M)
        cm = credit_of(tail)
        row = dict(M=int(M), credit_B=None if c is None else round(c, 6),
                   credit_tail=None if cm is None else round(cm, 6),
                   model_dti=None if c is None else round(SM.model_dti(M, c, args.n_truth), 6),
                   ceiling=round(SM.perfect_placement_ceiling(M, int(args.n_truth)), 6))
        curve.append(row)
        log(f"  M={M:6d} credit_B={row['credit_B']} tail={row['credit_tail']} "
            f"model_dti={row['model_dti']} ceiling={row['ceiling']}")
    for row in [r for r in curve if r["M"] >= max(2000, int(0.25 * keep.size))][:4]:
        cc_ = [control_credit(row["M"], k) for k in range(3)]
        if any(v is None for v in cc_):
            row["control_B"] = None
        else:
            row["control_B"] = round(float(np.mean(cc_)), 6)
            row["control_sd"] = round(float(np.std(cc_)), 6)
            row["ratio_vs_control"] = round(row["credit_B"] / row["control_B"], 4) if row["control_B"] else None
        log(f"  control at M={row['M']}: {row.get('control_B')} ratio {row.get('ratio_vs_control')}")

    scored = [r for r in curve if r["model_dti"] is not None]
    best = max(scored, key=lambda r: r["model_dti"]) if scored else None
    if best is None:
        M_star = int(min(keep.size, 5000))
        best = dict(M=M_star, credit_B=None, control_B=None, model_dti=None,
                    ceiling=round(SM.perfect_placement_ceiling(M_star, int(args.n_truth)), 6))
    else:
        M_star = int(best["M"])
    emis = np.zeros((H, W), bool)
    emis[ky[:M_star], kx[:M_star]] = True

    # self-kernel of the emission, measured (must be 0 by construction, so verify it)
    kk = np.column_stack([ky[:M_star], kx[:M_star]]).astype(np.float32)
    if M_star > 1:
        nb = cKDTree(kk).query(kk, k=2)[0][:, 1] * G.PIXEL_M
        self_kern = float(MT.kernel(nb, MT.RADIUS_M).mean())
        nn_min = float(nb.min())
    else:
        self_kern, nn_min = 0.0, float("nan")
    dist_cat = ndimage.distance_transform_edt(~known, sampling=(G.PIXEL_M, G.PIXEL_M))
    yE, xE = np.nonzero(emis)
    blocks = np.histogram2d(yE / (H / 3.0), xE / (W / 2.0), bins=[3, 2], range=[[0, 3], [0, 2]])[0]
    stats = dict(n_dots=int(emis.sum()), n_candidates=int(ys.size), n_isolated_available=int(keep.size),
                 mass=M_star, credit_B=best.get("credit_B"), control_B=best.get("control_B"),
                 ratio_vs_control=best.get("ratio_vs_control"), model_dti=best.get("model_dti"),
                 ceiling=best.get("ceiling"), mean_self_kernel=round(self_kern, 6),
                 min_neighbour_distance_m=round(nn_min, 1),
                 min_dist_to_catalogue_m=round(float(dist_cat[yE, xE].min()), 1) if yE.size else None,
                 frac_within_400m_of_catalogue=round(float((dist_cat[yE, xE] <= 400.0).mean()), 6),
                 frac_on_catalogue=round(float(known[yE, xE].mean()), 6) if yE.size else None,
                 block_spread=[int(v) for v in blocks.ravel()],
                 n_components=int(ndimage.label(emis, structure=np.ones((3, 3), int))[1]),
                 gate_ladder=ladder, iso_meta=iso_meta)
    json.dump(dict(sweep=curve, chosen=dict(M=M_star, rule="max model DTI at N (MODEL, not a score)"),
                   stats=stats,
                   marginal_bar=dict(credit_at_target=round(0.2 * args.target_dti, 6),
                                     distance_m=round(MT.maximum_useful_distance_m(args.target_dti), 1),
                                     note="a dot is profitable iff its credit exceeds alpha*DTI"),
                   instrument_B="derived_sgmc_faults_100m.tif minus the catalogue; 300 m triangular "
                                "kernel credit per dot (a proxy: a 1:750k compilation)",
                   ), open(ev / "sweep.json", "w"), indent=1)

    # ---------------- write, then re-read and validate the bytes -------------------------------
    rec = G.write_submission(out, emis.astype(np.float32))
    json.dump(rec, open(ev / "receipt.json", "w"), indent=1)
    log(f"wrote {out}  {rec['bytes']:,} B  legal={rec.get('legal')}  dots={rec['n_positive']}  "
        f"sha256={rec['sha256'][:16]}")
    np.savez_compressed(ev / "fields_100m.npz", evid=F["evid"], step=F["step"], corr=F["corr"],
                        score=F["score"], doublet_frac=F["doublet_frac"], bench=F["bench"],
                        traced=traced.astype(np.float32), cand=cand.astype(np.float32),
                        emis=emis.astype(np.float32))
    json.dump(dict(dem=dem_meta, iso=iso_meta, args=vars(args), stats=stats,
                   receipt={k: rec[k] for k in ("file", "bytes", "sha256", "n_positive", "min",
                                                 "max", "nodata", "legal", "all_finite",
                                                 "n_outside_0_1", "transform_match", "crs_match")}),
              open(ev / "run_summary.json", "w"), indent=1)
    print(json.dumps(dict(stats=stats, chosen=dict(M=M_star, model_dti=best.get("model_dti"),
                                                    ceiling=best.get("ceiling"))), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
