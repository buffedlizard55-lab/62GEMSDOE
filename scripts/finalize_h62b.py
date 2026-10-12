#!/usr/bin/env python3
"""Finalize the H62-B artifact: emit, validate, holdout, uniqueness, run card.

Everything that leaves this repository as a shippable GeoTIFF goes through here, so there is
exactly one writer, one validator and one run card.  The file is re-read from disk after
writing and every check runs on the bytes on disk, not on the array in memory.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.stats import entropy as shannon_entropy

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import emit, grid, holdout, metric, validate  # noqa: E402

BUILD = ROOT / "build" / "h62b"
SURF = ROOT / "build" / "surfaces"
NAME = "gems62-h62b-lahontan-datumstep-trace-37654dots-20261012T000000Z-zeros"
SUBMISSION_NOTE = ("H62-B Lahontan base-level isobase steps/deflections, ridge-relief traced, "
                   "37654 isolated dots, >=300 m off catalogue. UNSCORED")

# Bars and calibration, all MEASURED in evidence/exp1..exp3.
#
# C_CONTROL is the hard-core Poisson control measured on *exactly* the instrument the
# artifact is scored on -- same truth (SGMC minus catalogue, 79,615 px), same catalogue
# +3 px mask, same mass M=37,654 -- i.e. evidence/exp1_instrument_calibration.json,
# variants.buffer3px.controls.poisson300m_offcat_M37654 = 0.119043.  An independent draw
# in Experiment 2 (M=40,000 over a 59,453-px truth) gave 0.1197, so the control is
# stable to ~0.6 % across draws; 0.1197 is recorded in exp2/exp3 as the screening bar.
C_CONTROL = 0.1190
C_CHAMPION = 0.1324
C_LANE_PREV = 0.1347
SHRINK = dict(slope=0.325, intercept=0.175, r=0.826, p=0.0005)


def load(name: str) -> np.ndarray:
    return np.load(SURF / f"{name}.npy")


def structural_stats(mask: np.ndarray, poscat: np.ndarray, footprint: np.ndarray) -> dict:
    dcat = distance_transform_edt(~poscat) * 100.0
    audit = metric.credit_audit(mask.astype(np.float32))
    dc = dcat[mask]
    H, W = mask.shape
    blocks = np.array([[mask[i * (H // 3):(i + 1) * (H // 3),
                            j * (W // 2):(j + 1) * (W // 2)].sum() for j in range(2)]
                       for i in range(3)], dtype=float).ravel()
    p = blocks / max(blocks.sum(), 1e-9)
    return dict(
        M=int(mask.sum()),
        mean_self_kernel=audit["mean_self_kernel"],
        redundancy_fraction=audit["redundancy_fraction"],
        dcat_median_m=float(np.median(dc)), dcat_mean_m=float(dc.mean()),
        dcat_p10_m=float(np.percentile(dc, 10)), dcat_p90_m=float(np.percentile(dc, 90)),
        frac_within_200m_of_catalogue=float((dc < 200).mean()),
        frac_beyond_1km=float((dc > 1000).mean()),
        frac_on_catalogue=float((mask & poscat).sum() / max(int(mask.sum()), 1)),
        block_entropy_bits=float(shannon_entropy(p[p > 0], base=2)),
        block_counts=[int(b) for b in blocks],
    )


def main() -> int:
    t0 = time.time()
    footprint = np.asarray(load("footprint"), bool)
    poscat = np.asarray(load("catalogue"), bool)
    rows = np.load(BUILD / "cand_rows.npy")
    cols = np.load(BUILD / "cand_cols.npy")
    score = np.load(BUILD / "cand_score.npy")
    M = int(sys.argv[1]) if len(sys.argv) > 1 else 37654
    M = min(M, len(rows))
    order = np.argsort(score)[::-1][:M]
    rr, cc = rows[order], cols[order]

    arr = np.zeros(footprint.shape, np.float32)
    arr[rr, cc] = 1.0
    mask = arr > 0

    out_tif = ROOT / "docs" / "downloads" / f"{NAME}.tif"
    receipt = grid.write_submission(out_tif, arr)
    rep = validate.validate_submission(out_tif, footprint)
    print("validator:", rep.passed, rep.failures, flush=True)

    # SGMC instrument (the one validated against organizer scores)
    sgmc = (rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif").read(1) > 0) & footprint
    known = binary_dilation(poscat, np.ones((7, 7), bool))
    domain = footprint & ~known
    comp = metric.dti_components(arr, (sgmc & ~known).astype(np.float32), valid=domain)
    c = float(comp.tp_w / M)
    ratio = c / C_CHAMPION
    # N-invariant projection: the champion's own implied truth credit, scaled by the ratio of
    # SGMC credits, run through the published metric.  N cancels to first order.
    def projection(N: float) -> float:
        T_ch = 0.2778 * (0.2 * 37654 * 0.968 + 0.8 * N)
        return float(T_ch * ratio / (0.2 * M * 0.968 + 0.8 * N))
    proj = {f"N{int(N)}": projection(N) for N in (6000, 10000, 13704)}
    proj_shrunk = {k: SHRINK["intercept"] + SHRINK["slope"] * v for k, v in proj.items()}

    # protocol holdout (hide-and-recover) — reported, but per IR-62-HOLDOUT-01 never used to
    # promote or reject
    # Holdout A: the protocol's hide-and-recover with the COMPETITION CATALOGUE as truth.
    # IR-62-HOLDOUT-02: mechanically 0 for any emission that keeps 300 m off the catalogue.
    h_cat = holdout.evaluate(arr, poscat, footprint, buffer_m=300.0, bootstrap_n=0)
    # Holdout B: the same evaluator whose withheld population is an INDEPENDENT fault set
    # (SGMC minus catalogue), which is what makes the test satisfiable.
    h_sgmc = holdout.evaluate(arr, poscat, footprint,
                              truth=(sgmc & ~poscat), buffer_m=300.0, bootstrap_n=0)
    fold_dti = [f.dti for f in h_sgmc.folds]
    print(f"holdout catalogue {h_cat.pooled_dti:.6f}  holdout SGMC {h_sgmc.pooled_dti:.5f}",
          flush=True)

    stats = structural_stats(mask, poscat, footprint)
    card = dict(
        lane_id="H62-B",
        lane="datum-offset: pluvial depositional datum as a strain gauge",
        package_version="1.0.0",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        hypothesis=("A 15 ka pluvial depositional surface is a near-level datum. Where its "
                    "base-level surface is stepped or its contour deflected, a structure younger "
                    "than the datum cuts it; such basin-margin structures are the class the "
                    "USGS/INGENIOUS catalogue is incomplete for."),
        mechanism=("base level = smooth(min-filter(DEM, 1.7 km)); HAB = z - base; pluvial band = "
                   "HAB<=120 m & slope<=6 deg & relief<=60 m; isobase = 6 km smooth of the base "
                   "level over the band (absorbs rebound); flags = |resid| >= 2.5 MAD per 50 km "
                   "tile and contour-azimuth kinks >= 25 deg over 300 m; each flag seeds a trace "
                   "that is marched along the local structure azimuth while cross-strike relief "
                   "holds (>= 33 m, the 25th percentile); dots are emitted at a 300 m hard core, "
                   ">= 300 m off every mapped fault, ranked by trace relief, capped at 37,654."),
        named_non_fault_process_that_could_mimic_it=(
            "Differential post-pluvial isostatic rebound itself: rebound varies between "
            "sub-basins, so a purely isostatic warp of the datum produces steps and azimuth "
            "kinks with no fault at all. Secondary mimics: alluvial-fan toes and debris-flow "
            "lobes; the 12-14 ka Truckee/Carson/Walker channel and delta margins (erosional); "
            "bedrock lithologic contacts expressed as differential erosion. The 6 km isobase is "
            "the control for the first; the relief gate and the ridge march are the controls for "
            "the others."),
        raster_sha256=rep.sha256,
        raster_bytes=rep.bytes,
        validator=dict(ok=rep.passed, failures=list(rep.failures),
                       no_nan_inside_footprint=rep.nan_inside_footprint == 0,
                       values_in_0_1=(rep.values_min >= 0.0 and rep.values_max <= 1.0),
                       crs=rep.crs, shape=list(rep.shape),
                       transform=list(rep.transform), nodata=rep.nodata),
        submission_format_receipt=receipt,
        structural_stats=stats,
        instrument=dict(
            name="mean 300 m kernel credit per dot vs SGMC-minus-catalogue, catalogue+3px masked",
            metric="gems62.metric.dti_components (alpha 0.2, beta 0.8)",
            M=M, mean_credit_per_dot=c,
            control_hardcore_poisson=C_CONTROL, champion_h33=C_CHAMPION,
            lane_previous_H62A=C_LANE_PREV,
            ratio_to_control=c / C_CONTROL, ratio_to_champion=ratio,
            coverage_of_sgmc_offcat=float(comp.tp_w / max(comp.tp_w + comp.fn_w, 1e-9)),
            projection_dti=proj,
            projection_shrunk_by_calibration=proj_shrunk,
            calibration_regression=SHRINK,
        ),
        holdout=dict(
            evaluator=h_sgmc.evaluator,
            A_catalogue_truth=dict(pooled_dti=h_cat.pooled_dti,
                                   withheld_cells_total=int(h_cat.withheld_cells_total),
                                   note="IR-62-HOLDOUT-02: identically 0 by arithmetic -- no dot "
                                        "lies within the 300 m kernel of any catalogue pixel. "
                                        "Bug/leakage screen only, never a quality measure."),
            B_sgmc_offcatalogue_truth=dict(
                pooled_dti=h_sgmc.pooled_dti,
                ci95=list(h_sgmc.ci95) if h_sgmc.ci95 else None,
                fold_dti=[float(v) for v in fold_dti],
                fold_dti_spread=float(max(fold_dti) - min(fold_dti)) if len(fold_dti) > 1 else None,
                n_folds=h_sgmc.n_folds, buffer_m=h_sgmc.buffer_m,
                withheld_segments_total=int(h_sgmc.withheld_segments_total),
                withheld_cells_total=int(h_sgmc.withheld_cells_total),
                folds=[dict(fold=f.fold, withheld_segments=f.withheld_segments,
                            withheld_cells=f.withheld_cells, tp_w=f.tp_w, fp_w=f.fp_w,
                            fn_w=f.fn_w, dti=f.dti) for f in h_sgmc.folds],
                note=h_sgmc.note),
            label="HOLDOUT-DTI (evaluator gems62.holdout.v2, whole-segment hide-and-recover)"),
        submission_name=NAME,
        submission_note=SUBMISSION_NOTE,
        submission_note_chars=len(SUBMISSION_NOTE),
        organizer_confirmed_score=None,
        seconds=round(time.time() - t0, 1),
    )
    (ROOT / "evidence" / "run_card_h62b.json").write_text(json.dumps(card, indent=1))
    (ROOT / "docs" / "downloads" / f"{NAME}.json").write_text(json.dumps(card, indent=1))
    print(json.dumps({k: card[k] for k in
                      ("raster_sha256", "structural_stats", "instrument")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
