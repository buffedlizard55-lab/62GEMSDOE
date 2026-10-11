#!/usr/bin/env python3
"""Does the Lahontan datum-offset lane add anything on top of a sibling emission?

Everything measured here is a *holdout* number: the hidden segments are part of
the contest catalogue, so a lane that re-derives the catalogue scores well on it
and the lane that finds independent geomorphic evidence scores poorly.  That
asymmetry is the point of the exercise -- it prices how much a new signal is
worth before spending a submission slot on it.

For each candidate emission raster (the sibling lanes' emitted rasters and this
lane's dots) the script reports pooled DTI on the segmented holdout, then prices
three ways of combining the best sibling with this lane:

  union          keep both emissions
  veto           keep sibling pixels only where the bench habitat allows it
  weight         rank the sibling's own emission by 'is this dot on a bench that
                 carries a measured datum step', reported as an AUC against the
                 hidden truth so the sign of the effect is visible

Usage:  python scripts/blend_eval62.py [--sibling GLOB ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62_bench import grid as gd_mod                       # noqa: E402
from gems62_bench import holdout_segmented as hs               # noqa: E402
from gems62_bench import lahontan                              # noqa: E402

CACHE = Path("/home/user/datacache")
G61 = Path("/tmp/gems61")
SIB_GLOBS = ["docs/downloads/*.tif", "docs/submissions/*.tif",
             "data/external/*faults*.tif"]


def load_mask(path: Path, shape) -> np.ndarray | None:
    """Read a candidate raster as a boolean emission mask on the contest grid."""
    try:
        with rasterio.open(path) as src:
            if src.height != shape[0] or src.width != shape[1]:
                return None
            a = src.read(1)
    except Exception:                                     # pragma: no cover
        return None
    m = np.asarray(a, np.float32)
    m = np.where(np.isfinite(m), m, 0.0)
    return m > 0


def auc(score: np.ndarray, truth: np.ndarray) -> float:
    s = np.asarray(score, np.float64)
    t = np.asarray(truth, bool)
    if t.sum() == 0 or (~t).sum() == 0:
        return float("nan")
    r = rankdata(s)
    n1, n0 = int(t.sum()), int((~t).sum())
    return float((r[t].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def ctx_visible(g) -> np.ndarray:
    """The catalogue pixels the holdout keeps visible (prune reference)."""
    return g.catalogue & g.footprint


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sib", action="append", default=[], help="extra raster path")
    ap.add_argument("--top", type=int, default=6, help="blend the N best siblings")
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/blend62.json")
    args = ap.parse_args()

    g = gd_mod.load_grid()
    ctx = hs.build_holdout(g)
    fld = None
    tag = "lahontan62"
    try:
        meta = json.loads((CACHE / f"{tag}_meta.json").read_text())
        fld = lahontan.DatumField()
        for k in ("bench", "slope", "step", "step_signed", "step_azim", "gated",
                  "zone", "evidence", "habitat", "isobase", "anomaly"):
            a = np.load(CACHE / f"{tag}_{k}.npy")
            fld[k] = a.astype(bool) if k in ("bench", "zone", "habitat") else a
        fld["meta"] = meta.get("field_meta", {})
        del meta
    except Exception as e:                                # pragma: no cover
        print(f"[lane] field cache unusable ({e}); using zero evidence", flush=True)

    masks: dict[str, np.ndarray] = {}
    # This lane's emission, rebuilt in holdout mode (no pruning against the
    # catalogue: the hidden segments ARE catalogue, so pruning deletes exactly the
    # signal being measured -- the mistake that made an earlier version of this
    # script price the lane at 0.0001 instead of ~0.03).
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_lane62 as rl                                      # noqa: E402
    seeds = rl.seed_points(fld.evidence, fld.gated, fld.zone,
                           fld.meta["min_step_m"])
    em = rl.emit_dots(fld, ctx_visible(g), g.footprint, seeds=seeds, spacing=2,
                      budget=40_000, prune=False)
    mine = em["dots"] & g.footprint
    n_mine = int(mine.sum())
    res_mine = hs.evaluate(mine, ctx, cell_mode="all")
    masks["<lane62 holdout dots>"] = mine
    alt = {"zone": fld.zone & g.footprint & ~ndi.binary_dilation(g.catalogue,
                                                                  iterations=1),
           "gated>=8": (fld.gated >= fld.meta["min_step_m"]) & g.footprint}

    cands = []
    seen = set()
    for pat in (args.sib or []):
        p = Path(pat)
        if p.exists():
            cands.append(p)
            seen.add(str(p))
    if not args.sib:
        for glob in SIB_GLOBS:
            for p in sorted((G61 / glob).parent.glob(Path(glob).name)):
                if str(p) not in seen and p.is_file():
                    cands.append(p); seen.add(str(p))

    rows = []
    for p in cands:
        m = load_mask(p, g.footprint.shape)
        if m is None:
            continue
        masks[p.name] = m & g.footprint
        r = hs.evaluate(masks[p.name], ctx, cell_mode="all")
        rows.append(dict(name=str(p.relative_to(G61) if G61 in p.parents else p),
                         pixels=int(masks[p.name].sum()),
                         pooled_dti=r["pooled_dti"],
                         coverage=r["pooled_coverage"],
                         on_visible=r["on_visible_catalogue"]))
        print(f"[cand] {rows[-1]['name'][-58:]:58s} px={rows[-1]['pixels']:7d} "
              f"DTI={r['pooled_dti']:.4f} cov={r['pooled_coverage']:.4f}", flush=True)
    rows.sort(key=lambda d: -d["pooled_dti"])
    rows.insert(1, dict(name="<lane62 holdout dots>", pixels=n_mine,
                     pooled_dti=res_mine["pooled_dti"],
                     coverage=res_mine["pooled_coverage"],
                     on_visible=res_mine["on_visible_catalogue"]))
    print(f"[lane62] px={n_mine} DTI={res_mine['pooled_dti']:.4f} "
          f"cov={res_mine['pooled_coverage']:.4f}")

    for kname, km in alt.items():
        r = hs.evaluate(km, ctx, cell_mode="all")
        masks[kname] = km
        print(f"[lane-alt] {kname:10s} px={int(km.sum()):8d} DTI={r['pooled_dti']:.4f} "
              f"cov={r['pooled_coverage']:.4f}", flush=True)
        rows.append(dict(name=f"<lane62 {kname}>", pixels=int(km.sum()),
                         pooled_dti=r["pooled_dti"], coverage=r["pooled_coverage"],
                         on_visible=r["on_visible_catalogue"]))

    blends = []
    hidden = np.zeros(g.footprint.shape, bool)
    dom = np.zeros(g.footprint.shape, bool)
    for cell in ctx.cells:
        if cell.mode != "all":
            continue
        sl = cell.bbox
        h = np.zeros(cell.active.shape, bool)
        h[cell.truth_yx] = True
        hidden[sl] |= h & cell.active            # truth that is actually scored
        dom[sl] |= cell.active
    dist_hidden = ndi.distance_transform_edt(~hidden)     # px to a hidden segment
    for row in rows[:args.top]:
        name = row["name"]
        A = masks.get(Path(name).name, masks.get(name))
        if A is None or name.startswith("<lane"):
            continue
        for label, B in [("union", A | mine),
                         ("veto", A & (fld.habitat if fld is not None else A)),
                         ("add_bench_dots", A | (mine & (fld.bench if fld is not None
                                                         else mine))),
                         ("union_zone", A | alt["zone"])]:
            r = hs.evaluate(B, ctx, cell_mode="all")
            blends.append(dict(sibling=name, how=label, pixels=int(B.sum()),
                               pooled_dti=r["pooled_dti"],
                               coverage=r["pooled_coverage"],
                               delta=r["pooled_dti"] - row["pooled_dti"]))
            print(f"[blend] {label:15s} {name[-40:]:40s} px={int(B.sum()):7d} "
                  f"DTI={r['pooled_dti']:.4f} delta={blends[-1]['delta']:+.4f}",
                  flush=True)
        # does the geomorphic lane rank the sibling's own pixels?
        if fld is not None:
            px = A & dom
            if px.any():
                istrue = px & (dist_hidden <= 2.0)              # within 200 m of a
                # hidden segment -- i.e. a pixel the metric would actually reward
                a_hab = auc(fld.evidence[px], istrue[px])
                a_bench = auc(fld.bench[px].astype(float), istrue[px])
                frac_in = float((istrue & ndi.binary_dilation(fld.bench, iterations=2)
                                 ).sum() / max(istrue.sum(), 1))
                frac_out = float(((~istrue) & ndi.binary_dilation(fld.bench,
                                        iterations=2)).sum() / max(int((~istrue).sum()), 1))
            else:
                a_hab = a_bench = frac_in = frac_out = float("nan")
            blends.append(dict(sibling=name, how="auc_evidence_vs_hidden",
                               pixels=int(A.sum()), pooled_dti=None,
                               coverage=None, delta=a_hab, auc_bench=a_bench,
                               true_frac_on_bench=frac_in, all_frac_on_bench=frac_out))
            print(f"[auc]   evidence {a_hab:.4f} / bench {a_bench:.4f} "
                  f"(0.5 = no information); hidden-true pixels on a bench "
                  f"{frac_in:.3f} vs all pixels {frac_out:.3f}", flush=True)
    del dom

    out = dict(baseline_lane62=dict(pooled_dti=res_mine["pooled_dti"],
                                    coverage=res_mine["pooled_coverage"],
                                    pixels=n_mine),
               candidates=rows, blends=blends)
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(json.dumps(out, indent=1, default=float))
    print(f"[done] -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
