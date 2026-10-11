#!/usr/bin/env python3
"""Cache the lane's catalogue-free habitat pool so the uniqueness gate can use it
as a null without holding the 19-band feature stack in memory.

Why this exists: running `isobase.build_surfaces()` and then the 709-comparator
gate in one process needs ~2.3 GB and gets OOM-killed on a 3.9 GB box
(observed, dmesg: "Out of memory: Killed process ... anon-rss:2322424kB"). The
pool is 271,102 pixels -- 2.2 MB of indices -- so computing it once and caching
it removes the entire feature stack from the gate's address space.

The pool is deliberately CATALOGUE-FREE: bench pixels whose isobase residual sits
in the bounded throw window [15,130) m. It is derived only from det_elev, its
slope and the fitted isobase, so using it as a null cannot beg the question
against comparators that were themselves built from the fault catalogue.

    GEMS62_DATA=... python scripts/make_habitat_pool.py
    GEMS62_DATA=... python scripts/make_habitat_pool.py --out /path/pool.npz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid, isobase                                       # noqa: E402

DEFAULT_OUT = Path.home() / ".cache/gems62/habitat_pool.npz"
THROW_LO_M, THROW_HI_M = 15.0, 130.0


def build_pool() -> tuple[np.ndarray, np.ndarray, dict]:
    stack = grid.load_stack(verify=False)
    fp = stack.footprint
    surf = isobase.build_surfaces(stack.features, fp)
    med = float(np.nanmedian(surf.resid[surf.bench]))
    ares = np.abs(surf.resid - med)
    pool = surf.bench & (ares >= THROW_LO_M) & (ares < THROW_HI_M) & fp
    info = dict(
        n_footprint=int(fp.sum()), n_bench=int(surf.bench.sum()),
        n_pool=int(pool.sum()), resid_median_m=med,
        throw_lo_m=THROW_LO_M, throw_hi_m=THROW_HI_M,
        definition=("bench & |isobase residual - median| in [15,130) m & footprint; "
                    "CATALOGUE-FREE by construction"),
    )
    # free the stack before returning: the caller only needs the two masks
    del stack, surf
    return pool, fp, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    pool, fp, info = build_pool()
    py, px = np.nonzero(pool)
    np.savez_compressed(
        out,
        pool_y=py.astype(np.int32), pool_x=px.astype(np.int32),
        footprint_packed=np.packbits(fp.ravel()),
        shape=np.array(fp.shape, np.int32),
    )
    info["out"] = str(out)
    info["bytes"] = out.stat().st_size
    info["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    info["elapsed_seconds"] = round(time.time() - t0, 1)
    (HERE / "evidence" / "e7c_habitat_pool.json").write_text(
        json.dumps(info, indent=2) + "\n")
    print(f"[pool] {info['n_pool']:,} px of {info['n_footprint']:,} footprint "
          f"({100*info['n_pool']/info['n_footprint']:.2f}%)")
    print(f"[pool] bench {info['n_bench']:,} px; residual median {med_fmt(info['resid_median_m'])}")
    print(f"[pool] wrote {out} ({info['bytes']:,} B) in {info['elapsed_seconds']}s")
    return 0


def med_fmt(v: float) -> str:
    return f"{v:+.3f} m"


if __name__ == "__main__":
    raise SystemExit(main())
