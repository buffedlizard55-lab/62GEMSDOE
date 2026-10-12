"""Score-prediction test for the SGMC-off-catalogue truth proxy.

Question the whole project turns on: does the exact published metric, evaluated with
the SGMC 1:750k faults *minus the published catalogue* as the truth, reproduce the
owner-reported leaderboard scores of the group's own submissions?

If yes, the proxy is a calibrated optimizer target and "beat 0.2778" becomes a
well-posed search problem.  If no, every number derived from it (including this
repo's earlier "credit enrichment" tables) has to be labelled an uncalibrated
ordinal screen and never used as a promotion gate.

Usage:
    python3 scripts/proxy_dti_regression.py --registry /tmp/registry \
        --measurements research/registry_measurements.json \
        --out research/proxy_dti_regression.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid  # noqa: E402
from gems62.metric import dti_binary  # noqa: E402


def load_rows(path: Path) -> list[dict]:
    rows = json.load(open(path))
    out = []
    for r in rows:
        if r.get("score") is None:
            continue
        base = r["base"].rstrip(".")
        if "__" in base:                     # the dumps carry the repo prefix
            base = base.split("__", 1)[1]
        out.append({"repo": r["repo"], "base": base, "score": float(r["score"]),
                    "mass_json": r.get("mass"), "dcat_med": r.get("dcat_med")})
    return out


def match(fname: str, rows: list[dict]) -> dict | None:
    """Registry dump names files REPO__base.tif; the measurements list is truncated."""
    repo, _, rest = fname.partition("__")
    best = None
    for r in rows:
        if r["repo"] != repo:
            continue
        if rest.startswith(r["base"]) or r["base"].startswith(rest):
            if best is None or len(r["base"]) > len(best["base"]):
                best = r
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="/tmp/registry")
    ap.add_argument("--measurements", default="research/registry_measurements.json")
    ap.add_argument("--out", default="research/proxy_dti_regression.json")
    ap.add_argument("--max-files", type=int, default=0)
    args = ap.parse_args()

    labels = grid.read_labels(ROOT / "data/labels.tif")
    foot = labels != -1
    cat = labels == 1
    with rasterio.open(ROOT / "build/ext/derived_sgmc_faults_100m.tif") as s:
        sgmc = s.read(1) > 0
    off = sgmc & ~cat
    active = foot & ~cat                      # organizer masks known faults out
    print(f"[proxy] footprint {int(foot.sum()):,}  catalogue {int(cat.sum()):,}  "
          f"sgmc_off_cat {int(off.sum()):,}  active {int(active.sum()):,}")

    rows = load_rows(ROOT / args.measurements)
    files = sorted(Path(args.registry).glob("*.tif"))
    if args.max_files:
        files = files[: args.max_files]

    out = []
    for f in files:
        r = match(f.name, rows)
        if r is None:
            continue
        try:
            with rasterio.open(f) as s:
                arr = s.read(1)
        except Exception as e:                                  # noqa: BLE001
            print(f"  SKIP {f.name}: {e}")
            continue
        pred = np.nan_to_num(arr.astype(np.float64)) > 0
        if pred.sum() == 0:
            continue
        if pred.sum() != int(r.get("mass_json") or pred.sum()):
            pass  # count mismatch is itself informative; record both
        m = int(pred.sum())
        print(f"  {r['repo']:12s} n={m:7,d} score={r['score']:.4f}  {f.name[:58]}")
        yy, xx = np.nonzero(pred)
        # nearest-neighbour spacing (px -> m)
        order = np.argsort(yy * 10000 + xx)
        pts = np.c_[yy[order], xx[order]]
        tree = ndi
        from scipy.spatial import cKDTree
        kd = cKDTree(pts)
        dd, _ = kd.query(pts, k=2)
        nn = dd[:, 1] * 100.0
        d = dti_binary(pred, off, active=active)
        out.append({
            "repo": r["repo"], "file": f.name, "reported_score": r["score"],
            "mass": m, "mass_json": r.get("mass_json"),
            "nn_med_m": float(np.median(nn)), "frac_nn_lt300": float((nn < 300).mean()),
            "proxy_tp": d["tp"], "proxy_fp": d["fp"], "proxy_fn": d["fn"],
            "proxy_dti": d["dti"], "proxy_truth_cells": d["n_truth"],
            "proxy_credit_per_dot": d["tp"] / max(m, 1),
        })
        print(f"      proxy TP={d['tp']:9.1f} FP={d['fp']:9.1f} FN={d['fn']:9.1f} "
              f"DTI={d['dti']:.4f}  (reported {r['score']:.4f})  nn_med={np.median(nn):.0f} m")

    Path(ROOT / args.out).write_text(json.dumps(out, indent=1))
    if len(out) >= 3:
        import math
        sc = np.array([o["reported_score"] for o in out])
        pr = np.array([o["proxy_dti"] for o in out])
        cr = np.array([o["proxy_credit_per_dot"] for o in out])
        def spearman(a, b):
            ra = np.argsort(np.argsort(a)).astype(float)
            rb = np.argsort(np.argsort(b)).astype(float)
            return float(np.corrcoef(ra, rb)[0, 1])
        print(f"\n[proxy] n={len(out)}  Spearman(proxy_dti, score) = {spearman(pr, sc):+.3f}"
              f"   Spearman(credit_per_dot, score) = {spearman(cr, sc):+.3f}")
        for o in sorted(out, key=lambda o: -o["proxy_dti"]):
            print(f"   proxy {o['proxy_dti']:.4f}  reported {o['reported_score']:.4f}  "
                  f"n={o['mass']:7,d}  {o['repo']:12s} {o['file'][:52]}")
    print(f"[proxy] wrote {args.out} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
