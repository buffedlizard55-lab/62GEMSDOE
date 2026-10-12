#!/usr/bin/env python3
"""H63M — is the 3-px lane-drift tripwire satisfiable against these registry rasters?

The parallel-run protocol says: *"if more than 70 % of your dots fall within 3 px of one
registry raster's dots you have drifted into another lane"*.  That test is only meaningful
if a **random** emission would score materially lower.  For a raster that blankets 4-5 %
of the footprint with 200 k+ positives, the 300 m kernel (28 cells) contains on average
more than one of its dots anywhere, so a random field already fails the test.

This script measures that null: for every registry raster, the fraction of a random
off-catalogue dot field (same mass, same off-catalogue domain as the shipped file) that
falls within 3 px of it, and the same fraction for the shipped file.  The ratio is the
number that decides whether the overlap is evidence of copying or an artefact of the
registry raster's density.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
REG = HERE / "data" / "registry"
RASTER = HERE / "lane62-h63m/docs/downloads/gems62-h63m-multiline-corroborated-90000-zeros.tif"
MASS = 90_000
OFFCAT_M = 300


def frac_within(mine_rr, mine_cc, other_pos):
    d = ndi.distance_transform_edt(~other_pos)
    return float((d[mine_rr, mine_cc] <= 3.0).mean())


def main() -> int:
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    dcat = (ndi.distance_transform_edt(~cat) * PIXEL_M).astype(np.float32)
    offcat = usable & (dcat >= OFFCAT_M)
    flat = np.flatnonzero(offcat.ravel())

    with rasterio.open(RASTER) as s:
        a = s.read(1)
    mr, mc = np.nonzero(a > 0)

    rng = np.random.default_rng(20261012)
    rows = []
    for p in sorted(REG.glob("*.tif")):
        with rasterio.open(p) as s:
            o = s.read(1)
        op = np.isfinite(o) & (o > 0)
        n = int(op.sum())
        random_fracs = []
        for _ in range(3):
            sel = flat[rng.choice(flat.size, size=MASS, replace=False)]
            rr, cc = np.unravel_index(sel, (HEIGHT, WIDTH))
            random_fracs.append(frac_within(rr, cc, op))
        mine = frac_within(mr, mc, op)
        rf = float(np.mean(random_fracs))
        rows.append(dict(registry=p.name, n_theirs=n,
                         density_frac=round(n / float(usable.sum()), 4),
                         random_frac_within_3px=round(rf, 4),
                         mine_frac_within_3px=round(mine, 4),
                         lift=round(mine / rf, 3) if rf else None,
                         test_satisfiable=bool(rf < 0.70)))
    res = {
        "generated_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "evidence_class": "MEASURED (random control, 3 draws, identical mass and domain)",
        "question": "for which registry rasters can the protocol's 70 % overlap tripwire "
                    "distinguish a copy from a random emission?",
        "rows": rows,
    }
    (HERE / "evidence" / "h63_uniqueness_control.json").write_text(json.dumps(res, indent=1))
    print("%-40s %9s %8s %9s %9s %6s %s" % ("registry", "n_theirs", "density", "random", "mine",
                                            "lift", "satisfiable"))
    for r in sorted(rows, key=lambda d: -d["mine_frac_within_3px"]):
        print("%-40s %9d %8.4f %9.3f %9.3f %6s %s" % (
            r["registry"][:38], r["n_theirs"], r["density_frac"], r["random_frac_within_3px"],
            r["mine_frac_within_3px"], r["lift"], r["test_satisfiable"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
