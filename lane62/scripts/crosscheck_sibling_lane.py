#!/usr/bin/env python3
"""Compare this lane's candidate TIFs with the sibling datum-offset lane that already
lives at the repository root (merged to main independently, same assigned lane).

The 508-raster registry used by uniqueness_gate.py was built from the group's other
public repositories and therefore never contained this repository's own files.  Now
that main carries a v8 datum-offset TIF and two 99-dot variants of the same lane, the
protocol's duplicate test is re-run against them: if our dots sit inside the sibling's
3 px dilation, or if the two fields are rank-correlated, this lane is a duplicate of a
lane that is already shipped and must say so.

Same conventions as uniqueness_gate.py: positivity is `value > 0`, "within 3 px" is
scipy.ndimage.binary_dilation(iterations=3), effective coverage is the dilated mask
intersected with the competition footprint, and the rank correlation is sampled from
the footprint (never from one file's own positives).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]            # lane62/
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G                          # noqa: E402

MINE = [ROOT / "docs/downloads/gems62-lahontan-datum-break-dotted-primary-zeros.tif",
        ROOT / "docs/downloads/gems62-lahontan-flagged-breaks-selective-secondary-zeros.tif"]
THEIRS = [REPO / "docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif",
          REPO / "docs/downloads/gems62-lahontan-isobase-99dots-zeros.tif",
          REPO / "docs/downloads/gems62-lahontan-isobase-99dots-nan.tif"]

OV_LIMIT, RHO_LIMIT, DISC = 0.70, 0.90, 0.50


def mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as d:
        a = np.asarray(d.read(1), dtype=np.float32)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    return a > 0


def main() -> int:
    g = G.load_grid(ROOT)
    fp = int(g.footprint.sum())
    h, w = g.footprint.shape
    fpi = np.flatnonzero(g.footprint.ravel())
    rng = np.random.default_rng(3)
    sample = rng.choice(fpi, min(200_000, fpi.size), replace=False)
    s_r, s_c = np.divmod(sample, w)

    out = {"generated_by": "lane62/scripts/crosscheck_sibling_lane.py",
           "convention": "positivity = value>0; 3 px = binary_dilation(iterations=3); "
                         "effective coverage vs the competition footprint",
           "targets": [str(p.relative_to(REPO)) for p in THEIRS], "pairs": []}
    for mine_p in MINE:
        mine = mask(mine_p)
        rr, cc = np.nonzero(mine)
        n_mine = int(rr.size)
        for their_p in THEIRS:
            if not their_p.exists():
                continue
            theirs = mask(their_p)
            n_theirs = int(theirs.sum())
            eff = float((ndi.binary_dilation(theirs, iterations=3) & g.footprint).sum()) / fp
            ov = float(ndi.binary_dilation(theirs, iterations=3)[rr, cc].mean()) if n_mine else 0.0
            inter = int((theirs & mine).sum())
            union = n_mine + n_theirs - inter
            rho, meth = float("nan"), None
            x, y = mine[s_r, s_c], theirs[s_r, s_c]
            if np.unique(x).size > 1 and np.unique(y).size > 1:
                rho, meth = float(spearmanr(x, y).statistic), "spearman"
            elif x.std() > 0 and y.std() > 0:
                rho, meth = float(np.corrcoef(x, y)[0, 1]), "point_biserial"
            discriminating = bool(eff <= DISC)
            dup = bool((discriminating and ov > OV_LIMIT) or
                       (np.isfinite(rho) and abs(rho) > RHO_LIMIT))
            row = dict(mine=mine_p.name, theirs=their_p.name,
                       n_positive_mine=n_mine, n_positive_theirs=n_theirs,
                       coverage_theirs=n_theirs / fp,
                       effective_coverage_theirs=eff, discriminating=discriminating,
                       overlap_3px_one_sided=ov,
                       exact_overlap_fraction_of_mine=inter / n_mine if n_mine else 0.0,
                       jaccard=inter / union if union else 0.0,
                       spearman=rho, spearman_method=meth,
                       duplicate_under_protocol=dup)
            out["pairs"].append(row)
            print(f"{mine_p.name[:52]:52s} vs {their_p.name[:44]:44s} "
                  f"ov3px={ov:.4f} exact={row['exact_overlap_fraction_of_mine']:.4f} "
                  f"rho={rho if not isinstance(rho,float) or np.isfinite(rho) else float('nan'):+.4f} "
                  f"eff={eff:.3f} -> {'DUPLICATE' if dup else 'distinct'}")
    (ROOT / "evidence/crosscheck_sibling_lane.json").write_text(json.dumps(out, indent=1) + "\n")
    print("wrote evidence/crosscheck_sibling_lane.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
