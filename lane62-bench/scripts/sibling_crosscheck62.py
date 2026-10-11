"""How much does this lane agree with the *other* Lahontan lanes in this repo?

``uniqueness_gate62.py`` answers a narrow question -- "is this a copy of a sibling
raster?" -- and its answer is no.  That is not the interesting question for a trunk
that now holds three independent attempts at the same science (``lane62``,
``lane62-h62a``, and the trunk's own ``src/gems62/lahontan.py`` + ``datum.py``).
The interesting question is whether they *find the same places*: lanes that agree are
one idea wearing two implementations, lanes that disagree are two chances at the
truth, and only the disagreeing pair can be unioned for score.

So compare my emission (binary dots) against every submission raster in the repo:
  support_n           positive pixels inside the footprint
  near_frac           share of my dots within 3 px (300 m) of the sibling's support
  overlap_frac        share of the sibling's support within 3 px of my dots
  iou_3px             intersection/union of the two 3-px-dilated supports
  spearman            rank correlation of the two float32 arrays, 4-px strided

A high ``near_frac`` at low ``support_n`` means the sibling is a *subset* of my lane
-- the usual relationship when one lane is a coarser version of another.  A high
symmetric overlap means one of the two is redundant.  Both are worth knowing before
anyone proposes blending, and neither is a claim about which is better: the holdout
cannot rank lanes that never read the catalogue (see README).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
REPO = ROOT.parent
from gems62_bench import grid as gd_mod  # noqa: E402

MINE = ROOT / "docs/downloads/gems62-lahontan-datumstep-min12max60-seed25-traceonly.tif"
SIB_GLOBS = ("docs/downloads/*.tif", "lane62/docs/downloads/*.tif",
             "lane62-h62a/docs/downloads/*.tif")
STRIDE, NEAR = 4, 3
# The tread-habitat mask is a cached product of run_lane62.py (field key
# 8cb1391bcc519270), not a repo file; when it is absent the null falls back to the
# footprint pool alone and says so.  The footprint pool understates chance
# agreement, because it scatters dots into terrain no bench lane can emit in.
HABITAT = Path("/home/user/datacache/lahontan62_habitat.npy")


def read(path: Path):
    with rasterio.open(path) as s:
        a = s.read(1).astype(np.float32)
    a = np.where(np.isfinite(a) & (a > 0), a, np.float32(0.0))
    return a


def main() -> int:
    g = gd_mod.load_grid()
    fp = g.footprint.astype(bool)
    mine = read(MINE)
    my_sup = (mine > 0) & fp
    my_d = ndi.binary_dilation(my_sup, ndi.generate_binary_structure(2, 2), iterations=NEAR)
    rows = []
    for pat in SIB_GLOBS:
        for p in sorted(REPO.glob(pat)):
            if p.resolve() == MINE.resolve():
                continue
            try:
                a = read(p)
            except Exception as exc:                       # unreadable / wrong grid
                rows.append(dict(raster=str(p.relative_to(REPO)), error=str(exc)[:120]))
                continue
            if a.shape != my_sup.shape:
                rows.append(dict(raster=str(p.relative_to(REPO)), error=f"shape {a.shape}"))
                continue
            sup = (a > 0) & fp
            n = int(sup.sum())
            if n == 0:
                rows.append(dict(raster=str(p.relative_to(REPO)), support_n=0,
                                 note="zero-filled / demonstration artifact"))
                continue
            sd = ndi.binary_dilation(sup, ndi.generate_binary_structure(2, 2), iterations=NEAR)
            inter, union = int((my_d & sd).sum()), int((my_d | sd).sum())
            sm, smy = a[::STRIDE, ::STRIDE], mine[::STRIDE, ::STRIDE]
            rho = spearmanr(sm.ravel(), smy.ravel()).statistic
            rows.append(dict(
                raster=str(p.relative_to(REPO)), support_n=n,
                near_frac=round(float((my_sup & sd).sum() / my_sup.sum()), 4),
                overlap_frac=round(float((sup & my_d).sum() / n), 4),
                iou_3px=round(float(inter / max(1, union)), 4),
                spearman=round(float(rho) if np.isfinite(rho) else 0.0, 4)))
    pools = {"footprint": fp}
    if HABITAT.exists():
        pools["habitat_and_footprint"] = (np.load(HABITAT) > 0) & fp
    rng = np.random.default_rng(62)
    n = int(my_sup.sum())
    null_rows = {}
    for r in rows:
        rel = r.get("raster")
        if not rel or "support_n" not in r or r.get("support_n", 0) < 5000:
            continue                     # chance level is meaningless for demo artifacts
        sib = read(REPO / rel)
        sd = ndi.binary_dilation((sib > 0) & fp, ndi.generate_binary_structure(2, 2),
                                 iterations=NEAR)
        row = dict(observed_near_frac=r["near_frac"])
        for pname, pool in pools.items():
            idx = np.flatnonzero(pool.ravel())
            draws = [float(sd.ravel()[rng.choice(idx, size=min(n, idx.size),
                                                  replace=False)].mean()) for _ in range(5)]
            row["null_" + pname] = dict(mean=round(float(np.mean(draws)), 4),
                                        sd=round(float(np.std(draws)), 4), draws=5,
                                        pool_px=int(idx.size),
                                        enrichment=round(r["near_frac"] / float(np.mean(draws)), 2))
        null_rows[rel] = row
    out = dict(mine=str(MINE.relative_to(REPO)), my_support_n=n,
               near_radius_px=NEAR, stride_px=STRIDE, rows=rows,
               null_test=dict(
                   question=("near_frac is directional and grows with the sibling's "
                             "support area, so 0.68 is not evidence of agreement "
                             "without a chance level: how much of this lane's support "
                             "falls within 300 m of the sibling's, for dot sets of the "
                             "same size drawn from the same pools?"),
                   note=("habitat_and_footprint is the fair pool (this lane can only "
                         "emit on tread habitat); footprint is permissive and "
                         "understates chance, so it inflates the enrichment."),
                   pools=tuple(pools), rows=null_rows))
    (ROOT / "evidence/sibling_crosscheck62.json").write_text(json.dumps(out, indent=1) + "\n")
    for r in rows:
        print(" ".join(f"{k}={v}" for k, v in r.items() if k != "raster"), "|", r["raster"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
