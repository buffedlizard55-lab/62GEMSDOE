#!/usr/bin/env python3
"""62GEMSDOE lane driver: Lahontan datum-offset strain gauge.

Pipeline (one experiment, one artifact):

  1. field      : persistent datum-step field from the pinned 100 m DEM
  2. canary     : every feature alone on the holdout (AUC > 0.90 => leakage)
  3. traces     : seed at each flagged step, extend while the evidence ridge
                  supports it, emit dotted lines (the lane's requested trace rule)
  4. holdout    : hide-and-recover pooled DTI (alpha 0.2 / beta 0.8, 300 m
                  triangular kernel) against equal-budget random-line and
                  random-dot controls, with a bootstrap CI
  5. submission : fail-closed validated single-band GeoTIFF + zip + receipt
  6. uniqueness : literal protocol gate against every accessible registry raster

Everything is written to ``evidence/`` and ``out/``; the deliverable raster goes
to ``docs/downloads/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid as gd_mod                      # noqa: E402
from gems62 import holdout_segmented as hs              # noqa: E402
from gems62 import lahontan, metric, submission_writer, uniqueness  # noqa: E402

CACHE = Path("/home/user/datacache")
DEM_PATH = CACHE / "g60/data/geodawn_dem_a2_100m.tif"
DEM_SHA = "d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431"
REGISTRY = Path("/home/user/datacache/registry")   # index.json + cache/*.tif
RIDGE_TOL_PX = 2          # lateral wander allowed when extending a trace
TRACE_MAX_PX = 60         # 6 km each way


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


FIELD_KEYS = ("bench", "slope", "step", "step_signed", "step_azim", "gated", "zone",
              "evidence", "habitat", "isobase", "anomaly")


def load_or_build(z: np.ndarray, footprint: np.ndarray, *, min_step: float,
                  max_step: float, tag: str = "lahontan62", rebuild: bool = False):
    """Build the step field, or reuse it when the cache was made by this code.

    The cache is keyed on the DEM hash, the detector source and the parameters, so
    a stale field can never be mistaken for a current one -- which matters, because
    an out-of-date cache silently invalidated a whole morning of debugging here.
    """
    src = (ROOT / "src" / "gems62" / "lahontan.py").read_bytes()
    key = hashlib.sha256(f"{DEM_SHA}\n{hashlib.sha256(src).hexdigest()}\n"
                         f"{min_step}|{max_step}".encode()).hexdigest()[:16]
    meta_path = CACHE / f"{tag}_meta.json"
    paths = {k: CACHE / f"{tag}_{k}.npy" for k in FIELD_KEYS}
    if not rebuild and meta_path.exists() and all(p.exists() for p in paths.values()):
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            meta = {}
        if meta.get("key") == key:
            fld = lahontan.DatumField()
            for k, p in paths.items():
                a = np.load(p)
                fld[k] = a.astype(bool) if k in ("bench", "zone", "habitat") else a
            fld["z"] = np.full(footprint.shape, np.float32(np.nan), np.float32)
            fld["aspect"] = np.zeros(footprint.shape, np.float32)
            fld["meta"] = meta.get("field_meta", {})
            fld["meta"].setdefault("min_step_m", float(min_step))
            print(f"[cache] reused {tag} fields (key {key})", flush=True)
            return fld
        print(f"[cache] key mismatch ({meta.get('key')} != {key}) -> rebuild", flush=True)
    fld = lahontan.build_field(z, footprint, min_step=min_step, max_step=max_step)
    for k, p in paths.items():
        np.save(p, fld[k].astype(np.float32))
    meta_path.write_text(json.dumps({"key": key, "dem_sha256": DEM_SHA,
                                      "fields": list(FIELD_KEYS),
                                      "field_meta": dict(fld.meta)},
                                     indent=1, default=float))
    print(f"[cache] wrote {tag} fields (key {key})", flush=True)
    return fld


# ----------------------------------------------------------------- emission
def seed_points(evidence: np.ndarray, gated: np.ndarray, zone: np.ndarray,
                min_step: float, sep_px: int = 8, max_seeds: int = 4000) -> np.ndarray:
    """Local maxima of the flagged step field, thinned by a spacing rule.

    ``zone`` is the lane's 'abrupt step' mask (field.zone): pixels where the
    datum offset passes the amplitude, persistence and linearity gates.  The
    anchor pixel of a step is the riser itself, which the flat-tread test
    rejects, so the mask is a 2 px dilation of the bench, not the bench.
    """
    src = np.where(zone & (gated >= min_step), evidence, 0.0).astype(np.float32)
    size = 2 * sep_px + 1
    mx = ndi.maximum_filter(src, size=size, mode="constant", cval=0.0)
    peaks = (src >= mx) & (src > 0)
    yy, xx = np.nonzero(peaks)
    if yy.size == 0:
        return np.zeros((0, 2), np.int32)
    order = np.argsort(-src[yy, xx])
    yy, xx = yy[order][:max_seeds], xx[order][:max_seeds]
    return np.stack([yy, xx], axis=1).astype(np.int32)


def extend_trace(field: "lahontan.DatumField", y0: int, x0: int, azim_deg: float,
                 *, max_px: int = TRACE_MAX_PX, tol: int = RIDGE_TOL_PX,
                 min_score: float = 0.05) -> np.ndarray:
    """Walk both ways from a seed while DEM/evidence ridge support persists.

    Direction comes from the flagged step's own trend; the walker keeps the
    lateral position that maximises the smoothed evidence within +-tol px, and
    stops when support drops under ``min_score`` for two consecutive steps.
    """
    ev = field.evidence
    th = np.radians(azim_deg)
    dx, dy = np.cos(th), np.sin(th)
    steps = []
    for sgn in (+1, -1):
        y, x = float(y0), float(x0)
        miss = 0
        for k in range(1, max_px + 1):
            ny = int(round(y + sgn * dy * k))
            nx = int(round(x + sgn * dx * k))
            best = (-1.0, ny, nx)
            for off in range(-tol, tol + 1):
                py = int(round(ny + off * dy))
                px = int(round(nx - off * dx))
                if 0 <= py < ev.shape[0] and 0 <= px < ev.shape[1]:
                    v = float(ev[py, px])
                    if v > best[0]:
                        best = (v, py, px)
            if best[0] < 0 or best[0] < min_score:
                miss += 1
                if miss >= 2:
                    break
                continue
            miss = 0
            steps.append((best[1], best[2], best[0]))
    if not steps:
        return np.array([[y0, x0]], np.int32)
    arr = np.array([(y0, x0)] + [(s[0], s[1]) for s in steps], np.int32)
    return arr


def emit_dots(field: "lahontan.DatumField", catalogue_visible: np.ndarray,
              footprint: np.ndarray, *, seeds: np.ndarray, spacing: int = 2,
              budget: int = 40_000, prune_px: int = 3, fill_spacing: int = 3,
              rng_seed: int = 7, prune: bool = True,
              trace_max_px: int = TRACE_MAX_PX,
              trace_min_score: float = 0.05) -> dict:
    """Dotted traces first (rank-ordered), then ranked fill from the field.

    Every emitted dot is pruned if it falls within ``prune_px`` of the visible
    mapped catalogue (the family's forensic rule: dots adjacent to the catalogue
    were net-negative on the live metric).
    """
    H, W = footprint.shape
    dots = np.zeros((H, W), bool)
    if prune and prune_px > 0:
        near_cat = ndi.binary_dilation(catalogue_visible, iterations=int(prune_px))
    elif prune:
        near_cat = np.asarray(catalogue_visible, bool)
    else:
        # holdout mode: pruning against the full catalogue would delete precisely
        # the hidden segments we are trying to recover, so it is switched off and
        # the evaluator's own visible-fault mask does the exclusion.
        near_cat = np.zeros(footprint.shape, bool)
    blocked = near_cat | ~footprint
    trace_len = 0
    order = np.argsort(-field.evidence[seeds[:, 0], seeds[:, 1]]) if len(seeds) else []
    used = 0
    traces = []
    for idx in order:
        if used >= budget:
            break
        y0, x0 = int(seeds[idx, 0]), int(seeds[idx, 1])
        az = float(field.step_azim[y0, x0])
        path = extend_trace(field, y0, x0, az, max_px=trace_max_px,
                            min_score=trace_min_score)
        trace_len += len(path)
        # dotted: every ``spacing`` px along the polyline
        sel = path[::spacing]
        ok = ~blocked[sel[:, 0], sel[:, 1]]
        take = sel[ok]
        if used + len(take) > budget:
            take = take[:budget - used]
        if len(take):
            dots[take[:, 0], take[:, 1]] = True
            used += int(len(take))
            traces.append(dict(seed=[y0, x0], azimuth_deg=az, n_px=int(len(path)),
                               n_dots=int(len(take))))
    n_trace = used
    # ranked fill inside the pluvial habitat, at fill_spacing
    if used < budget:
        cand = np.where(field.habitat & ~blocked, field.evidence, -1.0)
        # thin to a fill_spacing lattice so the fill spreads instead of clustering
        peak = ndi.maximum_filter(cand, size=2 * fill_spacing - 1, mode="constant", cval=-1.0)
        elig = (cand >= peak) & (cand > 0)
        yy, xx = np.nonzero(elig)
        if yy.size:
            v = cand[yy, xx]
            cut = np.partition(v, max(v.size - (budget - used), 0))[max(v.size - (budget - used), 0) - 1]
            keep = v >= cut
            yy, xx = yy[keep][:budget - used], xx[keep][:budget - used]
            dots[yy, xx] = True
            used = int(dots.sum())
    return dict(dots=dots, n_dots=int(dots.sum()), n_from_traces=n_trace,
                trace_px_total=trace_len, traces=traces[:50])


# ----------------------------------------------------------------- controls
def random_dots(shape, budget: int, eligible: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.nonzero(eligible)
    out = np.zeros(shape, bool)
    if yy.size == 0:
        return out
    pick = rng.choice(yy.size, size=min(budget, yy.size), replace=False)
    out[yy[pick], xx[pick]] = True
    return out


def random_lines(shape, budget: int, eligible: np.ndarray, seed: int,
                 seg_len: int = 60, spacing: int = 2) -> np.ndarray:
    """Equal-budget control: random-walk lines drawn inside the same habitat."""
    rng = np.random.default_rng(seed)
    yy, xx = np.nonzero(eligible)
    out = np.zeros(shape, bool)
    if yy.size == 0:
        return out
    n_needed = int(np.ceil(budget / max(spacing, 1)))
    for _ in range(4 * n_needed):
        if int(out.sum()) >= budget:
            break
        i = int(rng.integers(0, yy.size))
        y, x = float(yy[i]), float(xx[i])
        ang = float(rng.uniform(0, np.pi))
        for k in range(seg_len):
            y += np.cos(ang); x += np.sin(ang)
            ang += float(rng.normal(0, 0.12))
            iy, ix = int(round(y)), int(round(x))
            if 0 <= iy < shape[0] and 0 <= ix < shape[1] and eligible[iy, ix]:
                if k % spacing == 0:
                    out[iy, ix] = True
        if int(out.sum()) > budget:
            break
    return out


def pooled_with_ci(emitted_full: np.ndarray, ctx, mode: str, ci: float = 0.95) -> dict:
    """Pooled holdout DTI + a percentile bootstrap over fold cells."""
    res = hs.evaluate(emitted_full, ctx, cell_mode=mode)
    per = [v["dti"] for v in res["folds"].values()]
    rng = np.random.default_rng(1234)
    boots = []
    for _ in range(2000):
        s = rng.choice(per, size=len(per), replace=True)
        boots.append(float(np.mean(s)))
    lo, hi = np.percentile(boots, [100 * (1 - ci) / 2, 100 - 100 * (1 - ci) / 2])
    out = dict(res)
    out["dti_pooled"] = res["pooled_dti"]
    out["dti_ci95"] = [float(lo), float(hi)]
    out["coverage"] = res["pooled_coverage"]
    out["n_truth"] = res["pooled_n_truth"]
    out["n_cells"] = len(per)
    del out["folds"]
    return out


# ----------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=40_000)
    ap.add_argument("--spacing", type=int, default=2)
    ap.add_argument("--fill-spacing", type=int, default=3)
    ap.add_argument("--min-step", type=float, default=lahontan.MIN_STEP_M)
    ap.add_argument("--max-step", type=float, default=lahontan.MAX_STEP_M)
    ap.add_argument("--sep-px", type=int, default=8, help="seed thinning spacing")
    ap.add_argument("--max-seeds", type=int, default=4000)
    ap.add_argument("--trace-max-px", type=int, default=TRACE_MAX_PX,
                    help="trace extension length each way, px")
    ap.add_argument("--trace-min-score", type=float, default=0.05,
                    help="evidence level at which a trace stops being extended")
    ap.add_argument("--seed-min-step", type=float, default=None,
                    help="require a larger measured offset at the seed (m); "
                         "default is the field min_step")
    ap.add_argument("--no-fill", action="store_true", help="trace dots only")
    ap.add_argument("--skip-uniqueness", action="store_true",
                    help="omit the registry clearance pass (already in "
                         "evidence/uniqueness.json for this emission)")
    ap.add_argument("--no-controls", action="store_true",
                    help="skip the random dot/line controls (faster, same ranking)")
    ap.add_argument("--ladder", default="10000,20000,40000",
                    help="comma list of budgets to compare on the holdout")
    ap.add_argument("--emit", action="store_true", help="write the submission raster")
    ap.add_argument("--rebuild-field", action="store_true",
                    help="ignore the cached step field and recompute it")
    ap.add_argument("--name", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/lane62.json")
    args = ap.parse_args()
    # Fail fast on the writer's contract: it limits name and note to 140 chars and
    # demands a .tif suffix.  A violation used to surface only after the registry
    # uniqueness pass, i.e. ~50 minutes into the run, and cost the whole artifact.
    if not args.name.strip():
        raise SystemExit("--name is required with --emit")
    if len(args.note) > 140 or not args.note.strip():
        raise SystemExit(f"--note must be 1..140 characters (got {len(args.note)})")
    if not args.name.lower().endswith((".tif", ".tiff")):
        args.name = args.name + ".tif"
    # one place, both call sites: the holdout ladder and the artifact emission
    args.fill_spacing = 9999 if args.no_fill else args.fill_spacing
    t0 = time.time()
    log = dict(evidence_class="MEASURED",
               started_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               params={k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()})

    assert sha256(DEM_PATH) == DEM_SHA, "DEM hash pin failure"
    g = gd_mod.load_grid()
    import rasterio
    with rasterio.open(DEM_PATH) as src:
        zr = src.read(1).astype(np.float32)
    fld = load_or_build(zr, g.footprint, min_step=args.min_step, max_step=args.max_step,
                        rebuild=args.rebuild_field)
    log["field"] = dict(fld.meta, dem_sha256=DEM_SHA,
                        evidence_max=float(fld.evidence.max()),
                        step_median_on_flag=float(np.median(fld.step[fld.gated > 0])) if (fld.gated > 0).any() else None)
    del zr

    # ---------------------------------------------------------- holdout build
    ctx = hs.build_holdout(g)
    log["holdout"] = dict(evaluator="gems62.holdout_segmented v2 (template copy)",
                          cells=len(ctx.cells),
                          n_truth_total=int(sum(c.n_truth for c in ctx.cells)))

    # ------------------------------------------------------------- canary
    canary = {}
    rng = np.random.default_rng(3)
    for cell in ctx.cells:
        if cell.mode != "all":
            continue
        sl = cell.bbox
        truth = np.zeros(cell.active.shape, bool)
        truth[cell.truth_yx] = True
        sub = rng.integers(0, cell.active.size, size=200_000)
        dom = cell.active.ravel()
        for fname, arr in [("bench", fld.bench), ("abs_anomaly", np.abs(fld.anomaly)),
                           ("step", fld.step), ("evidence", fld.evidence),
                           ("slope", fld.slope)]:
            v = arr[sl].ravel()[sub].astype(np.float64)
            ok = np.isfinite(v) & dom.ravel()[sub]
            t = truth.ravel()[sub][ok]
            if t.sum() < 50 or (~t).sum() < 50:
                continue
            r = ndi.rank_data if False else None
            from scipy.stats import rankdata
            rk = rankdata(v[ok])
            n1, n0 = int(t.sum()), int((~t).sum())
            auc = (rk[t].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
            canary.setdefault(fname, []).append(float(auc))
    canary = {k: dict(n_cells=len(v), mean=float(np.mean(v)), min=float(np.min(v)),
                      max=float(np.max(v)), leakage_flag=bool(max(v) > 0.90))
              for k, v in canary.items()}
    log["leakage_canary"] = canary

    # ------------------------------------------------- budget ladder + controls
    visible_full = g.catalogue.copy()
    ladder = []
    for b in [int(x) for x in args.ladder.split(",") if x.strip()]:
        mss = args.seed_min_step or fld.meta["min_step_m"]
        seeds = seed_points(fld.evidence, fld.gated, fld.zone, mss,
                            sep_px=args.sep_px, max_seeds=args.max_seeds)
        em = emit_dots(fld, visible_full, g.footprint, seeds=seeds,
                       spacing=args.spacing, budget=b, fill_spacing=args.fill_spacing,
                       prune=False, trace_max_px=args.trace_max_px,
                       trace_min_score=args.trace_min_score)
        dots = em["dots"]
        hl = pooled_with_ci(dots, ctx, "all")
        hld = pooled_with_ci(dots, ctx, "detached")
        if args.no_controls:
            ctl_dots = ctl_lines = np.zeros(dots.shape, bool)
        else:
            ctl_dots = random_dots(dots.shape, b, fld.habitat & ~ndi.binary_dilation(g.catalogue, iterations=3), 11)
            ctl_lines = random_lines(dots.shape, b, fld.habitat & ~ndi.binary_dilation(g.catalogue, iterations=3), 12)
        ladder.append(dict(
            budget=b, emitted=int(dots.sum()), n_from_traces=em["n_from_traces"],
            trace_px_total=em["trace_px_total"],
            holdout_dti=hl["dti_pooled"], ci95=hl["dti_ci95"], n_truth=hl["n_truth"],
            coverage=hl["coverage"],
            holdout_dti_detached=hld["dti_pooled"],
            control_random_dots=(0.0 if args.no_controls else
                                 pooled_with_ci(ctl_dots, ctx, "all")["dti_pooled"]),
            control_random_lines=(0.0 if args.no_controls else
                                  pooled_with_ci(ctl_lines, ctx, "all")["dti_pooled"])))
        print(f"[ladder] b={b} emitted={ladder[-1]['emitted']} DTI={ladder[-1]['holdout_dti']:.4f} "
              f"ci={ladder[-1]['ci95']} rd={ladder[-1]['control_random_dots']:.4f} "
              f"rl={ladder[-1]['control_random_lines']:.4f}", flush=True)
        del dots, ctl_dots, ctl_lines, em, hl, hld
    log["budget_ladder"] = ladder
    best = max(ladder, key=lambda r: r["holdout_dti"])
    log["chosen_budget"] = best["budget"]

    # ------------------------------------------------------------- emission
    seeds = seed_points(fld.evidence, fld.gated, fld.zone,
                        args.seed_min_step or fld.meta["min_step_m"],
                        sep_px=args.sep_px, max_seeds=args.max_seeds)
    em = emit_dots(fld, visible_full, g.footprint, seeds=seeds, spacing=args.spacing,
                   trace_max_px=args.trace_max_px, trace_min_score=args.trace_min_score,
                   budget=best["budget"], fill_spacing=args.fill_spacing)
    dots = em["dots"]
    dcat = ndi.distance_transform_edt(~g.catalogue)
    log["emission"] = dict(n_dots=int(dots.sum()), n_seed_candidates=int(len(seeds)),
                           n_from_traces=em["n_from_traces"],
                           trace_px_total=em["trace_px_total"],
                           n_traces_listed=len(em["traces"]), traces=em["traces"][:20],
                           min_px_from_catalogue=float(dcat[dots].min()) if dots.any() else None,
                           median_px_from_catalogue=float(np.median(dcat[dots])) if dots.any() else None,
                           habitat_fraction=float(dots.sum() / max(int(fld.habitat.sum()), 1)))
    final = pooled_with_ci(dots, ctx, "all")
    final_d = pooled_with_ci(dots, ctx, "detached")
    log["holdout_final"] = dict(dti=final["dti_pooled"], ci95=final["dti_ci95"],
                                coverage=final["coverage"], n_truth=final["n_truth"],
                                n_emitted=final["emitted_pixels"],
                                detached_dti=final_d["dti_pooled"],
                                detached_ci95=final_d["dti_ci95"])
    np.save(CACHE / "dots62.npy", dots)
    np.save(CACHE / "evidence62.npy", fld.evidence.astype(np.float32))


    # ---------------------------------------------------------- submission
    if args.emit:
        out_tif = ROOT / "docs/downloads" / args.name
        pred = np.where(dots, 1.0, 0.0).astype(np.float32)
        receipt = submission_writer.write_submission(
            out_tif, pred, gd_mod.DATA_DIR / "sample_submission.tif", g.footprint,
            note=args.note, name=args.name.replace(".tif", ""), catalogue=g.catalogue,
            metadata=dict(lane="lahontan datum-offset", dem_sha256=DEM_SHA,
                          holdout_dti=best["holdout_dti"],
                          holdout_dti_pruned_emission=log["holdout_final"]["dti"],
                          chosen_budget=best["budget"]))
        log["submission"] = dict(file=out_tif.name, sha256=receipt["sha256"],
                                 bytes=receipt["bytes"], note=receipt["note"],
                                 checks_passed=all(receipt["validator"]["checks"].values()),
                                 validator=receipt["validator"]["checks"],
                                 info=receipt["validator"]["info"])
        (ROOT / "docs/downloads" / (out_tif.name + ".json")).write_text(
            json.dumps(json_safe(receipt), indent=2, allow_nan=False) + "\n")
        (ROOT / "out").mkdir(exist_ok=True)
        np.save(CACHE / "pred62.npy", pred)
        cand_sha = hashlib.sha256(pred.tobytes()).hexdigest()
        log["emission_sha256"] = cand_sha
        print(f"[emit] {out_tif.name} sha256={receipt['sha256'][:16]}.. "
              f"checks_passed={log['submission']['checks_passed']}", flush=True)

    # ------------------------------------------------------- uniqueness gate
    # Last, deliberately: it re-reads every accessible registry raster (tens of
    # minutes) and must never be able to cost the run its artifact.
    if args.emit and not args.skip_uniqueness:
        surface = fld.evidence if fld is not None else np.zeros(g.footprint.shape)
        inv = json.loads((REGISTRY / "index.json").read_text())
        log["uniqueness_started_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rep_s = uniqueness.compare_array_to_registry(surface, inv, g.footprint)
        rep_d = uniqueness.compare_array_to_registry(dots.astype(np.float32), inv, g.footprint)
        registry_report = dict(candidate_sha256=cand_sha,
                               candidate=str(ROOT / "docs/downloads" / args.name),
                               surface=rep_s, dots=rep_d)
        (ROOT / "evidence").mkdir(exist_ok=True)
        (ROOT / "evidence/uniqueness.json").write_text(json.dumps(
            json_safe(registry_report), indent=2, allow_nan=False) + "\n")
        log["uniqueness"] = dict(
            surface=dict(verdict=rep_s["verdict"], n=rep_s["inventory"]["raster_count"],
                         worst_rho=rep_s["worst_spearman"], worst_overlap=rep_s["worst_overlap"],
                         errors=rep_s["inventory"]["error_count"]),
            dots=dict(verdict=rep_d["verdict"], n=rep_d["inventory"]["raster_count"],
                      worst_rho=rep_d["worst_spearman"], worst_overlap=rep_d["worst_overlap"],
                      errors=rep_d["inventory"]["error_count"]))
        print("[uniq] surface", rep_s["verdict"], rep_s["worst_spearman"], rep_s["worst_overlap"], flush=True)
        print("[uniq] dots   ", rep_d["verdict"], rep_d["worst_spearman"], rep_d["worst_overlap"], flush=True)
        del surface, rep_s, rep_d
    elif args.emit:
        log["uniqueness"] = dict(skipped=True, reason="--skip-uniqueness")
        print("[uniq] skipped (--skip-uniqueness); evidence/uniqueness.json unchanged",
              flush=True)


    log["runtime_s"] = round(time.time() - t0, 1)
    log["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(json_safe(log), indent=2, allow_nan=False) + "\n")
    print(f"[done] {log['runtime_s']} s -> {args.out}", flush=True)
    return 0


def json_safe(v):
    if isinstance(v, dict):
        return {str(k): json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, Path):
        return str(v)
    return v


if __name__ == "__main__":
    raise SystemExit(main())
