#!/usr/bin/env python3
"""The information-free ceiling of the official metric, and where each real score sits above it.

Metric (competition page 967, verified): DTI = TP_w / (TP_w + 0.2*FP_w + 0.8*FN_w), with the
triangular kernel k(d) = max(1 - d/R, 0), R = 300 m.  Because TP_w + FN_w = |G| identically
(sum over truth pixels of max k, plus its complement), the index collapses to

    DTI = TP_w / (0.2*M + 0.8*|G| + 0.2*(TP_w - M_cov)),  TP_w <= M_cov <= M

so for a fixed predicted mass M the whole game is TP_w vs the hidden truth size |G|.

If the M predicted pixels carry no information, every (prediction, truth pixel) pair has
E[k] = 1/3 over the disk of radius R (the average of 1 - r/R under a uniform disk), and a random
pixel is within R of a given truth pixel with probability pi*R^2/A.  Hence

    TP_w_random = M * |G| * (pi*R^2/A) / 3

and the ceiling is sup_{|G|} TP_w_random / (0.2M + 0.8|G|) = (pi*R^2/A)/3 / 0.8, attained as
|G| -> infinity; at finite |G| it is smaller.  Any organiser score above the ceiling contains
real information about the hidden truth; the ratio score/ceiling measures how much.

The formula is cross-checked here against a measured control: 40,000 dots drawn uniformly from
the scored region, scored with the official kernel against a known population.

Usage: python3 scripts/metric_ceiling.py [--out evidence/metric_ceiling.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

R = 300.0
PX = 100.0
REGION_PX = 5_167_373                 # data/sample_submission.tif finite cells
AREA_M2 = REGION_PX * PX * PX
PAIR_P = np.pi * R * R / AREA_M2      # P(a random pixel lies within R of a given truth pixel)
E_K = 1.0 / 3.0                       # E[k] over the disk


def ceiling(mass: int, g: int) -> float:
    """DTI of an information-free field of `mass` pixels against a truth of `g` pixels."""
    tp = mass * g * PAIR_P * E_K
    return tp / (0.2 * mass + 0.8 * g)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/metric_ceiling.json")
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    grid = [5_000, 10_000, 20_000, 40_000, 62_098, 100_000, 200_000]
    masses = [20_000, 37_654, 40_000, 60_000, 120_000, 200_000]
    table = {str(m): {str(g): round(ceiling(m, g), 4) for g in grid} for m in masses}
    sup = {str(m): round(m * PAIR_P * E_K / 0.8, 4) for m in masses}

    report = {
        "generated_by": "scripts/metric_ceiling.py",
        "region": {"px": REGION_PX, "area_m2": AREA_M2},
        "pair_probability": PAIR_P,
        "expected_k_over_disk": E_K,
        "ceiling_table": table,
        "supremum_over_truth_size": sup,
        "verification": {
            "measured_uniform_40k_vs_sgmc_absent_62098px": 0.0745,
            "formula_uniform_40k_vs_62098px": round(ceiling(40_000, 62_098), 4),
            "note": "evidence/offcatalogue_coverage.py, seed 20261012; the 100 m hex lattice "
                    "used there excludes a little of the region, hence the small difference.",
        },
        "organiser_scores_against_the_ceiling_at_their_own_mass": {},
    }
    for name, score, mass in (("leaderboard #1 (2026-10-12)", 0.4275, 40_000),
                              ("leaderboard #5 (2026-10-12)", 0.3333, 40_000),
                              ("leaderboard #9 (2026-10-12)", 0.3195, 40_000),
                              ("group best h33-2-b2", 0.2778, 37_654),
                              ("group median 36-42k bucket", 0.2708, 40_000)):
        report["organiser_scores_against_the_ceiling_at_their_own_mass"][name] = {
            "score": score, "assumed_mass": mass,
            "ceiling_at_that_mass": round(mass * PAIR_P * E_K / 0.8, 4),
            "information_multiple": round(score / (mass * PAIR_P * E_K / 0.8), 2),
        }
    out = root / args.out
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["organiser_scores_against_the_ceiling_at_their_own_mass"], indent=1))
    print("verification:", report["verification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
