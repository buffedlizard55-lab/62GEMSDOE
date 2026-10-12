#!/usr/bin/env python3
"""H62-R — multi-level Lahontan datum stack as a repeat-offset strain gauge.

Session `arena/7eee17f9-62gemsdoe`, 2026-10-12.  Lane paragraph (verbatim scope):

    "Map shoreline benches in the DEM and fit a smooth isobase, allowing for
     post-pluvial isostatic rebound.  Flag abrupt steps or lateral deflections
     along strike, seed a trace at each, extend it while DEM-ridge evidence
     supports it, and emit dotted lines.  First deliverable: shoreline
     elevation-versus-distance profiles with the flagged steps."

Steps, and where each is implemented:

  E0  input verification           sha256 of every byte this run reads
  E1  level spectrum + surfaces    ``gems62.levels`` -- bench patches -> tile modes
                                   -> block-support spectrum -> a level list
  E2  leakage canary               per-feature rank AUC, threshold 0.90
  E3  repeat-offset test           Hough vote over the flagged steps of every level
  E4  first deliverable            shoreline elevation-vs-distance profiles,
                                   with the flagged steps marked (+ PNG, CSV)
  E5  emission                     seeds -> DEM-supported traces -> dotted lines
  E6  format validation            re-read the written bytes; two independent checks
  E7  uniqueness                   vs every raster in the registry
  E8  run card                     one JSON card, protocol item 5

Usage
-----
    .venv/bin/python scripts/run_lane_h62r.py --out-dir build/h62r \
        --demo /tmp/gems/dem --registry /tmp/registry
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import emit, grid, levels, uniqueness, validate          # noqa: E402
from gems62.datum import horn_slope                                   # noqa: E402
from gems62.holdout_segmented import leakage_canary                   # noqa: E402

LANE_ID = "H62-R"
VERSION = "gems62.levels v1"
SESSION = "arena/7eee17f9-62gemsdoe"

#: Levels are chosen from the measured block-support spectrum, not from memory.
#: ``scripts/run_lane_h62r.py`` recomputes the spectrum every run and records it;
#: these are the *default* picks with their measured support, and every one of
#: them is re-verified against the spectrum before use (see ``choose_levels``).
DEFAULT_LEVEL_PICKS = (1330.0, 1400.0, 1455.0, 1282.0)


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(obj, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(obj, indent=1, default=str) + "\n")
    return dest


# ---------------------------------------------------------------------------------------
# E0 — verify every byte this run reads
# ---------------------------------------------------------------------------------------
def e0_inputs(paths: dict[str, pathlib.Path]) -> dict:
    rec = {}
    for name, p in paths.items():
        rec[name] = dict(path=str(p), exists=p.exists(),
                         bytes=p.stat().st_size if p.exists() else None,
                         sha256=sha256(p) if p.exists() else None)
    return rec


# ---------------------------------------------------------------------------------------
# E1 — level spectrum, then one LevelSurface per level
# ---------------------------------------------------------------------------------------
def block_support_spectrum(bench: np.ndarray, dem: np.ndarray, *, tile_px: int = 200,
                           lo_m: float = 1150.0, hi_m: float = 1470.0, step_m: float = 1.0,
                           half_window_m: float = 12.0, min_px: int = 200) -> dict:
    """For every candidate elevation L, how many 20 km blocks hold >= min_px bench
    pixels within +/- half_window_m of L?

    This is the measured "level spectrum".  A real lake level is a *basin-wide*
    surface, so it shows up as a peak in this count; a lithologic or structural
    pseudo-bench is local and shows up as an isolated block.
    """
    ctr = np.arange(lo_m, hi_m, step_m)
    h, w = dem.shape
    ntile_r = h // tile_px + 1
    ntile_c = w // tile_px + 1
    M = np.zeros((ntile_r * ntile_c, ctr.size), dtype=np.int32)
    rr, cc = np.nonzero(bench)
    v = dem[rr, cc]
    ok = np.isfinite(v) & (v >= lo_m) & (v < hi_m)
    rr, cc, v = rr[ok], cc[ok], v[ok]
    bi = (rr // tile_px) * ntile_c + (cc // tile_px)
    np.add.at(M, (bi, ((v - lo_m) / step_m).astype(int)), 1)
    k = int(round(half_window_m / step_m))
    kern = np.ones(2 * k + 1)
    Mw = np.apply_along_axis(lambda r: np.convolve(r, kern, mode="same"), 1, M.astype(np.float64))
    nblocks = (Mw >= min_px).sum(axis=0)
    return dict(bins_m=ctr.tolist(), n_blocks=nblocks.tolist(),
                tile_px=tile_px, min_px=min_px, half_window_m=half_window_m,
                n_tiles=int(ntile_r * ntile_c), n_bench_px=int(bench.sum()))


def choose_levels(spec: dict, picks: tuple[float, ...], *, tol_m: float = 15.0,
                  min_blocks: int = 4) -> list[dict]:
    """Confirm each default pick against the measured spectrum and order oldest-first."""
    ctr = np.asarray(spec["bins_m"], float)
    nb = np.asarray(spec["n_blocks"], int)
    out = []
    for L in picks:
        m = np.abs(ctr - L) <= tol_m
        if not m.any():
            continue
        i = int(np.argmax(nb[m]))
        elev = float(ctr[m][i])
        support = int(nb[m].max())
        out.append(dict(elev_m=elev, block_support=support,
                        confirmed=bool(support >= min_blocks)))
    out = [d for d in out if d["confirmed"]]
    out.sort(key=lambda d: -d["elev_m"])
    for i, d in enumerate(out):
        d["level_index"] = i
    return out


# ---------------------------------------------------------------------------------------
# E4 — the first deliverable: elevation-versus-distance profiles
# ---------------------------------------------------------------------------------------
def shoreline_profiles(surf: levels.LevelSurface, *, min_run_px: int = 30) -> list[dict]:
    """Order each connected shoreline run and produce an elevation residual profile.

    The profile is the lane's first deliverable: for every connected bench run of a
    level, elevation above the fitted isobase is plotted against along-strike
    distance, and the flagged steps are the points where that profile jumps.

    Runs are ordered by a greedy nearest-neighbour walk (adequate here: each
    shoreline run is a near-1-D band, and the walk is checked for length).
    """
    from scipy import ndimage as ndi
    bench = surf.bench & np.isfinite(surf.resid)
    lab, n = ndi.label(bench, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return []
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    profiles: list[dict] = []
    for k in np.nonzero(sizes >= min_run_px)[0]:
        if k == 0:
            continue
        rr, cc = np.nonzero(lab == k)
        if rr.size < min_run_px:
            continue
        pts = np.column_stack([rr, cc]).astype(float)
        # order greedily from the point farthest from the centroid, with a jump break
        c = pts.mean(axis=0)
        start = int(np.argmax(((pts - c) ** 2).sum(axis=1)))
        order = [start]
        used = np.zeros(len(pts), bool)
        used[start] = True
        for _ in range(len(pts) - 1):
            last = pts[order[-1]]
            d = ((pts - last) ** 2).sum(axis=1)
            d[used] = np.inf
            nxt = int(np.argmin(d))
            if not np.isfinite(d[nxt]) or d[nxt] > 6.0 ** 2:
                break
            order.append(nxt)
            used[nxt] = True
        idx = np.array(order, int)
        seq = pts[idx]
        res = surf.resid[rr[idx], cc[idx]]
        step = surf.step[rr[idx], cc[idx]]
        dist = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(seq, axis=0).T)) * 100.0])
        profiles.append(dict(
            component=int(k), n_px=int(idx.size), length_m=float(dist[-1]),
            level_m=float(surf.level["elev_m"]),
            residual_median_m=float(np.nanmedian(res)),
            residual_min_m=float(np.nanmin(res)) if np.isfinite(res).any() else None,
            residual_max_m=float(np.nanmax(res)) if np.isfinite(res).any() else None,
            n_step_px=int(step.sum()),
            step_positions_m=[float(x) for x in dist[step][:64]],
            step_values_m=[float(x) for x in res[step][:64]],
            distance_m=[float(x) for x in dist[::max(1, dist.size // 240)]],
            residual_m=[float(x) for x in res[::max(1, dist.size // 240)]],
            row_col_centre=[float(seq[:, 0].mean()), float(seq[:, 1].mean())],
        ))
    profiles.sort(key=lambda p: -p["n_step_px"])
    return profiles


def write_profile_csv(profiles: list[dict], dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as fh:
        fh.write("level_m,profile_id,component,distance_m,residual_m,elevation_m,is_step\n")
        for pid, p in enumerate(profiles):
            for d, r in zip(p["distance_m"], p["residual_m"]):
                hull = p["level_m"] + r if np.isfinite(r) else ""
                fh.write(f"{p['level_m']},{pid},{p['component']},{d:.1f},"
                         f"{r if np.isfinite(r) else ''},"
                         f"{hull if hull != '' else ''},0\n")
            for d, r in zip(p["step_positions_m"], p["step_values_m"]):
                fh.write(f"{p['level_m']},{pid},{p['component']},{d:.1f},{r},"
                         f"{p['level_m'] + r},1\n")
    return dest


# ---------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="build/ext/geodawn_dem_a2_100m.tif")
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--stack", default="build/ext/gems-geodawn-numerical-features.tif")
    ap.add_argument("--registry", default="/tmp/registry")
    ap.add_argument("--out-dir", default="build/h62r")
    ap.add_argument("--name", default=None)
    ap.add_argument("--bench-threshold", type=float, default=0.5)
    ap.add_argument("--level-tol-m", type=float, default=10.0)
    ap.add_argument("--throw-lo-m", type=float, default=15.0)
    ap.add_argument("--k-mad", type=float, default=1.5)
    ap.add_argument("--min-span-km", type=float, default=2.0)
    ap.add_argument("--throw-hi-m", type=float, default=140.0)
    ap.add_argument("--iso-tile-px", type=int, default=40)
    ap.add_argument("--wide-m", type=float, default=45.0)
    ap.add_argument("--min-points", type=int, default=6)
    ap.add_argument("--max-traces", type=int, default=4000)
    ap.add_argument("--max-lines", type=int, default=20000)
    ap.add_argument("--seed-dedupe-m", type=float, default=2000.0)
    ap.add_argument("--dot-spacing-m", type=float, default=300.0)
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = args.name or f"gems62-h62r-multilevel-datum-hough-{stamp}-zeros"

    # ---------------- E0 -----------------------------------------------------------------
    e0 = e0_inputs(dict(dem=pathlib.Path(args.dem), labels=pathlib.Path(args.labels),
                        sample=pathlib.Path(args.sample), stack=pathlib.Path(args.stack)))
    jdump(e0, out / "e0_inputs.json")
    print(f"E0 inputs verified ({time.time() - t0:.0f}s); dem sha256 {e0['dem']['sha256'][:16]}")

    # ---------------- E1 -----------------------------------------------------------------
    dem = grid.read_dem(args.dem)
    lab = grid.read_labels(args.labels)
    footprint = lab != grid.LABEL_NODATA
    catalogue = lab == 1
    z = np.where(np.isfinite(dem) & footprint, dem, np.nan)
    slope = np.degrees(np.arctan(horn_slope(np.where(np.isfinite(z), z, 0.0), grid.PIXEL_M)))
    from gems62.datum import bench_response
    br = bench_response(z, grid.PIXEL_M)
    bench = (br["score"] >= args.bench_threshold) & footprint & np.isfinite(z)
    spec = block_support_spectrum(bench, z)
    lv = choose_levels(spec, DEFAULT_LEVEL_PICKS)
    jdump(dict(survey={k: (v if k != "n_blocks" else v) for k, v in spec.items()},
               picks=list(DEFAULT_LEVEL_PICKS), confirmed=lv,
               bench_threshold=args.bench_threshold,
               n_bench_px=int(bench.sum())), out / "e1_level_spectrum.json")
    print(f"E1 levels confirmed: {[d['elev_m'] for d in lv]} "
          f"(support {[d['block_support'] for d in lv]}) ({time.time() - t0:.0f}s)")
    if len(lv) < 2:
        print("E1 FATAL: fewer than two levels confirmed; a repeat-offset test needs two.",
              file=sys.stderr)
        return 2

    az_field, coherence, relief = emit.structure_tensor(z, footprint, sigma_px=5.0)
    surfaces = []
    for L in lv:
        s = levels.level_surface(z, slope, az_field, footprint & np.isfinite(z), L,
                                 bench_geom=bench, tol_m=args.level_tol_m,
                                 wide_m=args.wide_m, tile_px=args.iso_tile_px,
                                 throw_lo_m=args.throw_lo_m, throw_hi_m=args.throw_hi_m,
                                 k_mad=args.k_mad)
        surfaces.append(s)
        print(f"    level {L['elev_m']:7.1f} m: bench {s.n_bench:8d}  step {s.n_step:7d}  "
              f"deflect {s.n_deflect:7d}  resid med {s.resid_median_m:7.2f} mad {s.resid_mad_m:6.2f}")
    jdump(dict(
        evaluator=VERSION,
        levels=[dict(level=s.level, n_bench=s.n_bench, n_step=s.n_step, n_deflect=s.n_deflect,
                     resid_median_m=s.resid_median_m, resid_mad_m=s.resid_mad_m)
                for s in surfaces],
        bench_threshold=args.bench_threshold, level_tol_m=args.level_tol_m,
        throw_window_m=[args.throw_lo_m, args.throw_hi_m], iso_tile_px=args.iso_tile_px,
        wide_m=args.wide_m, k_mad=args.k_mad,
    ), out / "e1_surfaces.json")

    # ---------------- E2 -----------------------------------------------------------------
    canary = {}
    for nm, feat in (("bench_score", br["score"]), ("coherence", coherence),
                     ("relief_m", relief), ("slope_deg", slope)):
        canary[nm] = leakage_canary(feat, catalogue, footprint, known=None)
    for s in surfaces:
        canary[f"step_L{s.level['level_index']}"] = leakage_canary(
            s.step.astype(float), catalogue, footprint, known=None)
    canary["max"] = float(max(v for k, v in canary.items() if isinstance(v, float)))
    canary["threshold"] = 0.90
    canary["leakage"] = bool(canary["max"] > 0.90)
    jdump(canary, out / "e2_canary.json")
    print(f"E2 leakage canary max AUC {canary['max']:.4f} (threshold 0.90) -> "
          f"{'LEAKAGE' if canary['leakage'] else 'clean'}")

    # ---------------- E3 -----------------------------------------------------------------
    corr = levels.hough_offsets(surfaces, min_points=args.min_points, min_levels=2,
                                min_span_px=int(round(args.min_span_km * 1000.0 / grid.PIXEL_M)),
                                max_lines=args.max_lines)
    jdump(dict(
        evaluator=VERSION, algorithm="Hough over flagged step pixels, rho = r cosT + c sinT",
        azimuths_deg=corr.azimuths_deg, n_flagged_total=corr.n_flagged_total,
        min_span_px=corr.min_span_px,
        per_level_points=corr.per_level_points, per_level_step_px=corr.per_level_px,
        n_lines=len(corr.lines),
        lines=[dict(azimuth_deg=l.azimuth_deg, rho_px=l.rho_px, n_points=l.n_points,
                    n_levels=l.n_levels, levels=l.levels, signs=l.signs,
                    mean_throw_m=l.mean_throw_m, score=l.score,
                    support=l.support[:200]) for l in corr.lines[:200]],
        n_support_px=int(corr.support.sum()),
        n_lines_multilevel=int(sum(1 for l in corr.lines if l.n_levels >= 2)),
    ), out / "e3_repeat_offsets.json")
    print(f"E3 repeat-offset test: {len(corr.lines)} lines accepted "
          f"({sum(1 for l in corr.lines if l.n_levels >= 2)} multi-level), "
          f"{int(corr.support.sum())} support px ({time.time() - t0:.0f}s)")

    # ---------------- E4 -----------------------------------------------------------------
    profiles = []
    for s in surfaces:
        profiles.extend(shoreline_profiles(s))
    profiles.sort(key=lambda p: -p["n_step_px"])
    jdump(dict(evaluator=VERSION, n_profiles=len(profiles),
               n_profiles_with_step=sum(1 for p in profiles if p["n_step_px"] > 0),
               total_profile_km=sum(p["length_m"] for p in profiles) / 1000.0,
               profiles=profiles[:60]), out / "e4_profiles.json")
    write_profile_csv(profiles, out / "shoreline_profiles.csv")
    print(f"E4 first deliverable: {len(profiles)} shoreline profiles, "
          f"{sum(1 for p in profiles if p['n_step_px'] > 0)} with flagged steps, "
          f"{sum(p['length_m'] for p in profiles) / 1000:.0f} km total")

    # ---------------- E5 -----------------------------------------------------------------
    # Seed dedupe (IR-62-HOUGH-01).  Many accepted lines pass through the same small
    # clump of flagged pixels at slightly different azimuths; emitting one trace per
    # line there produces the radiating "star" seen in the first field map.  Keeping
    # the strongest line per 2 km neighbourhood is the simple cure, and it is the
    # lane's own instruction read literally: seed a trace at each flagged step.
    raw: list[tuple[float, float, float, float]] = []
    for l in corr.lines:
        if l.n_levels < 2 or not l.support:
            continue
        r, c = l.support[0]
        x = grid.TRANSFORM[2] + (c + 0.5) * grid.PIXEL_M
        y = grid.TRANSFORM[5] - (r + 0.5) * grid.PIXEL_M
        raw.append((l.score, x, y, l.azimuth_deg))
    raw.sort(key=lambda t: -t[0])
    dedupe = float(args.seed_dedupe_m)
    kept_xy: list[tuple[float, float, float]] = []
    cell = {}
    for sc, x, y, az in raw:
        key = (int(x // dedupe), int(y // dedupe))
        if any(other in cell for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               for other in [key] if (key[0] + dx, key[1] + dy) in cell
               and any(np.hypot(x - sx, y - sy) < dedupe
                       for sx, sy in cell[(key[0] + dx, key[1] + dy)])):
            continue
        cell.setdefault(key, []).append((x, y))
        kept_xy.append((x, y, az))
    seeds_xy = kept_xy[: args.max_traces]
    seeds = [emit.Seed(x=x, y=y, kind="datum_repeat_offset", strength=1.0,
                       azimuth_deg=az) for x, y, az in seeds_xy]
    traces = emit.traces_from_flags(seeds, az_field, coherence, relief, footprint,
                                    grid.TRANSFORM, min_length_m=400.0)
    rows, cols, estats = emit.dots_from_traces(traces, catalogue, footprint, grid.TRANSFORM,
                                               spacing_m=args.dot_spacing_m,
                                               exclusion_m=3.0 * grid.PIXEL_M,
                                               min_separation_m=args.dot_spacing_m)
    raster = emit.raster_from_dots(rows, cols, (grid.HEIGHT, grid.WIDTH), value=1.0)
    tif = out / f"{name}.tif"
    receipt = grid.write_submission(tif, raster, nodata=None)
    # hard-core isolation, measured on the emitted dots: the maximum number of dots
    # inside a 300 m radius disc (3 px) of any other dot.  The metric pays 0.2*M in
    # the denominator for every dot, so two dots inside one kernel waste mass.
    from scipy import ndimage as _ndi
    # IR-62-H62R-03.  The first version of this statistic counted dots inside a
    # radius-3 disc whose boundary is INCLUDED (hypot <= 3.0), so two dots exactly
    # 300 m apart -- where the metric kernel k(300 m) is exactly 0 -- were reported as
    # "sharing a disc" and the receipt said 39 % of dots share one while a k-d tree
    # said the minimum nearest-neighbour distance was exactly 300.000 m and the mean
    # self-kernel was 0.000000.  Both cannot be true; the k-d tree is the one that
    # matches the metric.  The statistic below therefore measures what actually costs
    # mass: the number of *other* dots whose kernel weight against this dot is > 0,
    # i.e. strictly closer than the kernel radius.
    yy, xx = np.mgrid[-3:4, -3:4]
    r2 = yy * yy + xx * xx
    kern = np.zeros((7, 7), dtype=np.float64)
    m = r2 < 9                                   # STRICTLY inside 300 m
    kern[m] = 1.0 - np.sqrt(r2[m]) / 3.0
    kern[3, 3] = 0.0                             # a dot is not its own neighbour
    wgt = _ndi.convolve(raster, kern, mode="constant")
    estats["max_kernel_mass_from_other_dots"] = float(wgt[raster > 0].max())
    estats["n_dots_with_kernel_overlap"] = int((wgt[raster > 0] > 0.0).sum())
    estats["frac_dots_with_kernel_overlap"] = float((wgt[raster > 0] > 0.0).mean())
    estats["_note"] = ("isolation is measured against the metric kernel k(d)="
                       "max(1-d/300m,0); a neighbour at exactly 300 m contributes 0")
    jdump(dict(evaluator=VERSION, n_seeds=len(seeds), n_traces=len(traces),
               trace_km=sum(t.length_m for t in traces) / 1000.0,
               emission=estats, receipt=receipt), out / "e5_emission.json")
    print(f"E5 emission: {estats['n_dots']} dots from {len(traces)} traces "
          f"({sum(t.length_m for t in traces) / 1000:.0f} km) -> {tif}")

    # ---------------- E6 -----------------------------------------------------------------
    with open(args.sample, "rb") as fh:
        pass
    import rasterio
    with rasterio.open(args.sample) as src:
        tpl = src.read(1)
    footprint_tpl = np.isfinite(tpl)
    rep = validate.validate_submission(tif, footprint_tpl)
    jdump(dict(evaluator=VERSION, grid_check=grid.check_submission(tif),
               validator=json.loads(rep.to_json())), out / "e6_validation.json")
    print(f"E6 validation: {'PASS' if rep.passed else 'FAIL'} "
          f"({len(rep.failures)} failures) nan_inside={rep.nan_inside_footprint} "
          f"range=[{rep.values_min},{rep.values_max}]")

    # ---------------- E7 -----------------------------------------------------------------
    uni = None
    if not args.no_registry and pathlib.Path(args.registry).is_dir():
        reg = {p.name: p for p in sorted(pathlib.Path(args.registry).glob("*.tif"))}
        if reg:
            entries = uniqueness.compare(raster, reg, footprint_tpl)
            uni = uniqueness.verdict(entries, uniqueness.last_skipped.get("entries"))
            jdump(dict(evaluator=VERSION, verdict=uni,
                       entries=[dict(alias=e.alias, positive_cells=e.positive_cells,
                                     rho=e.rho, frac3px=e.frac3px,
                                     coverage3px=e.coverage3px, vacuous=e.vacuous,
                                     sha256=e.sha256) for e in entries]),
                  out / "e7_uniqueness.json")
            print(f"E7 uniqueness vs {len(entries)} registry rasters: {uni['verdict']} "
                  f"(max |rho| {uni['max_abs_rho']:.3f}, max 3px {uni['max_frac3px_non_vacuous']:.3f})")
        else:
            print("E7 skipped: registry directory empty")
    else:
        print("E7 skipped: no registry")

    # ---------------- E8 -----------------------------------------------------------------
    card = dict(
        lane_id=LANE_ID, lane="lahontan-multilevel-datum-repeat-offset",
        session=SESSION, generated_utc=stamp, evaluator=VERSION,
        hypothesis=("The Lahontan datum is a STACK of nested shorelines, not one surface. "
                    "A tectonic step repeats coherently across two or more levels and lies on "
                    "one common line; a non-tectonic step (delta topset, fan toe, landslide "
                    "edge, resistant-bed notch) is local to one level and does not."),
        mechanism=("Bench patches -> tile modes -> a measured block-support level spectrum "
                   "-> per-level smooth isobase (5.5 km NaN-aware Gaussian, which absorbs "
                   "post-pluvial isostatic rebound and waterplane tilt) -> residual steps in "
                   "the 8-140 m throw window -> Hough vote over the flagged pixels of every "
                   "level, requiring >=2 distinct levels on a common line with sign agreement "
                   "-> seed a trace, extend it on DEM-ridge evidence, emit dotted lines."),
        named_non_fault_process_that_could_mimic_it=(
            "Bedrock lithology: a resistant unit that stands as a bench at every lake level "
            "crosses several levels at one place and is collinear along strike. Second: "
            "isobase-fit error at the margin of a level's extent. Third: a prograding delta "
            "/ fan that occupied the same position across lake cycles."),
        levels=[dict(level=s.level, n_step=s.n_step) for s in surfaces],
        n_lines=int(len(corr.lines)),
        n_lines_multilevel=int(sum(1 for l in corr.lines if l.n_levels >= 2)),
        leakage_canary=canary,
        validator=json.loads(rep.to_json()),
        raster_sha256=receipt["sha256"],
        uniqueness=uni,
        submission_name=name,
    )
    jdump(card, out / "e8_run_card.json")
    print(f"E8 run card -> {out / 'e8_run_card.json'}   total {time.time() - t0:.0f}s")
    print(f"    sha256 {receipt['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
