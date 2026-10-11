#!/usr/bin/env python3
"""Run the literal-copy uniqueness protocol against the registry cache.

Split out of ``run_lane62.py`` because it re-reads every accessible competition
raster (753 files here, ~550 MB) and took ~50 minutes -- long enough that a
validation failure in a later step used to cost the whole run its artifact.  The
emission is deterministic, so the gate is now run *after* the submission exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62_bench import grid as gd_mod                        # noqa: E402
from gems62_bench import uniqueness                            # noqa: E402

CACHE = Path("/home/user/datacache")
REGISTRY = CACHE / "registry"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", default=str(CACHE / "pred62.npy"))
    ap.add_argument("--surface", default=str(CACHE / "evidence62.npy"))
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/uniqueness.json")
    args = ap.parse_args()

    g = gd_mod.load_grid()
    pred = np.load(args.pred).astype(np.float32)
    # the protocol treats any non-finite value inside the footprint as an invalid
    # candidate; the evidence surface is a continuous field, so NaN outside the
    # DEM coverage is zeroed rather than dropping the check
    surf = np.nan_to_num(np.load(args.surface).astype(np.float32), nan=0.0)
    inv = json.loads((REGISTRY / "index.json").read_text())
    print(f"[inv] {len(inv.get('rasters', []))} rasters, scope_complete="
          f"{inv.get('declared_scope_complete')}, errors={len(inv.get('errors', []))}",
          flush=True)
    t0 = datetime.now(timezone.utc)
    prog = lambda i, n, row: print(f"[inv] {i}/{n} {row.get('file','')[:40]}", flush=True) \
        if i % 150 == 0 else None
    rep_p = uniqueness.compare_array_to_registry(pred, inv, g.footprint, progress=prog)
    print(f"[uniq] emission  {rep_p['verdict']} rho={rep_p['worst_spearman']} "
          f"overlap={rep_p['worst_overlap']}", flush=True)
    rep_s = uniqueness.compare_array_to_registry(surf, inv, g.footprint, progress=prog)
    print(f"[uniq] surface   {rep_s['verdict']} rho={rep_s['worst_spearman']} "
          f"overlap={rep_s['worst_overlap']}", flush=True)
    report = dict(candidate_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),
                  surface_sha256=hashlib.sha256(surf.tobytes()).hexdigest(),
                  started_utc=t0.isoformat(timespec="seconds"),
                  runtime_s=round((datetime.now(timezone.utc) - t0).total_seconds(), 1),
                  emission=rep_p, evidence_surface=rep_s)
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(json.dumps(report, indent=1, default=float, allow_nan=False) + "\n")
    summary = dict(verdict_emission=rep_p["verdict"], verdict_surface=rep_s["verdict"],
                   n_rasters=rep_p["inventory"]["raster_count"],
                   errors=rep_p["inventory"]["error_count"],
                   worst_spearman=max(float(rep_p["worst_spearman"] or 0.0),
                                      float(rep_s["worst_spearman"] or 0.0)),
                   worst_overlap=max(float(rep_p["worst_overlap"] or 0.0),
                                     float(rep_s["worst_overlap"] or 0.0)),
                   candidate_sha256=report["candidate_sha256"],
                   runtime_s=report["runtime_s"])
    (args.out.parent / "uniqueness_summary.json").write_text(
        json.dumps(summary, indent=1) + "\n")
    print(f"[done] {summary['n_rasters']} rasters, {summary['errors']} errors -> {args.out}",
          flush=True)
    return 0 if rep_p["verdict"] == "pass" and rep_s["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
