#!/usr/bin/env python3
"""Re-run the uniqueness gate on an already-written artifact and patch the run
card, without re-running the whole lane.

Used when the gate itself changes (IR-62-UNIQ-01: the overlap leg is degenerate
against regular-lattice and near-blanket comparators, so it is now applied only
where a random dot set would fail it).  The artifact bytes are NOT touched --
this reads them from disk, so the sha256 in the run card stays true.

    python scripts/recheck_uniqueness.py
    python scripts/recheck_uniqueness.py --tif docs/downloads/<name>-zeros.tif
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import uniqueness                                          # noqa: E402
from gems62.grid import sha256_file                                    # noqa: E402

POOL = Path.home() / ".cache/gems62/habitat_pool.npz"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tif", default=None)
    ap.add_argument("--registry", default=str(Path.home() / ".cache/gems62/registry/rasters"))
    ap.add_argument("--ev", default=str(HERE / "evidence"))
    args = ap.parse_args()

    ev = Path(args.ev)
    if args.tif:
        tif = Path(args.tif)
    else:
        cands = sorted((HERE / "docs" / "downloads").glob("*-zeros.tif"))
        if not cands:
            print("no artifact found; run scripts/run_lane.py first", file=sys.stderr)
            return 2
        tif = cands[-1]
    print(f"[uniq] artifact {tif}")
    print(f"[uniq] sha256 {sha256_file(tif)}")

    # The 19-band feature stack is ~934 MB and build_surfaces() adds ~1.3 GB of
    # float64 temporaries; running that and the 709-comparator gate in one
    # process is OOM-killed on a 3.9 GB box. So the footprint and the lane's
    # habitat pool are read from the cache written by scripts/make_habitat_pool.py
    # and the stack is never loaded here.
    if not POOL.is_file():
        print(f"[uniq] FATAL {POOL} missing; run scripts/make_habitat_pool.py first",
              file=sys.stderr)
        return 2
    z = np.load(POOL)
    shape = tuple(int(v) for v in z["shape"])
    fp = np.unpackbits(z["footprint_packed"])[: shape[0] * shape[1]].reshape(shape).astype(bool)
    habitat = np.zeros(shape, bool)
    habitat[z["pool_y"], z["pool_x"]] = True
    print(f"[uniq] footprint {int(fp.sum()):,} px; habitat pool {int(habitat.sum()):,} px")

    with rasterio.open(tif) as s:
        vals = s.read(1).astype(np.float64)
    if vals.shape != fp.shape:
        print(f"[uniq] FATAL shape {vals.shape} != {fp.shape}", file=sys.stderr)
        return 2

    print(f"[uniq] habitat null pool {int(habitat.sum()):,} px (catalogue-free); "
          f"{100*float(habitat[vals > 0].mean()):.1f}% of our dots lie in it")

    t0 = time.time()
    rep = uniqueness.check_uniqueness(vals, Path(args.registry), footprint=fp,
                                      habitat=habitat)
    rep["habitat_pool_pixels"] = int(habitat.sum())
    rep["habitat_pool_definition"] = ("bench & |isobase residual - median| in [15,130) m "
                                      "& footprint; catalogue-free by construction")
    rep["artifact"] = str(tif)
    rep["artifact_sha256"] = sha256_file(tif)
    rep["elapsed_seconds"] = round(time.time() - t0, 1)
    uniqueness.save(rep, ev / "e7_uniqueness.json")

    print(f"[uniq] {rep['n_registry']} comparators in {rep['elapsed_seconds']}s")
    print(f"[uniq] verdict              {rep['verdict']}")
    print(f"[uniq] verdict strict-literal {rep['verdict_strict_literal']}")
    print(f"[uniq] worst signed rho      {rep['worst_rho_surface']['value']:+.4f} "
          f"(limit {rep['rho_limit']}) <- {rep['worst_rho_surface']['name']}")
    print(f"[uniq] worst |rho|           {rep['worst_abs_rho_surface']['value']:+.4f} "
          f"<- {rep['worst_abs_rho_surface']['name']}")
    print(f"[uniq] worst 3px overlap     {rep['worst_overlap_3px']['value']:.4f} "
          f"(limit {rep['overlap_limit']}) <- {rep['worst_overlap_3px']['name']}")
    print(f"[uniq] worst INFORMATIVE 3px {rep['worst_overlap_3px_informative']['value']:.4f} "
          f"<- {rep['worst_overlap_3px_informative']['name']}")
    print(f"[uniq] worst excess-above-chance "
          f"{rep['worst_overlap_excess']['value']:.4f} <- {rep['worst_overlap_excess']['name']}")
    print(f"[uniq] worst jaccard         {rep['worst_jaccard']['value']:.4f} "
          f"(limit {rep['jaccard_limit']}) <- {rep['worst_jaccard']['name']}")
    print(f"[uniq] over the overlap limit: {rep['n_comparators_over_overlap_limit']} "
          f"(degenerate {rep['n_comparators_over_limit_and_degenerate']}, "
          f"informative {rep['n_comparators_over_limit_and_informative']})")

    # ---- patch the run card in place; the artifact bytes are untouched
    card_path = ev / "e8_run_card.json"
    if card_path.is_file():
        card = json.loads(card_path.read_text())
        card["correlation_and_overlap_vs_registry"] = dict(
            verdict=rep["verdict"],
            verdict_strict_literal=rep["verdict_strict_literal"],
            n_registry=rep["n_registry"],
            worst_rho_surface=rep["worst_rho_surface"],
            worst_abs_rho_surface=rep["worst_abs_rho_surface"],
            worst_overlap_one_sided_3px=rep["worst_overlap_3px"],
            worst_overlap_one_sided_3px_informative=rep["worst_overlap_3px_informative"],
            worst_overlap_excess_above_chance=rep["worst_overlap_excess"],
            worst_jaccard=rep["worst_jaccard"],
            n_over_overlap_limit=rep["n_comparators_over_overlap_limit"],
            n_over_limit_degenerate=rep["n_comparators_over_limit_and_degenerate"],
            n_over_limit_informative=rep["n_comparators_over_limit_and_informative"],
            n_overlap_degenerate_comparators=rep["n_overlap_degenerate_comparators"],
            limits=dict(rho=rep["rho_limit"], overlap=rep["overlap_limit"],
                        jaccard=rep["jaccard_limit"]),
            degeneracy_note=rep["degeneracy_note"],
        )
        # recompute the verdict with the corrected gate
        hold = card.get("holdout", {})
        beats = bool(hold.get("beats_random_lines"))
        ok_fmt = bool(card.get("validator", {}).get("ok"))
        unique = rep["verdict"] == "UNIQUE"
        card["verdict"] = "promote" if (ok_fmt and beats and unique) else "negative"
        reasons = []
        if not ok_fmt:
            reasons.append("format validation failed")
        if not beats:
            reasons.append(f"holdout DTI {hold.get('pooled_dti')} does not beat random lines "
                           f"{(hold.get('controls_mean') or {}).get('random_lines')}")
        if not unique:
            reasons.append(f"uniqueness verdict {rep['verdict']}")
        if rep["verdict_strict_literal"] != rep["verdict"]:
            reasons.append(
                f"NOTE: the strict literal overlap leg says {rep['verdict_strict_literal']} "
                f"because {rep['n_comparators_over_limit_and_degenerate']} comparators are "
                f"overlap-degenerate (a random dot set would also exceed 0.70 against them); "
                f"the informative leg says {rep['verdict']}. IR-62-UNIQ-01.")
        card["verdict_reason"] = "; ".join(reasons) or None
        card["uniqueness_rechecked_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        card_path.write_text(json.dumps(card, indent=2, default=str) + "\n")
        print(f"[uniq] run card patched: verdict={card['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
