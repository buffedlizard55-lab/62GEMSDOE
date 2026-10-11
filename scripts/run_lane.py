#!/usr/bin/env python3
"""Datum-offset lane, end to end: official 3DEP DEM -> shoreline benches -> isobase ->
flagged steps/deflections -> seeded, DEM-extended traces -> dotted submission GeoTIFF.

Design constraints that shaped this script
------------------------------------------
* the official rasters are the only fault-side input; the DEM is the only morphology input;
* the driving machine has ~3 GB RAM, so both DEM passes are *windowed* (30 km blocks with
  3 km overlap) and only reduced products are held in memory;
* the isobase is global (it must not be refit per block, or a block-edge step would be
  manufactured by the fit itself), so it is built from pass 1 and evaluated by a sampler in
  pass 2;
* everything that ends up in the submission is written with the same code path as the
  format receipt (`gems62.grid.write_submission`), so the bytes on disk and the receipt can
  never disagree.

Usage:
  python scripts/run_lane.py --dem /tmp/gems/dem/dem_25m_utm11.tif \
      --catalogue /home/user/work/bridge/existing_faults.tif \
      --sample /home/user/work/bridge/example_submission.tif \
      --out-dir build/lane --name gemsdoe62-datum-lahontan-isobase
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import datum, grid, metric  # noqa: E402



def read_z(src, window, res=None):
    """Decode a DEM window to metres with NaN for nodata.

    The transport GeoTIFF stores int16 decimetres (z_m = value/10) with the -32767/-32768
    sentinel family; both the scale and the sentinel are handled here so no threshold in this
    script ever sees decimetres by accident (a 10x unit error would silently disable every
    elevation window in the pipeline).
    """
    import numpy as np
    z = src.read(1, window=window).astype(np.float32)
    z[z <= -32000.0] = np.nan
    return z * 0.1

def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def block_windows(h: int, w: int, block_px: int, overlap_px: int):
    step = block_px - 2 * overlap_px
    if step <= 0:
        raise ValueError("overlap too large for block size")
    for r0 in range(0, h, step):
        for c0 in range(0, w, step):
            r1 = min(h, r0 + block_px)
            c1 = min(w, c0 + block_px)
            if r1 - r0 < 32 or c1 - c0 < 32:
                continue
            yield r0, c0, r1, c1


class IsobaseSampler:
    """Bilinear evaluation of the coarse isobase tile surface, in UTM coordinates."""

    def __init__(self, surf: np.ndarray, transform_origin, tile_m: float, res: float):
        self.surf = surf
        self.x0 = transform_origin[0]
        self.y1 = transform_origin[1]
        self.tile_m = tile_m
        self.res = res
        self.tr, self.tc = surf.shape

    def at_rows_cols(self, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
        x = self.x0 + (cols + 0.5) * self.res
        y = self.y1 - (rows + 0.5) * self.res
        fi = np.clip((y - (self.y1 - self.tr * self.tile_m)) / self.tile_m - 0.5, 0, self.tr - 1.001)
        fj = np.clip((x - self.x0) / self.tile_m - 0.5, 0, self.tc - 1.001)
        i0 = np.floor(fi).astype(int); j0 = np.floor(fj).astype(int)
        i1 = np.clip(i0 + 1, 0, self.tr - 1); j1 = np.clip(j0 + 1, 0, self.tc - 1)
        a = fi - i0; b = fj - j0
        return (self.surf[i0, j0] * (1 - a) * (1 - b) + self.surf[i1, j0] * a * (1 - b)
                + self.surf[i0, j1] * (1 - a) * b + self.surf[i1, j1] * a * b)

    def at_rc(self, r: float, c: float) -> float:
        return float(self.at_rows_cols(np.array([r]), np.array([c]))[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True)
    ap.add_argument("--catalogue", required=True, help="labels.tif / existing_faults.tif")
    ap.add_argument("--sample", required=True, help="sample_submission.tif (defines the footprint)")
    ap.add_argument("--out-dir", default="build/lane")
    ap.add_argument("--name", default="gemsdoe62-datum-lahontan-isobase")
    # bench / isobase knobs
    ap.add_argument("--flat-slope", type=float, default=0.035)
    ap.add_argument("--riser-slope", type=float, default=0.10)
    ap.add_argument("--bench-min-score", type=float, default=0.25)
    ap.add_argument("--isobase-tile-m", type=float, default=8000.0)
    ap.add_argument("--isobase-smooth-tiles", type=float, default=3.0)
    ap.add_argument("--stand-bin-m", type=float, default=2.0)
    ap.add_argument("--stand-tol-m", type=float, default=6.0)
    ap.add_argument("--min-tile-support", type=int, default=40)
    ap.add_argument("--stand-band-tol-m", type=float, default=18.0)
    ap.add_argument("--shore-tol-m", type=float, default=12.0)
    ap.add_argument("--z-lo", type=float, default=1150.0)
    ap.add_argument("--z-hi", type=float, default=1450.0)
    # segment / locus knobs
    ap.add_argument("--min-segment-px", type=int, default=100)
    ap.add_argument("--min-length-m", type=float, default=2000.0)
    ap.add_argument("--min-elongation", type=float, default=4.0)
    ap.add_argument("--step-window-m", type=float, default=500.0)
    ap.add_argument("--min-step-m", type=float, default=2.0)
    ap.add_argument("--min-deflection-deg", type=float, default=12.0)
    # trace knobs
    ap.add_argument("--max-loci", type=int, default=400)
    ap.add_argument("--locus-separation-m", type=float, default=2000.0)
    ap.add_argument("--trace-window-m", type=float, default=20000.0)
    ap.add_argument("--max-trace-len-m", type=float, default=15000.0)
    ap.add_argument("--min-trace-evidence", type=float, default=0.22)
    ap.add_argument("--scarp-sigma-m", type=float, default=75.0)
    ap.add_argument("--min-locus-evidence", type=float, default=0.06)
    ap.add_argument("--max-chain-jump-m", type=float, default=150.0)
    ap.add_argument("--min-datum-evidence", type=float, default=0.10)
    ap.add_argument("--max-shore-distance-m", type=float, default=1500.0)
    ap.add_argument("--max-loci-per-block", type=int, default=40)
    # emission knobs
    ap.add_argument("--dot-spacing-px", type=float, default=2.8)
    ap.add_argument("--min-catalogue-px", type=float, default=1.0)
    ap.add_argument("--max-dots", type=int, default=12000)
    ap.add_argument("--block-km", type=float, default=30.0)
    ap.add_argument("--overlap-km", type=float, default=3.0)
    args = ap.parse_args()

    import rasterio
    from rasterio.windows import Window

    out_dir = pathlib.Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ---------------- official rasters: catalogue + footprint on the 100 m grid --------------
    known, footprint = grid.load_catalogue(args.catalogue)
    with rasterio.open(args.sample) as s:
        sample = s.read(1)
    footprint = np.isfinite(sample)
    log(f"catalogue positives={int(known.sum())} footprint cells={int(footprint.sum())}")

    # ---------------- DEM ---------------------------------------------------------------------
    src = rasterio.open(args.dem)
    res = abs(src.res[0])
    H, W = src.height, src.width
    log(f"DEM {args.dem} {H}x{W} res={res} crs={src.crs} nodata={src.nodata}")

    block_px = int(round(args.block_km * 1000 / res))
    overlap_px = int(round(args.overlap_km * 1000 / res))

    # ---------------- pass 1: bench pixels -> isobase ----------------------------------------
    bench_pts = []          # (row, col, z) in DEM grid coordinates
    n_blocks = 0
    for (r0, c0, r1, c1) in block_windows(H, W, block_px, overlap_px):
        n_blocks += 1
        z = read_z(src, Window(c0, r0, c1 - c0, r1 - r0))
        if not np.isfinite(z).any():
            continue
        if np.nanmin(z) > args.z_hi or np.nanmax(z) < args.z_lo:
            continue
        b = datum.bench_response(z, res, flat_slope=args.flat_slope, riser_slope=args.riser_slope)
        m = (b["score"] >= args.bench_min_score) & (z >= args.z_lo) & (z <= args.z_hi)
        rr, cc = np.nonzero(m)
        if rr.size:
            rr = rr[::2]; cc = cc[::2]          # light subsample: the isobase is a coarse surface
            bench_pts.append(np.stack([rr + r0, cc + c0, z[rr, cc]], axis=1))
        del b, m, z
    if not bench_pts:
        log("FATAL: no bench pixels found; adjust thresholds")
        return 2
    bench_all = np.concatenate(bench_pts, axis=0)
    log(f"pass 1: {n_blocks} blocks, bench pixels={len(bench_all)}")

    # ---- restrict to the pluvial stand band, data-driven from the basin-wide flat-pixel histogram ----
    zb = bench_all[:, 2]
    hist, edges = np.histogram(zb, bins=np.arange(0.0, 3500.0, 2.0))
    k = np.ones(6) / 6.0
    hs = np.convolve(hist, k, mode="same")
    peaks = [int(i) for i in range(2, hs.size - 2)
             if hs[i] == hs[i - 2:i + 3].max() and hs[i] >= 0.20 * hs.max()]
    peak_z = sorted(0.5 * (edges[i] + edges[i + 1]) for i in peaks)
    z_lo_b, z_hi_b = (peak_z[0] - args.stand_band_tol_m, peak_z[-1] + args.stand_band_tol_m)
    in_band = (zb >= z_lo_b) & (zb <= z_hi_b)
    log(f"flat-pixel histogram -> {len(peak_z)} stands at z={np.round(peak_z, 0).tolist()}; "
        f"band [{z_lo_b:.0f}, {z_hi_b:.0f}] m keeps {int(in_band.sum())} of {zb.size} pixels")
    bench_all = bench_all[in_band]

    # ---- local stand filter: keep bench pixels whose elevation equals the local mode ----
    tile_m = args.isobase_tile_m
    tpx = int(round(tile_m / res))
    tr, tc = int(np.ceil(H / tpx)), int(np.ceil(W / tpx))
    surf = np.full((tr, tc), np.nan, dtype=np.float32)
    ti = np.clip((bench_all[:, 0] // tpx).astype(int), 0, tr - 1)
    tj = np.clip((bench_all[:, 1] // tpx).astype(int), 0, tc - 1)
    zz = bench_all[:, 2]
    order = np.lexsort((zz, tj, ti))
    ti_s, tj_s, zz_s = ti[order], tj[order], zz[order]
    bounds = np.nonzero(np.diff(ti_s * tc + tj_s))[0]
    starts = np.concatenate([[0], bounds + 1]); ends = np.concatenate([bounds + 1, [len(zz_s)]])
    for a, b_ in zip(starts, ends):
        vals = zz_s[a:b_]
        if vals.size < args.min_tile_support:
            continue
        hist, edges = np.histogram(vals, bins=np.arange(max(np.floor(vals.min()), args.z_lo),
                                                       min(np.ceil(vals.max()), args.z_hi) + 2.0,
                                                       args.stand_bin_m))
        if hist.size == 0:
            continue
        k = int(np.argmax(hist))
        if hist[k] < max(6, args.min_tile_support // 4):
            continue
        lo, hi = edges[k], edges[k + 1]
        inb = vals[(vals >= lo) & (vals <= hi)]
        surf[ti_s[a], tj_s[a]] = float(np.median(inb))
    tile_i = (bench_all[:, 0] // tpx).astype(int); tile_j = (bench_all[:, 1] // tpx).astype(int)
    tile_z = surf[np.clip(tile_i, 0, tr - 1), np.clip(tile_j, 0, tc - 1)]
    stand_ok = np.isfinite(tile_z) & (np.abs(bench_all[:, 2] - tile_z) <= args.stand_tol_m)

    # ---- the isobase itself: robust quadratic (absorbs rebound + regional tilt, cannot follow
    #      a fan apron or a single scarp -- see datum.isobase_quadratic) ----
    bx = src.transform.c + (bench_all[stand_ok, 1] + 0.5) * res
    by = src.transform.f - (bench_all[stand_ok, 0] + 0.5) * res
    bz = bench_all[stand_ok, 2]
    if bz.size < 500:
        log(f"FATAL: only {bz.size} stand-consistent bench pixels; nothing to fit")
        return 2
    fit = datum.isobase_quadratic(bx, by, bz)
    log(f"isobase quadratic fit: n={fit['n']} rmad={fit['rmad']:.2f} m  "
        f"coeffs[km]={np.round(fit['coeffs'], 2).tolist()}")
    resid_all = bench_all[stand_ok, 2] - datum.isobase_eval(fit, bx, by)
    log(f"datum residual on bench pixels: p05={np.percentile(resid_all, 5):.1f} "
        f"p50={np.percentile(resid_all, 50):.1f} p95={np.percentile(resid_all, 95):.1f} m; "
        f"|r|<={args.shore_tol_m:.0f} m for {float((np.abs(resid_all) <= args.shore_tol_m).mean()):.3f} of pixels")

    def isobase_block(r0_, c0_, r1_, c1_):
        rows_ = np.arange(r0_, r1_); cols_ = np.arange(c0_, c1_)
        xx = src.transform.c + (cols_ + 0.5) * res
        yy = src.transform.f - (rows_ + 0.5) * res
        return datum.isobase_eval(fit, xx[None, :] * np.ones((len(rows_), 1)),
                                  yy[:, None] * np.ones((1, len(cols_))))

    # ---------------- pass 2: shoreline strands (profiles) + datum-step loci ----------------
    loci: list[dict] = []
    segments_meta: list[dict] = []
    for (r0, c0, r1, c1) in block_windows(H, W, block_px, overlap_px):
        z = read_z(src, Window(c0, r0, c1 - c0, r1 - r0))
        if not np.isfinite(z).any():
            continue
        if np.nanmin(z) > args.z_hi or np.nanmax(z) < args.z_lo:
            continue
        b = datum.bench_response(z, res, flat_slope=args.flat_slope, riser_slope=args.riser_slope)
        if (~np.isfinite(z)).any():
            ind = ndimage.distance_transform_edt(~np.isfinite(z), return_distances=False,
                                                 return_indices=True)
            z_filled = z[tuple(ind)]
        else:
            z_filled = z
        rows = np.arange(r0, r1); cols = np.arange(c0, c1)
        iso = isobase_block(r0, c0, r1, c1)
        # ---- (a) the lane's core signal: steps in the isobase residual ----
        ds = datum.datum_step_loci(z_filled, iso, b["score"], res,
                                   min_step_m=args.min_step_m,
                                   min_datum_evidence=args.min_datum_evidence,
                                   max_shore_distance_m=args.max_shore_distance_m,
                                   suppression_m=args.locus_separation_m,
                                   max_loci=args.max_loci_per_block)
        for e in ds.get("loci", []):
            if e["row"] < 0.5 * overlap_px or e["col"] < 0.5 * overlap_px or \
               e["row"] > (r1 - r0) - 0.5 * overlap_px or e["col"] > (c1 - c0) - 0.5 * overlap_px:
                continue                    # drop block-edge duplicates (kept by the neighbour)
            loci.append(dict(kind="datum_step", row=e["row"] + r0, col=e["col"] + c0,
                             weight=float(e["score"]), step_m=float(e["step_m"]),
                             datum_evidence=float(e["datum_evidence"]),
                             shore_distance_m=float(e["shore_distance_m"]),
                             strike_deg=float(e["strike_deg"]), seg=-1, s_m=float("nan")))
        # ---- (b) shoreline strands: the profile deliverable + deflection loci ----
        shore = datum.shoreline_mask(z, b, iso, tol_m=args.shore_tol_m,
                                     min_score=args.bench_min_score)
        lab, n = ndimage.label(shore, structure=np.ones((3, 3), int))
        scarp_blk = datum.ScarpField.from_dem(z_filled, res, sigma_m=args.scarp_sigma_m)
        for k in range(1, n + 1):
            rr, cc = np.nonzero(lab == k)
            if rr.size < args.min_segment_px:
                continue
            pts = np.stack([rr, cc], axis=1).astype(np.float64)
            for chain in datum.chains_from_component(pts, res, max_jump_m=args.max_chain_jump_m,
                                                     min_chain_px=args.min_segment_px):
                cpts = pts[chain]
                xy = cpts * res
                centred = xy - xy.mean(0)
                _, sv, _ = np.linalg.svd(centred, full_matrices=False)
                elong = float(sv[0] / (sv[1] + 1e-9))
                length = float(sv[0] * 2 * np.sqrt(2.0))
                if elong < args.min_elongation or length < args.min_length_m:
                    continue
                prof = datum.profile(cpts, z, iso, res)
                steps = datum.flag_steps(prof, window_m=args.step_window_m, res=res,
                                         min_step_m=args.min_step_m)
                defl = datum.flag_deflections(prof, res=res, window_m=args.step_window_m,
                                              min_delta_deg=args.min_deflection_deg)
                seg_id = len(segments_meta)
                segments_meta.append(dict(seg=seg_id, block=[r0, c0, r1, c1],
                                          n_px=int(cpts.shape[0]), length_m=length,
                                          elongation=elong, n_steps=len(steps),
                                          n_deflections=len(defl),
                                          from_component_px=int(rr.size)))
                for e in steps + defl:
                    i = e["i"]
                    lr = float(cpts[i, 0]); lc = float(cpts[i, 1])
                    ev = float(scarp_blk.sample(lr, lc, scarp_blk.evidence))
                    if ev < args.min_locus_evidence:
                        continue
                    weight = (abs(e["step_m"]) if e["kind"] == "step"
                              else abs(e["delta_deg"]) / 10.0) * (0.5 + ev)
                    loci.append(dict(kind=e["kind"], row=lr + r0, col=lc + c0, seg=seg_id,
                                     s_m=float(e["s_m"]), weight=float(weight),
                                     value=float(e.get("step_m", e.get("delta_deg"))),
                                     evidence=ev))
                if (len(steps) or len(defl)) and len(segments_meta) <= 400:
                    np.save(out_dir / f"profile_seg{seg_id:03d}.npy",
                            np.stack([prof["s"], prof["z"], prof["isobase"], prof["r"],
                                      np.nan_to_num(prof["azimuth"])], axis=1))
        del b, shore, z
    log(f"pass 2: segments={len(segments_meta)} flagged loci={len(loci)}")

    # ---------------- traces ------------------------------------------------------------------
    (out_dir / f"{args.name}.loci.json").write_text(json.dumps(loci, indent=1))
    loci_sorted = sorted(loci, key=lambda e: -e["weight"])
    chosen: list[dict] = []
    for e in loci_sorted:
        if len(chosen) >= args.max_loci:
            break
        if all(np.hypot(e["row"] - c["row"], e["col"] - c["col"]) * res > args.locus_separation_m
               for c in chosen):
            chosen.append(e)
    log(f"loci kept after {args.locus_separation_m:.0f} m separation: {len(chosen)}")

    half_px = int(round(args.trace_window_m / 2 / res))
    traces: list[dict] = []
    for j, e in enumerate(chosen):
        r0 = max(0, int(e["row"]) - half_px); c0 = max(0, int(e["col"]) - half_px)
        r1 = min(H, int(e["row"]) + half_px); c1 = min(W, int(e["col"]) + half_px)
        z = read_z(src, Window(c0, r0, c1 - c0, r1 - r0))
        if not np.isfinite(z).any():
            continue
        # fill any NaN by nearest interpolation so the Hessian is defined at block edges
        if (~np.isfinite(z)).any():
            ind = ndimage.distance_transform_edt(~np.isfinite(z), return_distances=False,
                                                 return_indices=True)
            z = z[tuple(ind)]
        scarp = datum.ScarpField.from_dem(z, res)
        seed = (e["row"] - r0, e["col"] - c0)
        path = datum.trace_from_seed(scarp, seed, max_len_m=args.max_trace_len_m,
                                     min_evidence=args.min_trace_evidence)
        if (j < 8):
            ev_here = [scarp.sample(q[0], q[1], scarp.evidence) for q in path]
            log(f"  locus {j} {e['kind']} row={e['row']:.0f} col={e['col']:.0f} "
                f"strike={scarp.sample(seed[0], seed[1], scarp.strike_deg):.0f} "
                f"evid_seed={scarp.sample(seed[0], seed[1], scarp.evidence):.3f} "
                f"path={len(path)} mean_evid={np.mean(ev_here) if ev_here else float('nan'):.3f}")
        if len(path) < 8:                       # shorter than ~1.6 km: not worth emission mass
            continue
        ev = float(np.mean([scarp.sample(p[0], p[1], scarp.evidence) for p in path]))
        traces.append(dict(seed_rc=[seed[0] + r0, seed[1] + c0],
                           rowcol=[[p[0] + r0, p[1] + c0] for p in path],
                           evidence=ev, loci=[e], kind=e["kind"], weight=e["weight"]))
        del z
        if (j + 1) % 50 == 0:
            log(f"traces {j + 1}/{len(chosen)} (kept {len(traces)})")
    log(f"traces kept: {len(traces)}")

    # ---------------- emission -----------------------------------------------------------------
    with rasterio.open(args.dem) as d:
        dem_transform = d.transform
    emis, emis_summary = datum.emit_dots(
        traces, dem_transform, catalogue=known, footprint=footprint,
        spacing_px=args.dot_spacing_px, min_catalogue_px=args.min_catalogue_px,
        max_dots=args.max_dots)

    # ---------------- write + receipt ----------------------------------------------------------
    tif = out_dir / f"{args.name}.tif"
    receipt = grid.write_submission(tif, emis)
    audit = metric.credit_audit(emis > 0)
    receipt.update({"audit": audit, "n_traces": len(traces),
                    "n_loci_flagged": len(loci), "n_loci_emitted": len(chosen),
                    "params": vars(args)})
    (out_dir / f"{args.name}.receipt.json").write_text(json.dumps(receipt, indent=1))
    (out_dir / f"{args.name}.traces.json").write_text(json.dumps(
        {"traces": [dict(t, n_points=len(t["rowcol"])) for t in traces]}, indent=1))
    (out_dir / f"{args.name}.segments.json").write_text(json.dumps(segments_meta, indent=1))
    log(f"WROTE {tif} sha256={receipt['sha256'][:16]} dots={receipt['n_positive']} "
        f"mass={receipt['total_mass']:.1f} legal={receipt['legal']} "
        f"redundancy={audit['redundancy_fraction']:.3f} elapsed={time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
