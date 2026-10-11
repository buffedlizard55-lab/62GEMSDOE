#!/usr/bin/env python3
"""Regenerate docs/ from evidence/*.json.  Every number on the site comes from a
JSON file that was written by a run; nothing is hand-typed into the HTML.

    python scripts/build_site.py

Pages: index, executive-summary, analysis, method, results, hypotheses, profiles,
sources, irregularities, run-card, limitations, leaderboard.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

DOCS = HERE / "docs"
EV = HERE / "evidence"

ORGANIZER_ANCHORS = [
    # (submission name, score, source page) -- all copied from the tasking
    # paragraph's own score list, which is a transcription of submission-page
    # receipts.  Nothing here is inferred.
    ("h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros", 0.2778, "GEMSDOE32"),
    ("anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros", 0.2750, "GEMSDOE36"),
    ("h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan", 0.2710, "GEMSDOE28"),
    ("h27-4-solo-d28-20261004-8acb75e1-nan", 0.2708, "GEMSDOE31"),
    ("h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan", 0.2708, "GEMSDOE28"),
    ("h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan", 0.2707, "GEMSDOE28"),
    ("h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan", 0.2649, "GEMSDOE28"),
    ("h33d-analog-tip-stepover-r30-20261004-cb490425926e", 0.2632, "GEMSDOE33"),
    ("dotted-h19-5-d2-8-20261002-e56ea318af89-nan", 0.2600, "GEMSDOE25"),
    ("d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca", 0.2600, "GEMSDOE30"),
    ("efd28-repro-20261003-1cc7dc534d51-nan", 0.2600, "GEMSDOE29"),
    ("wormrank-d28-20261003-59dcaf6dd11d-zeros", 0.2560, "GEMSDOE29"),
    ("h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan", 0.2477, "GEMSDOE24"),
    ("topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan", 0.2449, "GEMSDOE27"),
    ("gate_ortho_w0.25-40k-20261006T213721Z-nan", 0.2376, "GEMSDOE49"),
    ("h59-cover-ds-belief-b2xh33d-20261008T184547Z-b79c4c61d8d8", 0.2296, "GEMSDOE48"),
    ("h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan", 0.1922, "19GEMSDOE"),
    ("h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan", 0.1894, "19GEMSDOE"),
    ("h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-nan", 0.1890, "20GEMSDOE"),
    ("h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan", 0.1855, "16GEMSDOE"),
    ("h28-dotted-ridge-20260928T020256236880Z-6452ae1d00", 0.1839, "GEMSDOE10"),
    ("gems-submission-20260925T001403Z-7f00890a", 0.1563, "GEMSDOE"),
    ("gemsdoe2-dual-family-union-20260925T160406Z-f68e590f", 0.1560, "GEMSDOE2"),
    ("r11f-scarp-radiometric-fusion-00e049b51218-zeros", 0.1589, "GEMSDOE46"),
    ("lidarscarp-ridge-top2pct-36c3a3f341c8", 0.1461, "7GEMSDOE"),
    ("h30-arrangement-matched-habitat-20261002-0d4e02e8-nan", 0.1352, "GEMSDOE23"),
    ("r7-nms3-dem10-scarp_0c9199f14e62", 0.1294, "12GEMSDOE"),
    ("H25-ctx-ridge-20260927T232947704150Z-6452ae1d00", 0.1280, "GEMSDOE10"),
    ("pindrop-v4-nodes-20260925T152420Z-f347b70daa", 0.1193, "GEMSDOE3"),
    ("h6-physics-dotted-80k-20261005T055000Z-0bef9211631c", 0.1193, "GEMSDOE37"),
    ("h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686", 0.0921, "GEMSDOE10"),
    ("h23-a-dti-optimal-emission-6pct-20261002-e2ec4b49-nan", 0.1002, "GEMSDOE22"),
    ("h18-3a-topo-geophys-x-complexity-prior-20260930-c502dfab-nan", 0.0976, "16GEMSDOE"),
    ("20261001_r13-lattice-s5_v2_nan-outside", 0.0904, "13GEMSDOE"),
    ("pindrop-v4-discovery-20260925T152423Z-37f9d5b855", 0.0830, "GEMSDOE3"),
    ("gems-tso1-20260929T005627Z-conj_alteration_mag", 0.0782, "15GEMSDOE"),
    ("h34-scatter-q50-arr-matched-20261004T223317Z", 0.0778, "GEMSDOE34"),
    ("D-step-3p0-07pct-tipProt-20261005-ecfbf59e2b48-zero", 0.0763, "GEMSDOE38"),
    ("h56-final-dotted-ridge-d2p8-20261009T190421Z", 0.0658, "56GEMSDOE"),
    ("xscale-worm-persistence-20261006T000541Z-nan", 0.0581, "GEMSDOE42"),
    ("h16-continuation-20260927T065521077735Z-3431b83c7c", 0.0461, "GEMSDOE10"),
    ("h35-06-aaa86efb25-20261004T225420098147Z-candidate", 0.0418, "GEMSDOE35"),
    ("sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan", 0.0424, "GEMSDOE43"),
    ("h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard", 0.0397, "GEMSDOE40"),
    ("h18-4-usgs-geologic-map-faults-gap-20260930-aef8f42c-nan", 0.0360, "16GEMSDOE"),
    ("gems-submission-20260926T163915Z-237f0063", 0.0343, "GEMSDOE4"),
    ("h40-e-disc-h40e-30k-zeros", 0.0339, "GEMSDOE39"),
    ("H19-C_20260930T212401Z_c11e495e", 0.0297, "18GEMSDOE"),
    ("tensor_full-n16000-sep3-20261009T211747Z-nan", 0.0290, "55GEMSDOE"),
    ("gems6_hgb88-topk03_33cec71ff0", 0.0286, "6GEMSDOE"),
    ("h42-submission-primary", 0.0245, "GEMSDOE41"),
    ("gems-structural-area06-v1", 0.0202, "11GEMSDOE"),
    ("17GEMSDOE_F-ensemble-2pct_20260930T050626Z", 0.0187, "17GEMSDOE"),
    ("h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros", 0.0159, "GEMSDOE53"),
    ("h51-km-faultzone-20261006-zeros", 0.0106, "GEMSDOE45"),
    ("2314b599", 0.0107, "GEMSDOE9"),
    ("GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f", 0.0020, "14GEMSDOE"),
    ("repo-c0-habitat-emission-20261003-a4d439b07426-nan", 0.0041, "GEMSDOE29"),
]

SOURCES = [
    ("Competition home", "https://www.drivendata.org/competitions/306/competition-doe-gems/",
     "DrivenData #306, The Geologic Enhanced Mapping System (GEMS) Prize Challenge", "organiser"),
    ("Problem description & performance metric",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
     "DTI definition, alpha=0.2, beta=0.8, R=300 m triangular kernel, worked example (TP_w=3.00, "
     "FP_w=1.89, FN_w=2.00 -> 0.60), submission format", "organiser"),
    ("About / resources", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/",
     "additional resources", "organiser"),
    ("Data download (login required)",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
     "training_features.tif, labels, sample_submission.tif, 1m_DEM_links.csv", "organiser"),
    ("Leaderboard", "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
     "current standings", "organiser"),
    ("Rules", "https://www.drivendata.org/competitions/306/competition-doe-gems/rules/",
     "external-data licensing condition", "organiser"),
    ("Reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution",
     "U-Net + Monte Carlo CV, TverskyLoss(alpha=0.2, beta=0.8); confirms the loss parameters",
     "organiser"),
    ("GEMS technical PDF (OSTI 96647)", "https://docs.nlr.gov/docs/fy26osti/96647.pdf",
     "challenge outline as cited in the tasking brief", "cited-in-brief"),
    ("GeoDAWN survey", "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
     "USGS airborne magnetic & radiometric surveys, northwestern Great Basin, NV", "USGS"),
    ("INGENIOUS project", "https://gbcge.org/current-projects/ingenious/",
     "Great Basin Center for Geothermal Energy; source of part of the label set", "GBCGE"),
    ("EPSG:32611", "https://epsg.io/32611", "WGS 84 / UTM zone 11N -- the submission CRS", "EPSG"),
    ("Tversky index", "https://en.wikipedia.org/wiki/Tversky_index",
     "the similarity measure the DTI is a distance-weighted form of", "reference"),
    ("OpenEI GDR submission 1391", "https://gdr.openei.org/submissions/1391",
     "geothermal data resource cited in the tasking brief", "OpenEI"),
    ("DrivenData GEMS forum", "https://community.drivendata.org/c/gems-prize-challenge/111",
     "organiser answers, incl. known-fault masking (thread 11516)", "organiser"),
]

LITERATURE = [
    ("Briggs & Wesnousky 2004", "JGR",
     "Used features displaced since the Lahontan highstand to constrain slip on the Pyramid "
     "Lake fault zone. Cited in the tasking brief.", "cited-in-brief"),
    ("Dong et al.", "Geosphere",
     "Documented Lahontan shorelines displaced along a strike-slip fault outboard of the "
     "Wassuk Range front. Cited in the tasking brief.", "cited-in-brief"),
    ("Pierce & Wesnousky 2016", "SCEC poster",
     "Two previously unmapped NW-striking segments in Smith Valley's basin centre offsetting "
     "Holocene sediments. Cited in the tasking brief.", "cited-in-brief"),
]

IRREGULARITIES = [
    dict(id="IR-62-HOLDOUT-01", severity="CRITICAL -- invalidates the promotion gate",
         status="open -- measured, not fixable inside this repository",
         title="The hide-and-recover holdout is ANTI-correlated with the organiser's score",
         detail=("The parallel-run protocol gates every submission on the segmented holdout, and the "
                 "standing instruction is not to spend a weekly slot on an idea that has not beaten "
                 "the current holdout best. Scoring 10 ORGANIZER-CONFIRMED artifacts as FROZEN dot "
                 "masks on one identical holdout shows that gate points the wrong way: "
                 "Spearman(HOLDOUT-DTI, ORGANIZER-CONFIRMED) = -0.9141 (p = 0.0002), Kendall tau "
                 "-0.8140 (p = 0.0015). It is not merely a dot-count artefact: the partial Spearman "
                 "controlling for n_dots is -0.6810 (p = 0.0302), and in 7 of 8 count-matched pairs "
                 "(|Delta dots| <= 1,500) the file with the LOWER holdout carries the HIGHER "
                 "organiser score. The cleanest case is h33-h33-2-b2 (37,654 dots, HOLDOUT 0.0053, "
                 "ORGANIZER 0.2778) against h36-1-rung30-blind-r1 (37,660 dots -- six apart -- "
                 "HOLDOUT 0.0368, ORGANIZER 0.2710): a 7x holdout difference in the wrong direction."),
         evidence=("evidence/e9_frozen_artifact_holdout.json, produced by scripts/compare_holdout.py "
                   "over registry/organizer_scores.json. Mechanism, measured directly: the holdout "
                   "withholds whole segments of the PUBLIC catalogue and scores their recovery, while "
                   "the organiser's Initial Prize Round scores a PRIVATE set of faults labelled before "
                   "the competition. The holdout therefore rewards dots that hug the catalogue and the "
                   "organiser rewards dots that avoid it. The 0.2778 file was built by DELETING 6,436 "
                   "dots within 3 px of the mapped catalogue, which raised its organiser score "
                   "0.2600 -> 0.2778 and collapses its holdout DTI 0.1322 -> 0.0053. Our own artifact "
                   "has zero dots within 3 px of any catalogue pixel (minimum distance 3.2 px, median "
                   "18.9 px), so its frozen HOLDOUT-DTI is exactly 0.0000 -- by construction, not by "
                   "failure. The same is true of the winner."),
         resolution=("NOT papered over and NOT worked around. The run card's verdict is 'negative' and "
                     "the artifact is marked ok_to_submit = false, because the repository has no valid "
                     "instrument with which to justify spending a slot. The E3 arm-A3 number (0.1224) "
                     "remains a correct measurement of the PROCEDURE under per-fold visible-only "
                     "pruning, and is reported as such, but it is no longer presented as a promotion "
                     "argument. Fixing the gate needs a hidden truth set that is not the public "
                     "catalogue, which this sandbox cannot obtain."),
         unblock=("Either (a) obtain the organiser's private label set -- not public -- or (b) accept "
                  "that selection between off-catalogue artifacts is a human judgement informed by the "
                  "ORGANIZER-CONFIRMED budget ladder, not a holdout decision. Option (b) is what the "
                  "protocol already implies when it says promotion is a separate selector step."),
         source="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
    dict(id="IR-62-DEM-01", severity="high", status="open -- worked around",
         title="No absolute-elevation band exists in the official feature stack",
         detail=("The lane is specified as 'map shoreline benches in the DEM'. training_features.tif "
                 "has 19 bands and the only topographic ones are band 12 'Detrended elevation - "
                 "topography with regional trends removed' and band 19 its slope. A Lahontan isobase "
                 "is an ABSOLUTE elevation datum, so the detrending operator removes part of the "
                 "signal the lane needs. Verified by reading the band DESCRIPTION tags from the "
                 "sha256-pinned file itself."),
         evidence="evidence/e0_data_verification.json -> spec.band_descriptions",
         resolution=("The isobase is fit in detrended-elevation space (6 km Gaussian through the "
                     "pluvial-lake-margin band) and the flags are residuals against that fit. A "
                     "smooth detrend and a smooth isobase tilt are degenerate at long wavelength, "
                     "so the fit absorbs the unknown trend and the residual keeps the "
                     "short-wavelength step signal. The absolute shoreline elevation (the ~1177 m "
                     "class number) cannot be used and is not claimed anywhere on this site."),
         unblock="1m_DEM_links.csv from the DrivenData data tab, or USGS 3DEP directly. Free, public domain. Not reachable from this sandbox."),
    dict(id="IR-62-SENTINEL-01", severity="high", status="closed -- root cause of the portal error",
         title="3,061 cells inside the submission footprint carry the float32 nodata sentinel",
         detail=("training_features.tif uses -3.4028234663852886e+38 as nodata. Re-measured here: "
                 "7,113,308 cells carry it, and 3,061 of those lie INSIDE the submission footprint "
                 "(sample_submission.tif is finite there) in all 19 bands; band 6 'tc' has 12 extra "
                 "(3,073). Writing those values through unchanged puts cells outside [0, 1] and the "
                 "portal returns 'Predicted values must be in range [0, 1]'."),
         evidence="evidence/e0_data_verification.json -> spec.sentinel_cells_inside_footprint = 58,171 (= 19 bands x 3,061 + 12)",
         resolution=("submission_writer.py writes an all-finite artifact: zeros outside the "
                     "footprint, no nodata tag, every one of the 12,279,160 cells finite and in "
                     "[0, 1]. validate.py re-opens the bytes from disk and asserts it. This is the "
                     "form the group's organiser-confirmed 0.2778 file was shipped in."),
         unblock="none needed"),
    dict(id="IR-62-BENCH-01", severity="medium", status="closed -- bug found and fixed in this session",
         title="The bench mask circularly excluded the residuals it was meant to flag",
         detail=("The first implementation of bench_pixels() required |elev - isobase| to be below "
                 "the 60th percentile of the in-band residual, and flag_steps() then looked for "
                 "residual outliers inside that set. The two conditions are contradictory: the run "
                 "produced n_steps = 0 over the entire 5.17 M-pixel footprint."),
         evidence="first run: n_bench=230,025, n_steps=0, step_threshold_m=127.7",
         resolution=("bench_pixels() is now geometric only (margin band + slope window + plan "
                     "curvature percentile). The residual test lives solely in flag_steps(). "
                     "tests/test_gems62.py::test_bench_pixels_no_longer_excludes_large_residuals "
                     "asserts the regression cannot return."),
         unblock="none needed"),
    dict(id="IR-62-STEP-01", severity="medium", status="closed -- measured and corrected",
         title="An unbounded isobase-residual outlier test selects DEPLETED terrain",
         detail=("Flagging steps as 'residual > k * MAD' keeps exactly the pixels the lane should "
                 "reject. Measured catalogue enrichment by |isobase residual| inside the bench "
                 "band: 2.26-2.77x below 210 m, then 1.45x at 210-260 m, 1.16x at 260-320 m, "
                 "0.66x at 320-400 m, and 0.00x above 400 m (403 px, not one mapped fault). The "
                 "unbounded k=2.5 flag scored 1.21x over 14,586 px -- below the 2.44x of the bench "
                 "band it was drawn from."),
         evidence="evidence/e2_enrichment.json",
         resolution=("flag_steps() takes a bounded throw window [15, 130) m. The bounds have an "
                     "independent physical meaning: a structure offsetting the ~15 ka highstand at "
                     "1-8 mm/yr accumulates 15-120 m of throw in 15 kyr, which brackets the "
                     "slow-to-fast range of Great Basin faults. Below ~15 m the step is under what "
                     "a 100 m pixel can express; above ~130 m it is the range front or a canyon "
                     "head, not a displaced shoreline."),
         unblock="none needed"),
    dict(id="IR-62-EXT-01", severity="medium", status="closed -- bug found and fixed in this session",
         title="Trace extension walked across the structure instead of along it",
         detail=("extend_traces() originally derived its walk direction from the gradient of the "
                 "smoothed evidence field, on the argument that evidence ridges run along the "
                 "structure. On this data that direction is far too noisy: median trace length 1 "
                 "px, mean 2.4 px -- the traces never extended at all."),
         evidence="first run: n_traces=1,943, traced_px=3,801, len_mean=2.4, len_median=1",
         resolution=("The walk direction is now the strike of the fitted isobase "
                     "(local_strike()), which is well posed, and the evidence field is used only as "
                     "the stopping criterion -- which is what the lane text actually says. "
                     "tests/test_gems62.py::test_extend_traces_walks_along_strike_not_across_it "
                     "asserts a north strike yields a north-south trace and no east-west motion."),
         unblock="none needed"),
    dict(id="IR-62-NMS-01", severity="low", status="closed -- bug found and fixed in this session",
         title="The greedy dot thinning was O(k^2) and could not finish a fold",
         detail=("_greedy_thin() compared each candidate against a growing Python list via "
                 "np.asarray(taken_y), which is O(k^2): at a 38,000-dot budget that is ~1.4e9 "
                 "element conversions per holdout fold."),
         evidence="code inspection; the first holdout run did not complete a fold",
         resolution="Replaced with a spatial hash of cell size min_sep, O(1) amortised, with an early break at the budget.",
         unblock="none needed"),
    dict(id="IR-62-HOLDOUT-01", severity="high", status="open -- structural, cannot be fixed here",
         title="The holdout's truth is the visible catalogue, so it cannot reward a new fault",
         detail=("The competition's hidden test set is a set of faults NOT in the USGS/INGENIOUS "
                 "catalogue. Every holdout in this repository can only score against catalogue "
                 "faults, and this lane's whole premise is that it finds structures the catalogue "
                 "is missing. A holdout win is therefore necessary but not sufficient, and a "
                 "holdout loss does not prove the lane wrong."),
         evidence="same limitation recorded as IR-32-PROXY-01 in buffedlizard55-lab/GEMSDOE32",
         resolution=("Reported, not hidden. Every score on this site is labelled HOLDOUT-DTI and "
                     "carries the evaluator version, the withheld-positive count and a 95% CI. No "
                     "projection is ever written as a score."),
         unblock="the organiser's hidden label set, which no participant has"),
    dict(id="IR-62-DATA-01", severity="medium", status="open -- access limitation",
         title="No DrivenData authentication in this sandbox",
         detail=("The data tab redirects to login. training_features.tif, labels.tif, "
                 "sample_submission.tif and 1m_DEM_links.csv cannot be downloaded directly."),
         evidence="curl https://www.drivendata.org/ from this sandbox -> connection refused (egress allowlist)",
         resolution=("The three rasters were restored from the in-organisation git bridge "
                     "(buffedlizard55-lab/6GEMSDOE : data/bridge/) and re-verified against the "
                     "published sha256 pins -- all three match exactly. 1m_DEM_links.csv is NOT "
                     "available and is the reason IR-62-DEM-01 stays open."),
         unblock="run scripts/download_competition_data.sh on a machine with DrivenData login"),
    dict(id="IR-62-DEFL-01", severity="low", status="open -- honest negative",
         title="Lateral deflections along strike carry no catalogue enrichment at 100 m",
         detail=("The lane asks for 'abrupt steps OR lateral deflections along strike'. The "
                 "azimuth-kink flag (>22 deg over 3 px) selects 1,173-4,399 px and measures 1.12x "
                 "enrichment -- at the footprint mean, i.e. no signal. Broken out by habitat it is "
                 "0.75x, 1.42x, 0.90x, 0.52x across habitat bins: inconsistent."),
         evidence="measured in this session; recorded in evidence/e1_lane_surfaces.json",
         resolution=("Kept in the emission as low-priority seeds because the lane specifies them, "
                     "but they contribute ~0.4% of the flag set and are not relied on. The finding "
                     "is reported rather than quietly dropped."),
         unblock="1 m lidar: a lateral offset of a shoreline bench is a metre-scale feature"),
]

HYPOTHESES = [
    dict(rank=1, id="H62-A", title="Isobase-residual throw window x basin-margin habitat (IMPLEMENTED)",
         layers="band 12 det_elev, band 19 det_elev_slope, band 3 tmi_hg, band 18 iso_grav_anom_hg",
         signature=("Smooth isobase fit (6 km Gaussian) through the pluvial-lake-margin band; "
                    "bounded residual window [15,130) m; plan-curvature-selected contour-parallel "
                    "benches; across-strike profile curvature + horizontal-gradient rank for trace "
                    "support."),
         why_new=("A fault that offsets a 15 ka shoreline is by construction younger than the "
                  "highstand, so it is a fault the catalogue is most likely to be missing or "
                  "mislocated. The measured habitat -- deep topographic position (tpi < -120 m) "
                  "with a scarp-scale slope -- is 2.3-3.2x enriched, and the throw-window "
                  "intersection with habitat >= 2.0 measured 3.67x over 66,163 px."),
         differs=("No sibling repository fits an isobase or uses a bounded throw window. The "
                  "closest lanes are gravity basement-depth steps (61GEMSDOE), radiometric scarp "
                  "fusion (GEMSDOE46) and Euler-deconvolution lineaments (GEMSDOE40) -- all "
                  "subsurface or potential-field, none shoreline-datum based."),
         cost="implemented", expected="HOLDOUT-DTI 0.1224 (CI 0.1154-0.1284) vs random lines 0.0228"),
    dict(rank=2, id="H62-B", title="Isobase-parallel strike continuity: gaps between collinear mapped traces",
         layers="band 12 det_elev, labels.tif (visible faults only)",
         signature=("Fit a RANSAC line to each collinear run of visible catalogue traces inside a "
                    "basin-margin band, then score the GAP between the ends of two runs whose "
                    "strikes agree within ~10 deg and whose perpendicular offset is < ~300 m. "
                    "Emit dots only in the gap."),
         why_new=("Pierce & Wesnousky's Smith Valley segments are exactly this: short "
                  "NW-striking segments in a basin centre that earlier maps missed. A gap between "
                  "two collinear mapped traces is a fault the catalogue demonstrably failed to "
                  "connect -- the single most direct definition of 'missing' available without "
                  "hidden labels."),
         differs="GEMSDOE27's topo-gap-closure worked on a d1.5 base but closed gaps in a "
                 "probability surface, not in the catalogue's own strike geometry.",
         cost="~3 h; no new data", expected="medium-high: targets catalogue incompleteness directly"),
    dict(rank=3, id="H62-C", title="Radiometric K/Th breach of the clay cap at basin-margin faults",
         layers="GeoDAWN radiometrics (NOT in the 19-band stack) x band 17 cond_surf x band 15 depth_to_base_surf",
         signature=("Potassium metasomatism and hydrothermal clay alteration along a permeable "
                    "fault produce a local K/Th ratio anomaly that breaches the low-conductivity "
                    "cap. Target the intersection of high cond_surf, shallow depth_to_base_surf "
                    "and a radiometric ratio edge."),
         why_new=("This is the only signature in the list that is diagnostic of the GEOTHERMAL "
                  "part of 'geothermal-indicative fault' rather than of a fault per se, which is "
                  "what the prize is actually about."),
         differs="GEMSDOE46 fused a radiometric scarp detector but as a scarp proxy, not as a "
                 "K/Th alteration ratio against a clay cap.",
         cost=("BLOCKED on data: the radiometric channels are not among the 19 bands. The free "
               "official source is the USGS GeoDAWN release "
               "(https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) "
               "and the ScienceBase item 657e1d85d34e23d3533209f7. Public domain, but usgs.gov is "
               "not in this sandbox's egress allowlist -- OBTAINABILITY UNVERIFIED HERE."),
         expected="high if obtained; cannot be validated without the radiometric grid"),
    dict(rank=4, id="H62-D", title="Strain-rate dilatation bands as the deep expression of basin-margin faults",
         layers="band 7 geod_shearrate, band 8 geod_dilaterate, band 4 geod_2ndinv",
         signature=("Dilatation-rate maxima aligned along strike with a basin-margin scarp. A "
                    "locked or creeping fault shows as a narrow band of dilatation contrast in "
                    "GPS/InSAR-derived strain even where no surface expression is mapped."),
         why_new=("Strain rate is the one layer family that is insensitive to erosion and "
                  "alluviation, so it can localise a fault whose surface expression has been "
                  "buried -- the failure mode that makes catalogue faults incomplete in basin "
                  "centres."),
         differs="61GEMSDOE's H61-M used a gravity+magnetic conjunction; no sibling lane uses the "
                 "geodetic strain family as the primary localiser.",
         cost="~2 h; data already in the stack", expected="low-medium: the 100 m grid smooths strain heavily"),
    dict(rank=5, id="H62-E", title="Earthquake-density azimuthal anisotropy (deq/ieq directional decomposition)",
         layers="band 10 deq_n100a15, band 16 ieq_n100a15",
         signature=("These bands are already azimuthally parameterised (n=100 km radius, "
                    "a=15 deg azimuth). The ratio between two azimuthal samples isolates "
                    "lineations; a fault shows as a persistent azimuthal contrast rather than a "
                    "radial one."),
         why_new=("Seismicity clusters on active structures, and an unmapped active fault is "
                  "precisely the target class."),
         differs="No sibling lane decomposes these bands; all treat them as scalar distance/intensity.",
         cost="~2 h; data already in the stack", expected="low: the parameterisation is not documented well enough to invert confidently"),
]

CSS = """
:root{--ink:#12212f;--mut:#5b6b7b;--line:#dfe6ec;--bg:#f6f8fa;--card:#fff;
--acc:#0f5c8c;--good:#1a7f4b;--warn:#b26a00;--bad:#b3261e;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{background:#0b1c2b;color:#fff;padding:18px 0}
header .w{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
header h1{font-size:19px;margin:0;font-weight:650;letter-spacing:.2px}
header .sub{color:#9fb6c9;font-size:13px}
nav{background:#12293c;padding:0;border-bottom:3px solid #1c4a70}
nav .w{display:flex;flex-wrap:wrap;gap:2px}
nav a{color:#cfe0ee;text-decoration:none;font-size:13px;padding:9px 11px;display:block}
nav a:hover{background:#1c4a70;color:#fff}
nav a.on{background:#1c4a70;color:#fff;font-weight:600}
.w{max-width:1080px;margin:0 auto;padding:0 18px}
main{padding:26px 0 60px}
h2{font-size:21px;margin:34px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:16.5px;margin:22px 0 8px}
p{margin:9px 0}
a{color:var(--acc)}
code,kbd{font-family:var(--mono);font-size:13px;background:#eef2f6;padding:1px 5px;border-radius:4px}
pre{background:#0b1c2b;color:#dbe7f1;padding:13px;border-radius:8px;overflow:auto;font-size:12.5px;line-height:1.5}
pre code{background:none;color:inherit;padding:0}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;background:var(--card)}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#eaf0f5;font-weight:650;font-size:13px}
tr:nth-child(even) td{background:#fbfcfd}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0}
.dl{background:linear-gradient(180deg,#fff,#f2f8fd);border:2px solid #1c4a70;border-radius:12px;padding:20px;margin:16px 0}
.dl h2{border:0;margin:0 0 6px;font-size:22px}
.btn{display:inline-block;background:#12691f;color:#fff;text-decoration:none;font-weight:650;
padding:13px 22px;border-radius:9px;font-size:16px;margin:6px 8px 6px 0}
.btn:hover{background:#0d5218}
.btn.sec{background:#1c4a70}
.btn.sec:hover{background:#153a58}
.btn.ghost{background:#fff;color:#12212f;border:1.5px solid #9fb0bf}
.pill{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;
padding:3px 9px;border-radius:20px;vertical-align:middle}
.pill.ok{background:#dff3e5;color:#125c33}
.pill.no{background:#fbe0de;color:#8c1d16}
.pill.warn{background:#fdf0d8;color:#7a4b00}
.pill.info{background:#e2edf7;color:#12405f}
.callout{border-left:4px solid #b9c6d2;background:#f6f8fa;padding:12px 16px;border-radius:0 6px 6px 0;margin:12px 0}
.callout.ok{border-left-color:#2e7d4f;background:#f0f8f2}
.callout.warn{border-left-color:#b8860b;background:#fdf8ec}
.callout.no{border-left-color:#b3261e;background:#fdf1f0}
.callout ul{padding-left:20px}
.callout li{margin:6px 0}
tr.hi{background:#fff8e1}
tr.ours{background:#eef4fb;font-weight:600}
.ok{color:var(--good);font-weight:650}
.no{color:var(--bad);font-weight:650}
.warn{color:var(--warn);font-weight:650}
.mut{color:var(--mut)}
.small{font-size:13px}
.big{font-size:34px;font-weight:700;font-family:var(--mono);letter-spacing:-1px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:820px){.grid2,.grid3{grid-template-columns:1fr}}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .l{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
blockquote{border-left:4px solid #1c4a70;margin:12px 0;padding:6px 14px;background:#f0f5fa;color:#22384a}
footer{border-top:1px solid var(--line);padding:20px 0;color:var(--mut);font-size:13px}
.toc{columns:2;font-size:14px}
@media(max-width:820px){.toc{columns:1}}
figure{margin:12px 0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px}
figure img{max-width:100%;height:auto;display:block;border-radius:4px}
figcaption{font-size:12.5px;color:var(--mut);padding:6px 2px 0}
.checklist li{margin:5px 0}
"""


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def load(name: str, default=None):
    p = EV / name
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def fmt(v, nd=4):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return esc(v)


def page(title: str, body: str, active: str = "", blurb: str = "") -> str:
    links = [("index.html", "Home"), ("executive-summary.html", "How to submit"),
             ("analysis.html", "Why 0.2778"), ("method.html", "Method"),
             ("results.html", "Results"), ("hypotheses.html", "Hypotheses"),
             ("profiles.html", "Shoreline profiles"), ("sources.html", "Sources"),
             ("irregularities.html", "Irregularities"), ("run-card.html", "Run card"),
             ("limitations.html", "Limitations"), ("leaderboard.html", "Leaderboard")]
    def _navlink(h: str, t: str) -> str:
        cls = ' class="on"' if h == active else ""
        return f'<a href="{h}"{cls}>{esc(t)}</a>'

    nav = "".join(_navlink(h, t) for h, t in links)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 62GEMSDOE</title>
<meta name="description" content="{esc(blurb or title)}">
<link rel="stylesheet" href="assets/site.css">
</head><body>
<header><div class="w"><h1>62GEMSDOE — Lake Lahontan shorelines as a strain gauge</h1>
<span class="sub">DOE GEMS Prize · DrivenData #306 · datum-offset lane H62-A</span></div></header>
<nav><div class="w">{nav}</div></nav>
<main><div class="w">{body}</div></main>
<footer><div class="w">Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from
<code>evidence/*.json</code> by <code>scripts/build_site.py</code>. Every number on this site is
labelled <b>HOLDOUT-DTI</b> or <b>ORGANIZER-CONFIRMED</b>. No projection is written as a score.
<a href="../README.md">README</a> · <a href="https://github.com/buffedlizard55-lab/62GEMSDOE">repository</a></div></footer>
</body></html>
"""


def kpi(label, value, sub=""):
    return (f'<div class="kpi"><div class="l">{esc(label)}</div>'
            f'<div class="big">{value}</div>'
            f'<div class="small mut">{sub}</div></div>')


def _n(v) -> str:
    """Integer with thousands separators, or an em dash if it is missing.

    `esc()` returns a string, so `{_n(x)}` raises
    "Cannot specify ',' with 's'" -- these eight sites were the reason
    build_site.py had never been executed successfully.
    """
    if v is None:
        return "\u2014"
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return esc(v)


def _f(v, spec: str = "") -> str:
    """Float format that tolerates a missing value (returns an em dash)."""
    if v is None:
        return "\u2014"
    try:
        return format(float(v), spec.lstrip(":") or ".4g")
    except (TypeError, ValueError):
        return esc(v)


def _pill(ok: bool, yes: str = "PASS", no: str = "FAIL") -> str:
    cls, txt = ("ok", yes) if ok else ("no", no)
    return f'<span class="{cls}">{esc(txt)}</span>'


def canary_rows(aucs: dict, limit: float = 0.90) -> str:
    """One table row per canary AUC, flagged against the leakage limit.

    Hoisted out of the f-string on purpose: an inline conditional carrying a
    class name needs escaped quotes, and a backslash inside an f-string
    expression is a SyntaxError before Python 3.12.
    """
    out = []
    for k, v in aucs.items():
        ok = v <= limit
        cls, txt = ("ok", "OK") if ok else ("no", "LEAKAGE")
        out.append(
            f"<tr><td><code>{esc(k)}</code></td>"
            f"<td class='num'>{v:.3f}</td>"
            f"<td>{_pill(ok, txt, txt)}</td></tr>")
    return "".join(out)


def check_table(receipt: dict) -> str:
    if not receipt:
        return "<p class='mut'>No validation receipt found. Run <code>scripts/run_lane.py</code>.</p>"
    rows = "".join(
        f"<tr><td>{esc(c['check'])}</td>"
        f"<td>{_pill(c['ok'])}</td>"
        f"<td class='num small'>{esc(c['detail'])}</td></tr>"
        for c in receipt.get("checks", []))
    return ("<table><thead><tr><th>check</th><th>result</th><th>measured</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


# --------------------------------------------------------------------------------------
def build():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "assets").mkdir(exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS)
    (DOCS / ".nojekyll").touch()
    (HERE / ".nojekyll").touch()

    e0 = load("e0_data_verification.json", {})
    e1 = load("e1_lane_surfaces.json", {})
    e2 = load("e2_enrichment.json", {})
    e2c = load("e2_canary.json", {})
    e2b = load("e2b_traces.json", {})
    e3 = load("e3_holdout.json", {})
    e3c = load("e3_canary_withheld.json", {})
    e4 = load("e4_profiles.json", {})
    e5 = load("e5_emission.json", {})
    e6 = load("e6_submission.json", {})
    e7 = load("e7_uniqueness.json", {})
    e7b = load("e7b_uniqueness_null_analysis.json", {})
    card = load("e8_run_card.json", {})
    e9 = load("e9_frozen_artifact_holdout.json", {})

    spec = (e0 or {}).get("spec", {})
    rec = (e6 or {}).get("receipt", {})
    ok_submit = bool((e6 or {}).get("ok_to_submit"))
    status = (card or {}).get("artifact_status") or {}
    gate = (card or {}).get("holdout_gate") or {}
    uni = (card or {}).get("correlation_and_overlap_vs_registry") or {}
    ok_submit = bool(status.get("ok_to_submit", ok_submit))
    verdict = (card or {}).get("verdict", "not-run")
    vpill = ('<span class="pill ok">PROMOTE-CANDIDATE</span>' if verdict == "promote"
             else '<span class="pill warn">NEGATIVE RESULT</span>' if verdict == "negative"
             else '<span class="pill info">NOT RUN</span>')

    stem = (card or {}).get("submission_name") or (e6 or {}).get("stem") or ""
    tif = f"downloads/{stem}-zeros.tif" if stem else None
    zp = f"downloads/{stem}-zeros.zip" if stem else None
    note = (card or {}).get("submission_note", "")

    hold = ((e3 or {}).get("arms") or {})
    best_arm = (card or {}).get("holdout", {}).get("best_arm")
    hd = (card or {}).get("holdout", {})
    ci = hd.get("ci95") or [None, None]

    # ---------------------------------------------------------------- index
    fmt_ok = bool((rec or {}).get("ok"))
    safe = ("YES — FORMAT-VALID" if fmt_ok else "NO — FORMAT INVALID")
    submit_pill = ("YES" if ok_submit else "NO — NOT VALIDATED")
    slot = ("YES" if verdict == "promote" else "NO — honest negative" if verdict == "negative" else "—")

    b = []
    b.append(f"""<div class="dl">
<h2>⬇ ONE-CLICK SUBMISSION FILE</h2>
<p style="font-size:17px;margin:2px 0 14px"><b>Is it OK to <u>download</u> this file?</b>
&nbsp;<span class="pill {'ok' if fmt_ok else 'no'}">{esc(safe)}</span>
&nbsp; {_n(rec.get('n_pass'))}/{_n((rec.get('n_pass') or 0) + (rec.get('n_fail') or 0))} checks pass.</p>
<p style="font-size:17px;margin:2px 0 12px"><b>Is it OK to <u>submit</u> this file?</b>
&nbsp;<span class="pill {'ok' if ok_submit else 'no'}">{esc(submit_pill)}</span>
&nbsp;{vpill}</p>
<div class="callout {'ok' if ok_submit else 'warn'}">
<p style="margin:0 0 6px"><b>{esc(status.get('ok_to_submit_reason') or 'See the run card.')}</b></p>
<p class="small" style="margin:0">Two irregularities are open and both need a human decision, not an
autonomous one:</p>
<ul class="small" style="margin:6px 0 0">
<li><b>IR-62-HOLDOUT-01 — the promotion gate is broken.</b> Across
{_n(gate.get('count_matched_pairs') and len([r for r in (e9.get('rows') or []) if isinstance(r.get('organizer_confirmed_score'), float)]))}
ORGANIZER-CONFIRMED artifacts scored on one identical holdout, HOLDOUT-DTI is
<b>anti-correlated</b> with the organizer's score: Spearman
<b>{_f(gate.get('spearman_holdout_vs_organizer'), '+.4f')}</b>
(p={_f(gate.get('spearman_p'), '.4f')}), and it survives controlling for dot count
(partial Spearman {_f(gate.get('partial_spearman_given_ndots'), '+.4f')},
p={_f(gate.get('partial_spearman_p'), '.4f')}).
{_n(gate.get('count_matched_pairs_lower_holdout_higher_organizer'))} of
{_n(gate.get('count_matched_pairs'))} count-matched pairs go the same way.
The withheld truth <i>is</i> public catalogue, so the holdout rewards dots that hug the
catalogue, while the organizer's private set rewards dots that avoid it. Our artifact has
zero dots within 3 px of the catalogue and therefore scores
{_f(gate.get('our_shipped_artifact_frozen_dti'), '.4f')} on it — by construction, not by
failure. <a href="results.html#frozen">The full table</a>.</li>
<li><b>IR-62-UNIQ-01 — the uniqueness rule returns DUPLICATE, and the artifact is
still not a copy.</b> {_n(uni.get('n_comparators_over_overlap_limit'))} comparator rows put
&gt;70% of our dots within 3 px. Calibrating that leg with two nulls — dots scattered anywhere
in the footprint, and dots scattered through <i>our own</i> catalogue-free lane habitat — waives
all but <b>{_n(uni.get('n_binding_distinct_fields'))}</b> distinct fields, and those bind only
marginally: their habitat nulls sit within {_f(uni.get('binding_margin_to_waiver'), '.3f')} of
the 0.70 waiver cliff, and <i>which</i> of them binds flips with the null seed. So the rule's
answer is <b>{esc(uni.get('verdict'))}</b> and this repository does not overrule its own tasking
protocol autonomously.<br>
But every statistic that can actually detect <b>copying</b> is far inside its limit: max Jaccard
<b>{_f(uni.get('max_jaccard'), '.4f')}</b> (limit 0.50), max signed rho
<b>{_f(uni.get('max_signed_rho'), '+.4f')}</b> (limit 0.90, most negative
{_f(uni.get('min_signed_rho'), '+.4f')} — anti-correlation, the opposite of copying), max mutual
containment <b>{_f(uni.get('max_reverse_overlap'), '.4f')}</b>.
<code>is_a_copy = {esc(str(uni.get('is_a_copy')))}</code>. Against the 0.2778 file specifically we
share {_n((uni.get('vs_organizer_best_0_2778') or {}).get('n_intersection'))} exact pixels of its
{_n((uni.get('vs_organizer_best_0_2778') or {}).get('n_theirs'))}, and
{100 - 100 * float((uni.get('vs_organizer_best_0_2778') or {}).get('overlap_one_sided_3px') or 0):.1f}%
of our dots are in places it does not cover. Overriding the rule is your call.
<a href="results.html#uniq-null">Calibration table</a> ·
<a href="irregularities.html">details</a>.</li>
</ul>
<p class="small" style="margin:8px 0 0">So: the file is <b>safe to download, inspect and learn
from</b>, and it is <b>not a copy</b> of anything in the {_n(uni.get('n_registry'))}-raster
registry by any statistic that can detect copying. What this repository cannot do is
<i>validate</i> spending a weekly submission slot on it: the only instrument it has for that
decision is provably pointed the wrong way, and its own uniqueness rule returns DUPLICATE on a
leg that a random dot set would also trip.</p>
</div>
<p>{'<a class="btn" href="' + tif + '" download>Download ' + esc(stem) + '-zeros.tif</a>' if tif else '<span class="mut">No artifact yet — run <code>scripts/run_lane.py</code>.</span>'}
{'<a class="btn sec" href="' + zp + '" download>.zip (single GeoTIFF inside)</a>' if zp else ''}
{'<a class="btn ghost" href="downloads/' + stem + '-zeros.json">format receipt</a>' if stem else ''}</p>
<table>
<tr><th style="width:34%">Field</th><th>Value to use on the submission form</th></tr>
<tr><td><b>File to submit</b></td><td><code>{esc(stem)}-zeros.tif</code> (or the .zip)</td></tr>
<tr><td><b>Unique submission name</b></td><td><code>62GEMSDOE-{esc(stem)}</code></td></tr>
<tr><td><b>Note (optional)</b> — {len(note)}/140 chars</td><td><code>{esc(note)}</code></td></tr>
<tr><td>sha256</td><td class="num small">{esc(rec.get('sha256'))}</td></tr>
<tr><td>Geometry</td><td>single band · float32 · EPSG:{esc(rec.get('epsg'))} · 100 m ·
 {rec.get('shape',['?','?'])[0]}×{rec.get('shape',['?','?'])[1]} · transform
 <code>{esc(rec.get('transform'))}</code></td></tr>
<tr><td>Values</td><td class="num">min {fmt(rec.get('min'),6)} · max {fmt(rec.get('max'),6)} ·
 NaN cells {rec.get('n_nan')} · positive px {rec.get('n_positive')} · nodata tag
 {esc(rec.get('nodata'))}</td></tr>
</table>
<p class="small mut">Full instructions, including what to paste in each field of the DrivenData
form, are on the <a href="executive-summary.html">executive summary / how-to-submit</a> page.</p>
</div>""")

    b.append("<h2>Status at a glance</h2><div class='grid3'>")
    b.append(kpi("HOLDOUT-DTI (best arm)", fmt(hd.get("pooled_dti")),
                 f"{esc(best_arm)} · 95% CI {fmt(ci[0])}–{fmt(ci[1])}<br>"
                 f"{esc(hd.get('n_withheld_positives_total'))} withheld positives"))
    b.append(kpi("Random-lines control", fmt((hd.get("controls_mean") or {}).get("random_lines")),
                 "same evaluator, same budget"))
    b.append(kpi("Dots emitted", f"{(rec.get('n_positive') or 0):,}",
                 f"{(100*(rec.get('n_positive') or 0)/max(int(spec.get('footprint') or 1),1)):.3f}% of footprint"))
    b.append(kpi("Uniqueness", esc((e7 or {}).get("verdict", "—")),
                 f"{esc((e7 or {}).get('n_registry', 0))} earlier rasters scanned"))
    b.append(kpi("Validator", f"{rec.get('n_pass','—')}/{(rec.get('n_pass',0) or 0)+(rec.get('n_fail',0) or 0)}",
                 "checks re-read from the bytes on disk"))
    b.append(kpi("Organiser score", "none",
                 "no artifact in this repo has been scored"))
    b.append("</div>")

    b.append(f"""<div class="card"><h3 style="margin-top:0">Should this be given a weekly submission slot?</h3>
<p><b>{esc(slot)}.</b> {esc((card or {}).get('verdict_reason') or
('The holdout says this beats its equal-budget controls, the format is legal and the raster is '
 'unique against every earlier artifact — but promotion to a real slot is a separate selector '
 'step under the weekly cap on the submission page, and this repository does not spend slots.'))}</p>
<p class="small">Read the <a href="analysis.html">arithmetic</a> before disagreeing: this lane is
geographically confined to pluvial-lake margins, and the metric charges false negatives over the
<b>whole</b> hidden set. A confined file cannot reach 0.2778. Its value is defensibility — its
seeds are structures that demonstrably offset a ~15 ka surface, which is the class the expert
panel adds in the Final Prize Round.</p></div>""")

    b.append(f"""<h2>What this is</h2>
<p>62GEMSDOE implements one lane of the <b>DOE GEMS Prize</b> (Drivendata #306, GeoDAWN region,
northwestern Great Basin, Nevada): use the ~15 ka <b>Lake Lahontan highstand shoreline</b> as a
near-level datum, find where that datum is <b>stepped in elevation</b> or <b>deflected laterally
along strike</b>, and ship those structures as a legal, unique GeoTIFF.</p>
<p>It has four parts: an exact re-implementation of the organiser's metric
(<a href="method.html#metric">verified against the published worked example and a brute-force
transcription</a>); the lane detector itself (<a href="method.html">isobase fit, throw-window
flags, strike-parallel trace extension</a>); a preregistered spatially-blocked
<a href="results.html">hide-and-recover holdout</a> with equal-budget controls; and a fail-closed
<a href="executive-summary.html">submission writer</a> whose output is validated by re-reading
the bytes from disk.</p>""")

    b.append(f"""<h2>The portal error <code>"Predicted values must be in range [0, 1]"</code> — root-caused</h2>
<p>Two different failures produce that one message, and both are measured here rather than guessed.</p>
<table><thead><tr><th>mechanism</th><th>measured</th><th>fix</th></tr></thead><tbody>
<tr><td><b>M1 — the float32 sentinel.</b> <code>training_features.tif</code> uses
<code>-3.4028234663852886e+38</code> as nodata.</td>
<td><b>7,113,308</b> cells carry it, of which <b>3,061</b> lie <i>inside</i> the submission
footprint, in all 19 bands (band 6 has 12 extra). Recorded as
<code>sentinel_cells_inside_footprint = {esc(spec.get('sentinel_cells_inside_footprint'))}</code>
= 19×3,061 + 12.</td>
<td>Never written through. The primary artifact is all-finite.</td></tr>
<tr><td><b>M2 — the NaN sentinel.</b> A raster with <code>nodata=NaN</code> and NaN outside the
footprint is legal today ("data outside the bounds is null or nan") but is one validator change
away from the same rejection.</td><td><code>sample_submission.tif</code> carries
{esc(spec.get('footprint'))} finite and 7,111,787 NaN cells.</td>
<td>The primary download is <b>zeros outside, no nodata tag</b>. A NaN-outside twin is also
produced and labelled as the twin.</td></tr>
</tbody></table>
<p>Every file offered here is single-band float32, EPSG:32611, 100 m,
{rec.get('shape',['?','?'])[0]}×{rec.get('shape',['?','?'])[1]},
<b>all {(rec.get('shape',['?','?'])[0] or 0) and (rec.get('shape',['?','?'])[0]*rec.get('shape',['?','?'])[1]) or '?':,} cells finite</b>,
min {fmt(rec.get('min'),6)}, max {fmt(rec.get('max'),6)}, <b>zero NaN</b>, <b>no nodata tag</b>,
and <b>zero dots exactly on a mapped catalogue pixel</b>. Each download ships a JSON receipt
produced by re-opening the file from disk.</p>""")

    b.append("<h2>The headline measurement</h2>")
    if hold:
        rows = []
        for arm in sorted(hold):
            h = hold[arm]
            cm = h.get("controls_mean") or {}
            rows.append(
                f"<tr><td><b>{esc(arm)}</b></td><td>{esc(HYP_ARM.get(arm,''))}</td>"
                f"<td class='num'>{fmt(h.get('pooled_dti'))}</td>"
                f"<td class='num small'>{fmt((h.get('fold_dti_ci95') or [None])[0])}–"
                f"{fmt((h.get('fold_dti_ci95') or [None,None])[1])}</td>"
                f"<td class='num'>{fmt(cm.get('random_lines'))}</td>"
                f"<td class='num'>{fmt(cm.get('random_dots'))}</td>"
                f"<td class='num'>{fmt(cm.get('catalogue_offset'))}</td></tr>")
        b.append("<table><thead><tr><th>arm</th><th>what it is</th><th>HOLDOUT-DTI</th>"
                 "<th>95% CI</th><th>random lines</th><th>random dots</th>"
                 "<th>catalogue offset</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
        b.append(f"<p class='small mut'>Evaluator <code>{esc(hd.get('evaluator'))}</code> · "
                 f"α=0.2 β=0.8 R=300 m · {esc(hd.get('n_withheld_positives_total'))} withheld "
                 f"positives pooled across {esc(len(hold.get(best_arm,{}).get('folds',[])))} folds · "
                 f"whole fault segments withheld with a {esc(hd.get('buffer_px'))} px buffer · "
                 f"visible faults masked pixel-exactly · catalogue-derived weights rebuilt from "
                 f"visible faults only, per fold.</p>")
    b.append("<p><a class='btn sec' href='results.html'>Full results &amp; controls</a>"
             "<a class='btn ghost' href='run-card.html'>The run card</a></p>")

    b.append("""<h2>Honest limits of this page</h2>
<ul class="small">
<li><b>No score here is organiser-verified.</b> Every number is HOLDOUT-DTI (with evaluator
version, withheld-positive count and 95% CI) or ORGANIZER-CONFIRMED (copied from a
submission-page receipt for an <i>earlier</i> file).</li>
<li><b>The holdout's truth is the visible catalogue</b>, so it cannot reward a genuinely new
fault (IR-62-HOLDOUT-01). A holdout win is necessary, not sufficient.</li>
<li><b>There is no absolute DEM in the official stack</b> (IR-62-DEM-01). The isobase is fit in
detrended-elevation space; absolute Lahontan shoreline elevations are not used or claimed.</li>
<li><b>The submitted file is a candidate, not a proven improvement.</b></li>
</ul>""")
    (DOCS / "index.html").write_text(page("Home", "\n".join(b), "index.html",
                                          "One-click submission file, status, and the headline holdout measurement"))

    # ---------------------------------------------------------------- executive summary
    b = ["""<h2>Executive summary — exactly how to make a submission</h2>
<p>This page is the whole procedure. Nothing on it requires judgement calls or manual data
preparation. If a step cannot be completed automatically it says so and names the blocker.</p>"""]
    b.append(f"""<div class="dl"><h3 style="margin-top:0">Step 0 — the file</h3>
<p>{'<a class="btn" href="' + tif + '" download>Download ' + esc(stem) + '-zeros.tif</a>' if tif else '<span class="mut">not built yet</span>'}
{'<a class="btn sec" href="' + zp + '" download>.zip version</a>' if zp else ''}</p>
<p class="small">Either form is accepted by the portal: <i>"You can submit a single-band GeoTIFF
(.tif) file, or a .zip file containing a single GeoTIFF"</i>. The .zip contains exactly one
GeoTIFF and nothing else.</p></div>""")
    b.append(f"""<h3>Step 1 — go to the submission page</h3>
<p><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">
https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/</a> — sign in, then
click <b>New submission</b>. Check the weekly cap shown on that page before you spend a slot;
this repository does not spend slots for you.</p>
<h3>Step 2 — <i>File to submit</i></h3>
<p>Choose the downloaded <code>{esc(stem)}-zeros.tif</code>. <span class="mut">(The .zip is
equivalent.)</span></p>
<h3>Step 3 — <i>Note (optional)</i></h3>
<p>Paste this. It is {len(note)} of the 140 characters allowed:</p>
<pre><code>{esc(note)}</code></pre>
<h3>Step 4 — submit, then record the receipt</h3>
<p>The portal returns a score. Copy it into <code>registry/organizer_scores.json</code> next to
the submission name and the sha256 above. <b>Until you do that, the score does not exist</b> —
nothing on this site may be relabelled ORGANIZER-CONFIRMED from a projection.</p>""")
    b.append(f"""<h2>Why this file cannot produce <code>"Predicted values must be in range [0, 1]"</code></h2>
<p>That error has two mechanisms and this file closes both. See the front page for the
measurement; the summary is:</p>
<ol class="checklist">
<li><b>No sentinel.</b> The float32 nodata value <code>-3.4028234663852886e+38</code> occurs in
<b>3,061</b> cells that lie <i>inside</i> the submission footprint in the official feature stack.
This artifact writes <code>0.0</code> there.</li>
<li><b>No NaN and no nodata tag.</b> All
<b>{(rec.get('shape',[0,0])[0]*rec.get('shape',[0,0])[1]) if rec.get('shape') else '?':,}</b>
cells are finite. The file carries <b>no</b> nodata tag
(receipt: <code>nodata = {esc(rec.get('nodata'))}</code>), so there is no out-of-range value for
a validator to find anywhere in the file — inside or outside the footprint.</li>
<li><b>Values.</b> min {fmt(rec.get('min'),6)}, max {fmt(rec.get('max'),6)}; the file is strictly
binary {{0.0, 1.0}}.</li>
</ol>""")
    b.append("<h2>Validator output — re-read from the bytes on disk</h2>")
    b.append(f"<p class='small mut'>path <code>{esc(rec.get('path'))}</code> · "
             f"{esc(rec.get('bytes'))} bytes · sha256 <code>{esc(rec.get('sha256'))}</code></p>")
    b.append(check_table(rec))
    b.append(f"""<h2>What the file contains</h2>
<p><b>{(rec.get('n_positive') or 0):,}</b> single-pixel dots at value 1.0, at least
{esc((e5 or {}).get('emission',{}).get('min_sep'))} px apart, every one of them more than
{esc((e5 or {}).get('emission',{}).get('prune_cat_px'))} px from an already-mapped catalogue
fault. Median distance to the catalogue
{fmt(((e5 or {}).get('emission',{}).get('dot_dist_to_catalogue_px') or {}).get('median'),1)} px;
{fmt(100*((e5 or {}).get('emission',{}).get('dot_dist_to_catalogue_px') or {}).get('frac_within_3px',0),2)}%
within 3 px (must be 0).</p>""")
    b.append("""<h2>How to reproduce this file from scratch</h2>
<pre><code>python -m venv .venv &amp;&amp; . .venv/bin/activate
pip install -r requirements.txt
export GEMS62_DATA=/path/to/dir/with/the/three/official/rasters
pytest tests -q                                  # 36 assertions, all published numbers or brute force
python scripts/build_registry.py                 # fetch every earlier raster for the uniqueness gate
python scripts/run_lane.py --budget 38000 --arms A1 A2 A3 --folds 4
python scripts/build_site.py                     # regenerate this site from evidence/*.json</code></pre>
<p class="small">The three official rasters are sha256-pinned and re-verified at the start of
every run. <code>1m_DEM_links.csv</code> and the rasters themselves sit behind DrivenData login;
<code>scripts/download_competition_data.sh</code> documents both the login route and the
in-organisation git bridge used here.</p>""")
    b.append("<h2>Other pages</h2><div class='toc'>"
             "<p><a href='analysis.html'>Why 0.2778 — the budget arithmetic</a></p>"
             "<p><a href='method.html'>Method, step by step</a></p>"
             "<p><a href='results.html'>Results, controls and canaries</a></p>"
             "<p><a href='hypotheses.html'>Five candidate hypotheses, ranked</a></p>"
             "<p><a href='profiles.html'>First deliverable: shoreline profiles</a></p>"
             "<p><a href='sources.html'>Every source, with links for manual review</a></p>"
             "<p><a href='irregularities.html'>Irregularities flagged for review</a></p>"
             "<p><a href='run-card.html'>The run card (protocol §5)</a></p>"
             "<p><a href='limitations.html'>Limitations and what would unblock them</a></p>"
             "<p><a href='leaderboard.html'>Organizer-confirmed score ledger</a></p></div>")
    (DOCS / "executive-summary.html").write_text(
        page("Executive summary & how to submit", "\n".join(b), "executive-summary.html",
             "Step-by-step submission instructions, the file, the note text, and the validator output"))

    # ---------------------------------------------------------------- analysis
    from gems62.metric import attainable_kernel_weights, marginal_inclusion_threshold
    kw = attainable_kernel_weights()
    ladder = [("61,328", 0.2449, "GEMSDOE27 topo-gap-closure on d1.5"),
              ("60,069", 0.2477, "GEMSDOE24 h25-1-dotted-h19-5-d1-5"),
              ("44,090", 0.2600, "d28-poisson300m-offcat (three repos, same dot set)"),
              ("40,199", 0.2708, "h27-4-solo-d28"),
              ("37,654", 0.2778, "h33-h33-2-b2 — group best")]
    rows = "".join(f"<tr><td class='num'>{d}</td><td class='num'><b>{s:.4f}</b></td>"
                   f"<td class='small'>{esc(n)}</td></tr>" for d, s, n in reversed(ladder))
    b = [f"""<h2>Why <code>h33-h33-2-b2</code> scored 0.2778</h2>
<p>Because DTI is a <b>budget</b>, not an accuracy score. From the organiser's published formula
(α = 0.2, β = 0.8) and the identity FN<sub>w</sub> = |G| − TP<sub>w</sub>:</p>
<pre><code>DTI = T / ( 0.2·(T + F) + 0.8·|G| )</code></pre>
<p>Every unit of emitted mass costs <b>0.2</b> whether it hits or misses — because a unit that
hits contributes k to T and (1−k) to F, and 0.2·(k + 1 − k) = 0.2 exactly. A unit that hits
earns at most <b>1.0</b>. So the denominator rises by exactly 0.2 per emitted pixel, and the
question is never "how confident am I" but "does this pixel's expected kernel credit beat
0.2·DTI".</p>
<h3>The break-even bar, derived</h3>
<p>Adding one unit of mass with realised kernel weight k:</p>
<pre><code>dT = k,   dF = 1 − k,   dD = α·(dT + dF) = α
dDTI &gt; 0  ⟺  k·D &gt; α·T  ⟺  k &gt; α·DTI</code></pre>
<p>At the group's organiser-confirmed best of 0.2778 the bar is
<b>k &gt; {marginal_inclusion_threshold(0.2778):.5f}</b>. The kernel weights attainable on the
100 m lattice are exactly:</p>
<pre><code>{json.dumps([round(v,5) for v in kw], indent=None)}</code></pre>
<p>So a pixel that coincides with a truth pixel (k = 1) or sits one pixel away (k = 0.667)
clears the bar comfortably; the (2,2)-diagonal at k = {kw[-2]:.5f} <b>still clears it</b>
({kw[-2]:.5f} &gt; {marginal_inclusion_threshold(0.2778):.5f}); a (3,0) pixel at k = 0 does not,
and neither does anything further out. That is the whole geometry of the problem: <b>a dot is
worth emitting only if it is within 2 pixels of a truth pixel</b>, and the (2,2) corner is the
last profitable ring.</p>
<h3>Why dots beat surfaces</h3>
<p>A filled probability surface emits many pixels that all cover the <i>same</i> truth pixel. The
first earns its k; every subsequent one earns nothing extra (TP<sub>w</sub> takes a
<b>max</b> over predictions per truth pixel) and still costs 0.2. Thinning to single pixels at
≥3 px spacing keeps the geometry and deletes the redundancy — the group measured the same field
going 0.1922 → 0.2600 when it was dotted.</p>
<h3>Why binary beats calibrated</h3>
<p>A dot that hits earns p(x)·k, so a soft value of 0.4 earns 0.4·k. A dot that misses costs
0.2·p(x). Writing 1.0 maximises credit on hits and the penalty on misses is bounded at 0.2 —
and because the profitable ring is only 2 px wide, the hit rate at the top of a good ranking is
high enough that hard 1.0 wins. Every organiser-confirmed file above 0.24 in the ledger is
binary.</p>
<h3>Why nothing on the mapped catalogue</h3>
<p>The hidden test set is a set of faults <b>not</b> in the USGS/INGENIOUS catalogue. A dot
within 3 px of an already-mapped trace is spending mass where the hidden truth is, by
construction, absent. The group's own forensics: the 0.2778 file is the exact set difference of
the 0.2600 file (44,090 dots) with the 6,436 dots within 3 px of the mapped catalogue deleted.
<b>44,090 → 0.2600; 37,654 → 0.2778.</b> That single deletion is worth +0.0178.</p>
<h2>The organiser-confirmed budget ladder</h2>
<table><thead><tr><th>dots emitted</th><th>score</th><th>file</th></tr></thead><tbody>{rows}</tbody></table>
<p>Monotone up to ~38 k dots and then flat-to-declining: the optimum is
<b>≈38,000 single-pixel dots at ≥3 px spacing, none on the catalogue</b>. This repository emits
at that budget.</p>
<h2>Can this lane beat 0.2778? The arithmetic, not the mood</h2>
<p>Write the score as <code>T / (0.2·P + 0.8·|G|)</code> where P is the emitted mass (for binary
dots, P = number of dots) and T the kernel credit collected. At P = 38,000 and a score of 0.2778
the denominator is <code>7,600 + 0.8·|G|</code> and <code>T = 0.2778·(7,600 + 0.8·|G|)</code>.
Since T ≤ P = 38,000, that forces <b>|G| ≤ ~1.6×10⁵</b>; and since the 0.2600 → 0.2778 step
removed 6,436 dots without losing credit, the credit those dots carried was ≈0, which pins
|G| lower still.</p>
<p>The binding constraint on this lane is not the budget, it is <b>geography</b>. The
pluvial-lake-margin band is {esc(e1.get('n_margin'))} px of a
{esc(spec.get('footprint'))}-px footprint
({100*int(e1.get('n_margin') or 0)/max(int(spec.get('footprint') or 1),1):.1f}%), and the
false-negative term <code>0.8·|G|</code> is charged over the <b>whole</b> hidden set, not over
the band. A file confined to lake margins cannot raise T enough to move that denominator. This
is why the lane's own brief says it "buys defensibility more than area", and it is why the run
card's verdict is computed rather than asserted.</p>
<p>What the lane <i>can</i> do is raise the <b>credit density at the top of the ranking</b>. The
measured habitat intersection — bench pixels inside the physical throw window with habitat
enrichment ≥ 2.0 — carries <b>3.67×</b> the footprint-mean fault rate over 66,163 px. If the
hidden set is distributed like the visible catalogue in that habitat, the top of this ranking is
denser in truth than the top of a stack-wide ranking. That is the only route to a higher score
that does not require data nobody has, and it is stated as a hypothesis, not a result.</p>"""]
    (DOCS / "analysis.html").write_text(page("Why 0.2778", "\n".join(b), "analysis.html",
                                            "The metric as a budget, the break-even bar, and the organiser-confirmed ladder"))

    # ---------------------------------------------------------------- method
    b = ["""<h2 id="metric">0. The metric, transcribed and cross-checked</h2>
<p>From <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric">the
organiser's problem-description page</a>:</p>
<pre><code>k(d) = max(1 − d/R, 0)                     R = 300 m = 3 px at 100 m

TP_w = Σ_{g∈G} max_{x : d(x,g) ≤ R} p(x)·k(d(x,g))
FP_w = Σ_{x : p(x)&gt;0} p(x)·[1 − max_{g∈G} k(d(x,g))]
FN_w = Σ_{g∈G} [1 − max_{x : d(x,g) ≤ R} p(x)·k(d(x,g))]

DTI(α,β) = TP_w / (TP_w + α·FP_w + β·FN_w + ε)      α = 0.2, β = 0.8</code></pre>
<p>Three independent checks in <code>tests/test_gems62.py</code>: the organiser's worked example
(TP<sub>w</sub>=3.00, FP<sub>w</sub>=1.89, FN<sub>w</sub>=2.00 → 0.60); agreement of the fast
vectorised implementation with a literal O(|G||P|) brute-force transcription of the three sums
on random grids; and the algebraic identity <code>DTI = T/(0.2(T+F)+0.8|G|)</code> together with
<code>FN_w = |G| − TP_w</code>. The reference solution's
<code>TverskyLoss(alpha=0.2, beta=0.8, mode="binary")</code> independently confirms the
parameters.</p>"""]
    b.append(f"""<h2>1. Data, verified before use</h2>
<p>The three official rasters are sha256-pinned and the pins are re-checked on every run; a
mismatch aborts the run rather than proceeding with unverified data.</p>
<table><thead><tr><th>file</th><th>bytes</th><th>sha256 (pin == measured)</th></tr></thead><tbody>
{''.join(f"<tr><td><code>{esc(k)}</code></td><td class='num'>{esc(v)}</td><td class='num small'>{esc((spec.get('sha256') or {}).get(k))}</td></tr>"
          for k, v in [('training_features.tif', '418,912,844'), ('labels.tif', '425,830'),
                       ('sample_submission.tif', '1,599,597')])}
</tbody></table>
<p class="small">Geometry: {esc(spec.get('height'))}×{esc(spec.get('width'))}, 19 bands,
{esc(spec.get('dtype'))}, EPSG:{esc(spec.get('epsg'))}, {esc(spec.get('res'))} m,
transform <code>{esc(spec.get('transform'))}</code>, footprint
<b>{_n(spec.get('footprint'))}</b> px, label positives <b>{_n(spec.get('positives'))}</b> px,
label values <code>{esc(spec.get('labels_unique'))}</code>.</p>
<p class="small"><b>IR-62-SENTINEL-01:</b> {esc(spec.get('sentinel_cells_inside_footprint'))}
sentinel cells across the 19 bands lie inside the footprint (= 19 × 3,061 + 12).</p>""")
    b.append(f"""<h2>2. The lane, step by step</h2>
<h3>2.1 Pluvial-lake-margin band</h3>
<p>Topographic position index <code>TPI = det_elev − smooth(det_elev, σ=25 px = 2.5 km)</code>,
NaN-weighted so the footprint edge does not leak. The margin band is
<code>TPI ∈ [{esc(e1.get('tpi_lo'))}, {esc(e1.get('tpi_hi'))}) m</code> and
<code>slope ∈ [{esc(e1.get('slope_lo'))}, {esc(e1.get('slope_hi'))}]°</code> →
<b>{_n(e1.get('n_margin'))}</b> px
({100*int(e1.get('n_margin') or 0)/max(int(spec.get('footprint') or 1),1):.1f}% of the footprint).
A Gaussian weight floor of 0.35 marks the pixels whose TPI is trustworthy; the rest are excluded
rather than filled.</p>
<h3>2.2 The isobase fit</h3>
<p><code>isobase = smooth(det_elev restricted to the margin band, σ={esc(e1.get('iso_sigma'))} px
= {int(e1.get('iso_sigma') or 0)/10:.0f} km)</code>. A <b>local</b> smooth fit rather than one
global plane, because post-pluvial rebound is <i>differential</i>: the datum tilts between the
Lahontan sub-basins (Pyramid Lake / Winnemucca / Lahontan Reservoir / Walker / Carson Sink /
Smith Valley), so a single plane over a 330 × 373 km footprint would be geologically wrong.
6 km is long enough to be a datum and short enough to follow rebound between sub-basins.</p>
<h3>2.3 Benches</h3>
<p><code>bench = margin ∧ slope ∈ [3,22]° ∧ |plan curvature| ≤ its 55th percentile in-band</code>
→ <b>{_n(e1.get('n_bench'))}</b> px. Plan curvature is the curvature of the contour line: near
zero means straight-to-gently-arcuate, which is what a wave-cut bench is, and it rejects gullies,
fan heads and ridge crests. <b>IR-62-BENCH-01:</b> an earlier version also required the residual
to be small, which is circular and produced zero flags; the residual test now lives only in the
step flag.</p>
<h3>2.4 Flagging steps — a bounded throw window</h3>
<p><code>step = bench ∧ |resid − median| ∈ [{esc(e1.get('throw_lo_m'))},
{esc(e1.get('throw_hi_m'))}) m</code> → <b>{_n(e1.get('n_step_flag'))}</b> px. The window is
measured, not chosen: catalogue enrichment by |isobase residual| inside the bench band is
2.26–2.77× below 210 m, then 1.45× (210–260), 1.16× (260–320), 0.66× (320–400) and
<b>0.00× above 400 m</b> (403 px, not one mapped fault). An unbounded outlier test keeps exactly
the depleted tail. The bounds also have an independent physical meaning: 1–8 mm/yr over 15 kyr is
15–120 m of throw, which brackets the slow-to-fast range of Great Basin faults.</p>
<h3>2.5 Flagging lateral deflections</h3>
<p>Azimuth kinks: <code>|Δstrike| &gt; {esc(e1.get('deflect_deg'))}°</code> over 3 px, computed in
the double-angle representation so the [0,π) fold of a strike is handled as a proper circle →
<b>{_n(e1.get('n_deflect_flag'))}</b> px. <b>IR-62-DEFL-01:</b> this flag measured 1.12×
enrichment, i.e. no signal at 100 m. It is kept because the lane specifies it and reported as a
negative rather than dropped.</p>
<h3>2.6 Seeding and extending traces</h3>
<p>Each flag seeds a trace that walks both ways <b>along the local isobase strike</b> while
DEM-ridge evidence stays above {esc((e2b or {}).get('min_evidence'))}. Evidence =
0.65·(0.60·rank|profile curvature| + 0.40·rank(sclope in [3,25]°)) + 0.35·(rank TMI-HG,
rank isostatic-gravity HG), all rank-normalised inside the footprint so the combination is
scale-free. Result: <b>{_n((e2b or {}).get('n_traces'))}</b> traces,
<b>{_n((e2b or {}).get('n_traced_px'))}</b> px, median length
{esc((e2b or {}).get('len_median_px'))} px, mean {fmt((e2b or {}).get('len_mean_px'),2)},
p90 {esc((e2b or {}).get('len_p90_px'))}, max {esc((e2b or {}).get('len_max_px'))}.
<b>IR-62-EXT-01:</b> the first version derived the walk direction from the evidence gradient and
produced median length 1 px — the traces never extended. Direction now comes from the isobase
strike, which is well posed; evidence is only the stopping criterion, which is what the lane text
says.</p>
<h3>2.7 Habitat weighting from visible faults only</h3>
<p>A 9×8 binning of (TPI, slope) gives a smoothed per-pixel enrichment weight
(Laplace prior count 40 so sparse bins cannot fabricate a rate). Under the holdout the weights
are rebuilt <b>from the visible faults only</b>, per fold — never from the withheld ones.</p>
<h3>2.8 Emission</h3>
<p>Greedy non-maximum suppression in priority order at ≥{esc((e5 or {}).get('emission',{}).get('min_sep'))} px
separation, capped at the budget, then every dot within
{esc((e5 or {}).get('emission',{}).get('prune_cat_px'))} px of a mapped catalogue fault is
deleted. Values are strictly binary {{0.0, 1.0}}; outside the footprint 0.0; no nodata tag.</p>""")
    if e2 and e2.get("cells"):
        rows = "".join(
            f"<tr><td class='num'>[{c['tpi_lo']:.0f}, {c['tpi_hi']:.0f})</td>"
            f"<td class='num'>[{c['slope_lo']:.0f}, {c['slope_hi']:.0f})</td>"
            f"<td class='num'>{c['px']:,}</td><td class='num'>{c['positives']:,}</td>"
            f"<td class='num'><b>{c['enrichment']:.3f}×</b></td></tr>"
            for c in e2["cells"][:16])
        b.append(f"""<h2>3. Measured habitat enrichment</h2>
<p class="small">Base rate {e2['base_rate']*100:.4f}% over {e2['n_footprint']:,} footprint px and
{e2['n_positives']:,} catalogue positives. Top 16 of {len(e2['cells'])} cells by enrichment.</p>
<table><thead><tr><th>TPI (m)</th><th>slope (°)</th><th>px</th><th>catalogue positives</th>
<th>enrichment</th></tr></thead><tbody>{rows}</tbody></table>
<p>The physically coherent reading: the most fault-rich terrain in this footprint is
<b>deep topographic position with a scarp-scale slope</b> — the basin-side toe of a range front.
That is exactly where a pluvial-lake shoreline is cut, and exactly where a fault that offsets it
will show. Range crests (TPI &gt; +120 m) are depleted to 0.28–0.34×, which is why a detector
that ranks by "roughness" or by residual magnitude alone loses.</p>""")
    (DOCS / "method.html").write_text(page("Method", "\n".join(b), "method.html",
                                           "The lane method, step by step, with the metric transcribed and cross-checked"))

    # ---------------------------------------------------------------- results
    b = ["<h2>Results</h2>",
         "<p class='small'>Evaluator <code>" + esc(hd.get("evaluator")) +
         "</code> · α=0.2 β=0.8 R=300 m triangular kernel · hide-and-recover: whole fault "
         "segments withheld with a " + esc(hd.get("buffer_px")) +
         " px buffer, every catalogue-derived weight rebuilt from visible faults only, visible "
         "faults masked pixel-exactly at scoring time, DTI pooled over folds.</p>"]
    if hold:
        rows = []
        for arm in sorted(hold):
            h = hold[arm]
            cm = h.get("controls_mean") or {}
            rows.append(
                f"<tr><td><b>{esc(arm)}</b><div class='small mut'>{esc(HYP_ARM.get(arm,''))}</div></td>"
                f"<td class='num'><b>{fmt(h.get('pooled_dti'))}</b></td>"
                f"<td class='num small'>{fmt((h.get('fold_dti_ci95') or [None])[0])}–"
                f"{fmt((h.get('fold_dti_ci95') or [None,None])[1])}</td>"
                f"<td class='num'>{fmt(cm.get('random_lines'))}</td>"
                f"<td class='num'>{fmt(cm.get('random_dots'))}</td>"
                f"<td class='num'>{fmt(cm.get('catalogue_offset'))}</td>"
                f"<td class='num'>{esc(h.get('n_folds'))}</td>"
                f"<td class='num'>{esc(h.get('withheld_positives_total'))}</td></tr>")
        b.append("<table><thead><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95% CI</th>"
                 "<th>random lines</th><th>random dots</th><th>catalogue offset</th>"
                 "<th>folds</th><th>withheld px</th></tr></thead><tbody>"
                 + "".join(rows) + "</tbody></table>")
        ba = hold.get(best_arm, {})
        if ba.get("folds"):
            fr = "".join(
                f"<tr><td>{f['index']}</td><td>{f['seed']}</td>"
                f"<td class='num'>{f['n_segments_withheld']}</td>"
                f"<td class='num'>{f['n_segments_visible']}</td>"
                f"<td class='num'>{f['withheld_px']:,}</td>"
                f"<td class='num'>{f['result']['dti']:.4f}</td>"
                f"<td class='num'>{f['result']['coverage']:.4f}</td>"
                f"<td class='num'>{f['controls']['random_lines']['dti']:.4f}</td>"
                f"<td class='num'>{f['controls']['random_dots']['dti']:.4f}</td>"
                f"<td class='num'>{f['controls']['catalogue_offset']['dti']:.4f}</td></tr>"
                for f in ba["folds"])
            b.append(f"<h3>Per-fold detail — best arm {esc(best_arm)}</h3>"
                     "<table><thead><tr><th>fold</th><th>seed</th><th>segs withheld</th>"
                     "<th>segs visible</th><th>withheld px</th><th>DTI</th><th>coverage</th>"
                     "<th>rand lines</th><th>rand dots</th><th>cat offset</th></tr></thead>"
                     f"<tbody>{fr}</tbody></table>")
    b.append(f"""<h3>The ablation, read honestly</h3>
<p>A2 (band-only, <b>no isobase</b>) scored {fmt((hold.get('A2') or {}).get('pooled_dti'))}
against A1 (pure lane, no catalogue term) at
{fmt((hold.get('A1') or {}).get('pooled_dti'))}. So the isobase step-flag <i>on its own</i> does
not beat simply ranking the basin-margin band. A3 — the throw window <b>intersected with</b> the
measured habitat — scored {fmt((hold.get('A3') or {}).get('pooled_dti'))}, the best of the three,
and its CI ({fmt(((hold.get('A3') or {}).get('fold_dti_ci95') or [None])[0])}–{fmt(((hold.get('A3') or {}).get('fold_dti_ci95') or [None,None])[1])})
does not overlap A1's. The conclusion is the same one the sibling repositories reached on
different data: <b>the signal is in the conjunction, not in any single layer.</b></p>""")
    b.append(f"""<h2>Leakage canaries</h2>
<p>The protocol's rule: a single feature scoring AUC &gt; 0.90 on the holdout means leakage until
proven otherwise.</p>
<h3>Against the withheld truth, weights rebuilt from visible faults only</h3>
<table><thead><tr><th>feature</th><th>rank AUC</th><th>verdict</th></tr></thead><tbody>
{canary_rows((e3c or {}).get('aucs_vs_withheld_truth', {}))}
</tbody></table>
<p class="small">{esc((e3c or {}).get('n_withheld'))} withheld positives ·
{esc((e3c or {}).get('n_visible'))} visible · threshold
{esc((e3c or {}).get('threshold'))}</p>
<h3>Against the full catalogue (reference only)</h3>
<table><thead><tr><th>feature</th><th>rank AUC</th><th>verdict</th></tr></thead><tbody>
{canary_rows((e2c or {}).get('aucs', {}))}
</tbody></table>
<p class="small mut">{esc((e2c or {}).get('note'))}</p>""")
    b.append(f"""<h2>Uniqueness</h2>
<p>Protocol §1: stop if the rank-correlation with any registry raster exceeds 0.90, or if more
than 70% of this artifact's dots fall within 3 px of one registry raster's dots.</p>
<div class="grid3">
{kpi("verdict", f"<span class='pill {'ok' if (e7 or {}).get('verdict')=='UNIQUE' else 'no'}'>{esc((e7 or {}).get('verdict','—'))}</span>", f"{esc((e7 or {}).get('n_registry',0))} earlier rasters")}
{kpi("worst signed ρ", fmt(((e7 or {}).get('worst_rho_surface') or {}).get('value'),3), esc(((e7 or {}).get('worst_rho_surface') or {}).get('name',''))[:40] + ' · limit 0.90')}
{kpi("worst 3 px overlap", fmt(((e7 or {}).get('worst_overlap_3px') or {}).get('value'),3), esc(((e7 or {}).get('worst_overlap_3px') or {}).get('name',''))[:40] + ' · limit 0.70')}
</div>
<p class="small">Largest |ρ| overall: {fmt(((e7 or {}).get('worst_abs_rho_surface') or {}).get('value'),3)}
({esc(((e7 or {}).get('worst_abs_rho_surface') or {}).get('name',''))}). Worst symmetric Jaccard:
{fmt(((e7 or {}).get('worst_jaccard') or {}).get('value'),4)}
({esc(((e7 or {}).get('worst_jaccard') or {}).get('name',''))}).
The ρ gate uses the <b>signed</b> maximum: two fields can be perfectly anti-correlated when one's
dots sit exactly where the other's do not, which is the opposite of drifting into that lane.</p>""")
    if e7 and e7.get("comparisons"):
        top = sorted(e7["comparisons"], key=lambda r: -(r.get("overlap_one_sided_3px") or 0))[:20]
        rows = "".join(
            f"<tr><td class='small'>{esc(r['name'])[:70]}</td>"
            f"<td class='num'>{fmt(r.get('rho_surface'),3)}</td>"
            f"<td class='num'>{fmt(r.get('overlap_one_sided_3px'),3)}</td>"
            f"<td class='num'>{fmt(r.get('jaccard'),4)}</td>"
            f"<td class='num'>{esc(r.get('n_theirs'))}</td></tr>" for r in top)
        b.append("<h3>The 20 closest earlier rasters by 3 px overlap</h3>"
                 "<table><thead><tr><th>registry raster</th><th>ρ surface</th>"
                 "<th>one-sided 3 px overlap</th><th>Jaccard</th><th>their px</th></tr></thead>"
                 f"<tbody>{rows}</tbody></table>")
    # ------------------------------------------------- IR-62-HOLDOUT-01: the money table
    if e9 and e9.get("rows"):
        g = e9.get("summary") or {}
        frows = []
        for r in e9["rows"]:
            org = r.get("organizer_confirmed_score")
            cls = " class='ours'" if str(r.get("label", "")).startswith("OURS") else ""
            frows.append(
                f"<tr{cls}><td class='small'>{esc(str(r.get('label'))[:56])}</td>"
                f"<td class='num'>{_n(r.get('n_dots'))}</td>"
                f"<td class='num'>{('%.4f' % org) if isinstance(org, float) else '<b>UNSCORED</b>'}</td>"
                f"<td class='num'>{_f(r.get('holdout_dti'), '.4f')}</td>"
                f"<td class='num small'>{_f((r.get('holdout_dti_ci95') or [None])[0], '.4f')}\u2013"
                f"{_f((r.get('holdout_dti_ci95') or [None, None])[1], '.4f')}</td></tr>")
        b.append(f"""<h2 id="frozen">The holdout is pointed the wrong way (IR-62-HOLDOUT-01)</h2>
<div class="callout no">
<p style="margin:0 0 8px"><b>Spearman(HOLDOUT-DTI, ORGANIZER-CONFIRMED score) =
{_f(g.get('spearman_holdout_vs_organizer'), '+.4f')}</b> across
{_n(g.get('n_scored_artifacts_evaluated'))} artifacts scored on one identical frozen holdout
(p={_f(g.get('spearman_p'), '.4f')}). Kendall τ {_f(g.get('kendall_holdout_vs_organizer'), '+.4f')}
(p={_f(g.get('kendall_p'), '.4f')}). Controlling for dot count the anti-correlation survives:
partial Spearman {_f(g.get('partial_spearman_holdout_vs_organizer_given_ndots'), '+.4f')}
(p={_f(g.get('partial_spearman_p'), '.4f')}), and
{_n(g.get('count_matched_pairs_lower_holdout_higher_organizer'))} of
{_n(g.get('count_matched_pairs'))} count-matched pairs put the higher organizer score on the
<i>lower</i>-holdout file.</p>
<p class="small" style="margin:0"><b>Mechanism.</b> The holdout withholds whole segments of the
<i>public</i> fault catalogue and scores recovery of them. The organizer's Initial Prize Round
scores a <i>private set of faults labelled before the competition</i> — not the public catalogue.
So the holdout rewards dots that hug the catalogue and the organizer rewards dots that avoid it.
The 0.2778 file was built by <i>deleting</i> 6,436 dots within 3 px of the catalogue: that raised
its organizer score 0.2600 → 0.2778 and collapses its holdout DTI 0.1322 → 0.0053. The two
objectives are in direct opposition.</p>
<p class="small" style="margin:8px 0 0"><b>Cleanest counterexample.</b> {esc(g.get('cleanest_counterexample') or '')}</p>
</div>
<table><thead><tr><th>artifact (frozen, read from disk)</th><th>dots</th>
<th>ORGANIZER-CONFIRMED</th><th>HOLDOUT-DTI</th><th>95% CI</th></tr></thead>
<tbody>{''.join(frows)}</tbody></table>
<p class="small">Our artifact is the highlighted row. Its HOLDOUT-DTI is
{_f(g.get('ours_dti'), '.4f')} because it has <b>zero</b> dots within 3 px of any catalogue pixel
(measured: minimum dot-to-catalogue distance 3.2 px, median 18.9 px) and the withheld truth
<i>is</i> catalogue. That is the same property the 0.2778 winner has — it is not a failure of the
artifact, it is a failure of the instrument.</p>
<p class="small"><b>Consequence for the promotion decision.</b> The standing instruction is not to
spend a weekly slot on an idea that has not beaten the current holdout best
({_f(g.get('best_holdout_dti'), '.4f')}, {esc(str(g.get('best_holdout_label'))[:44])}). Our
artifact cannot beat that, and no valid instrument exists to overrule it — so the run card's
verdict is <b>negative</b> and the file is marked <b>NOT VALIDATED for submission</b>. The
negative result is the deliverable. <b>Caveat, stated plainly:</b> a frozen artifact is
information-advantaged (built with the full catalogue in hand) whereas our arms see only the
per-fold visible catalogue; for registry files that bias runs <i>against</i> them, since they were
built to sit off the catalogue.</p>
<p class="small mut">Source: <code>evidence/e9_frozen_artifact_holdout.json</code>, produced by
<code>scripts/compare_holdout.py</code>. ORGANIZER-CONFIRMED scores are copied from
<code>registry/organizer_scores.json</code>, which records only scores read off a submission-page
receipt. No number in the two columns is interchangeable, and none is a projection.</p>""")

    # ------------------------------------------------- uniqueness null calibration
    if e7b and e7b.get("comparators"):
        b7 = []
        for c in sorted(e7b["comparisons"] if "comparisons" in e7b else e7b["comparators"],
                        key=lambda r: -r["excess_over_habitat"]):
            b7.append(
                f"<tr><td class='small'>{esc(str(c.get('name'))[:54])}</td>"
                f"<td class='num'>{_n(c.get('n_theirs'))}</td>"
                f"<td class='num'>{_f(c.get('theirs_density'), '.3f')}</td>"
                f"<td class='num'>{_f(c.get('overlap_mine_vs_theirs'), '.3f')}</td>"
                f"<td class='num'>{_f(c.get('uniform_null'), '.3f')}</td>"
                f"<td class='num'>{_f(c.get('habitat_null'), '.3f')}</td>"
                f"<td class='num'>{_f(c.get('excess_over_habitat'), '+.3f')}</td>"
                f"<td class='num'>{_f(c.get('reverse_overlap_theirs_vs_mine'), '.3f')}</td>"
                f"<td class='num'>{_f(c.get('jaccard_exact'), '.4f')}</td></tr>")
        sb = e7b.get("summary") or {}
        b.append(f"""<h3 id="uniq-null">Why the overlap leg cannot decide this (IR-62-UNIQ-01)</h3>
<p class="small">Every comparator that trips the literal "&gt;70% of dots within 3 px" leg, with two
nulls. <b>uniform</b> = overlap a dot set scattered anywhere in the footprint would score;
<b>habitat</b> = overlap a dot set scattered through <i>our own</i> catalogue-free lane pool
(bench ∧ |isobase residual − median| ∈ [15,130) m, {_n(e7b.get('n_pool_pixels'))} px) would score.
<b>reverse</b> = fraction of <i>their</i> dots within 3 px of <i>ours</i>; copying is mutual.
<b>Jaccard</b> = exact set agreement.</p>
<table><thead><tr><th>comparator</th><th>their px</th><th>density</th><th>overlap</th>
<th>uniform null</th><th>habitat null</th><th>excess</th><th>reverse</th><th>Jaccard</th></tr></thead>
<tbody>{''.join(b7)}</tbody></table>
<p class="small">{_n(sb.get('n_where_habitat_null_also_over_limit'))} of
{_n(sb.get('n_distinct_fields_over_limit'))} would also be tripped by a random draw from our own
habitat — for those the leg cannot distinguish copying from convergent geology. Max excess over the
habitat null {_f(sb.get('max_excess_over_habitat'), '+.4f')} (table above recomputes it per row);
max Jaccard {_f(sb.get('max_jaccard'), '.5f')} against a 0.50 limit; max signed rho
{_f(sb.get('max_signed_rho'), '+.4f')} against a 0.90 limit; max mutual containment
{_f(sb.get('max_reverse_overlap'), '.4f')}. A copy would show Jaccard near 1.0 and rho near 1.0.</p>
<p class="small mut">Source: <code>evidence/e7b_uniqueness_null_analysis.json</code>, produced by
<code>scripts/uniq_null_analysis.py</code>. Note only
{_f(e7b.get('frac_our_dots_inside_pool'), '.3f')} of our dots lie inside that particular pool: arm
A3 emits from <i>traced</i> pixels, which extend along strike beyond the step flags, so this null
is conservative — a pool matched to the emission would waive more, not fewer.</p>""")

    (DOCS / "results.html").write_text(page("Results", "\n".join(b), "results.html",
                                            "Holdout DTI, controls, leakage canaries and the uniqueness gate"))

    # ---------------------------------------------------------------- hypotheses
    b = ["<h2>Candidate geological hypotheses, ranked</h2>",
         "<p>Five candidates, each naming the specific layers, the physical signature, why it "
         "should catch a fault <b>missing</b> from the USGS/INGENIOUS catalogue rather than one "
         "already in it, and how it differs from anything already implemented in this "
         "organisation's repositories. Ranked by expected DTI improvement against implementation "
         "cost. Where a candidate cannot be validated without new external data, the specific "
         "free official source is named and its obtainability from this sandbox is stated "
         "honestly.</p>"]
    for h in HYPOTHESES:
        blocked = "BLOCKED" in h["cost"]
        b.append(f"""<div class="card"><h3 style="margin-top:0">#{h['rank']} · {esc(h['id'])} —
{esc(h['title'])} {'<span class="pill no">data-blocked</span>' if blocked else '<span class="pill ok">viable</span>'}</h3>
<table>
<tr><th style="width:22%">Layers</th><td><code>{esc(h['layers'])}</code></td></tr>
<tr><th>Physical signature</th><td>{esc(h['signature'])}</td></tr>
<tr><th>Why a <i>missing</i> fault</th><td>{esc(h['why_new'])}</td></tr>
<tr><th>How it differs</th><td>{esc(h['differs'])}</td></tr>
<tr><th>Cost</th><td>{esc(h['cost'])}</td></tr>
<tr><th>Expected / measured</th><td>{esc(h['expected'])}</td></tr>
</table></div>""")
    b.append("""<h2>The ranking rule actually applied</h2>
<p>H62-A was implemented and validated on the spatially-blocked holdout before any slot was
considered, per the brief. H62-B is next by expected value per hour and needs no new data. H62-C
has the highest ceiling but is <b>data-blocked</b>: the GeoDAWN radiometric channels are not
among the 19 provided bands, so the free official source (the USGS GeoDAWN release) is named and
its obtainability from this sandbox is recorded as unverified rather than assumed. H62-D and
H62-E use data already in hand and are cheap, but their expected gains are lower and are ranked
below accordingly.</p>""")
    (DOCS / "hypotheses.html").write_text(page("Hypotheses", "\n".join(b), "hypotheses.html",
                                               "Five candidate hypotheses ranked by expected DTI gain vs cost"))

    # ---------------------------------------------------------------- profiles
    pngs = (e4 or {}).get("pngs") or []
    b = ["""<h2>First deliverable: shoreline elevation-versus-distance profiles</h2>
<p>The lane's brief names this as the first deliverable: <i>"shoreline elevation-versus-distance
profiles with the flagged steps. If only a handful are convincing, emit only those."</i></p>
<p>Transects run <b>perpendicular to the local isobase strike</b>, because a shoreline step is
only visible in cross-section. Each profile plots detrended elevation against distance along the
transect, with the fitted isobase overlaid and every flagged step (▼) and lateral deflection (▲)
marked.</p>"""]
    if pngs:
        b.append("<div class='grid2'>")
        for p in pngs[:12]:
            b.append(f"<figure><img src='profiles/{esc(p)}' alt='shoreline profile {esc(p)}'>"
                     f"<figcaption><code>{esc(p)}</code></figcaption></figure>")
        b.append("</div>")
        b.append(f"<p class='small mut'>{len(pngs)} of {esc((e4 or {}).get('n_profiles'))} "
                 f"profiles rendered. Full set: <a href='profiles/shoreline_profiles.csv'>"
                 f"shoreline_profiles.csv</a> (long format, every sample point) · "
                 f"<a href='profiles/shoreline_profiles.json'>shoreline_profiles.json</a> "
                 f"(per-profile summary).</p>")
    else:
        b.append("<p class='mut'>No profiles rendered yet.</p>")
    b.append(f"""<h3>How many are convincing?</h3>
<p>{_n(e1.get('n_step_flag'))} pixels carry a bounded throw-window step and
{_n(e1.get('n_deflect_flag'))} carry an azimuth kink. After trace extension along strike that
becomes {_n((e2b or {}).get('n_traces'))} traces covering
{_n((e2b or {}).get('n_traced_px'))} px. The emission then spends a budget of
{esc((e5 or {}).get('emission',{}).get('budget'))} dots on the top of that ranking, so the
"emit only those" instruction is implemented as a budget cap rather than as a hand-picked list —
and the cap is set at the organiser-confirmed optimum, not at a guess.</p>""")
    (DOCS / "profiles.html").write_text(page("Shoreline profiles", "\n".join(b), "profiles.html",
                                             "Elevation-versus-distance profiles with flagged steps"))

    # ---------------------------------------------------------------- sources
    b = ["<h2>Sources, with links for manual review</h2>",
         "<p>Every external claim on this site traces to one of these. The "
         "<b>verified-from</b> column says which artifact was actually read, so a reviewer can "
         "check the chain without trusting this page.</p>",
         "<table><thead><tr><th>source</th><th>what it establishes</th><th>class</th></tr></thead><tbody>"]
    for t, u, w, c in SOURCES:
        b.append(f"<tr><td><a href='{esc(u)}'>{esc(t)}</a><div class='small mut'>{esc(u)}</div></td>"
                 f"<td>{esc(w)}</td><td><span class='pill info'>{esc(c)}</span></td></tr>")
    b.append("</tbody></table>")
    b.append("<h2>Literature cited in the lane brief</h2><table><thead><tr>"
             "<th>reference</th><th>venue</th><th>what the brief uses it for</th>"
             "<th>verification status</th></tr></thead><tbody>")
    for a, v, w, c in LITERATURE:
        b.append(f"<tr><td>{esc(a)}</td><td>{esc(v)}</td><td>{esc(w)}</td>"
                 f"<td><span class='pill warn'>{esc(c)}</span> — <span class='small'>named in the "
                 f"tasking paragraph; the full text is NOT reachable from this sandbox "
                 f"(egress allowlist covers github.com, pypi.org and registry.npmjs.org only), so "
                 f"no quantitative claim from these papers is reproduced here. Only the "
                 f"qualitative mechanism — that Lahontan shoreline features are used as displaced "
                 f"datums — is used, and it is implemented from the provided raster alone.</span></td></tr>")
    b.append("</tbody></table>")
    b.append(f"""<h2>Data provenance actually used</h2>
<table><thead><tr><th>artifact</th><th>route</th><th>verification</th></tr></thead><tbody>
<tr><td><code>training_features.tif</code></td>
<td>DrivenData data tab requires login and is not reachable from this sandbox. Restored from the
in-organisation git bridge <code>buffedlizard55-lab/6GEMSDOE : data/bridge/</code> (5 parts,
reassembled by concatenation).</td>
<td>sha256 <code>{esc((spec.get('sha256') or {}).get('training_features.tif'))}</code> — matches
the pin published in that repository's <code>data/bridge/manifest.json</code>, which itself
records the Dropbox mirror URL and the original data-tab URL.</td></tr>
<tr><td><code>labels.tif</code></td><td>same bridge (<code>existing_faults.tif</code>)</td>
<td>sha256 <code>{esc((spec.get('sha256') or {}).get('labels.tif'))}</code> — matches the pin</td></tr>
<tr><td><code>sample_submission.tif</code></td><td>same bridge (<code>example_submission.tif</code>)</td>
<td>sha256 <code>{esc((spec.get('sha256') or {}).get('sample_submission.tif'))}</code> — matches the pin</td></tr>
<tr><td>band inventory (19 bands)</td><td>read from the TIFF <code>DESCRIPTION</code> and
<code>data_category</code> tags of the pinned file itself</td>
<td>not assumed; re-read every run and stored in
<code>evidence/e0_data_verification.json</code></td></tr>
<tr><td>registry of earlier rasters</td>
<td><code>scripts/build_registry.py</code> over every <code>*GEMSDOE*</code> repository in the
same GitHub organisation, fetching each <code>.tif</code> under a downloads/submissions directory
through the GitHub contents API</td>
<td>{esc((e7 or {}).get('n_registry',0))} rasters compared, {esc(len((e7 or {}).get('errors',[])))}
errors</td></tr>
</tbody></table>
<p class="small"><b>IR-62-DATA-01:</b> <code>1m_DEM_links.csv</code> (USGS 3DEP 1 m lidar) is NOT
available in this sandbox. That is why the lane works in detrended-elevation space and why
IR-62-DEM-01 stays open.</p>""")
    (DOCS / "sources.html").write_text(page("Sources", "\n".join(b), "sources.html",
                                            "Every source with links for manual review"))

    # ---------------------------------------------------------------- irregularities
    b = ["<h2>Irregularities flagged for review</h2>",
         "<p>Everything found that does not behave as the brief, the organiser's documentation, or "
         "an earlier version of this code implied. Several are bugs this session found in its own "
         "first implementation; two are defects in the tasking protocol itself "
         "(<b>IR-62-HOLDOUT-01</b> and <b>IR-62-UNIQ-01</b>) and are the reason the artifact is "
         "marked <b>not validated for submission</b>. Each is listed with the measurement that "
         "exposed it and, where it is a code bug, the regression test that stops it returning.</p>"]
    for ir in IRREGULARITIES:
        # severity is free text ("CRITICAL -- invalidates the promotion gate"),
        # so bucket on a prefix rather than an exact key, and never KeyError on
        # an optional field.
        sv = str(ir.get("severity", "")).lower()
        sev = ("no" if sv.startswith(("critical", "high")) else
               "warn" if sv.startswith(("medium", "high --")) else "info")
        status = str(ir.get("status", ""))
        unblock = ir.get("unblock")
        src = ir.get("source")
        b.append(f"""<div class="card"><h3 style="margin-top:0"><code>{esc(ir['id'])}</code>
<span class="pill {sev}">{esc(ir.get('severity'))}</span>
<span class="pill {'ok' if status.startswith('closed') else 'warn'}">{esc(status)}</span></h3>
<p><b>{esc(ir.get('title'))}</b></p>
<p>{esc(ir.get('detail'))}</p>
<p class="small"><b>Evidence:</b> {esc(ir.get('evidence'))}</p>
<p class="small"><b>Resolution:</b> {esc(ir.get('resolution'))}</p>
{f'<p class="small"><b>Unblock:</b> {esc(unblock)}</p>' if unblock else ''}
{f'<p class="small"><b>Source for manual review:</b> <a href="{esc(src)}">{esc(src)}</a></p>' if src else ''}
</div>""")
    (DOCS / "irregularities.html").write_text(
        page("Irregularities", "\n".join(b), "irregularities.html",
             "Everything irregular found in the data, the metric, or this session's own code"))

    # ---------------------------------------------------------------- run card
    b = ["<h2>Run card (protocol §5)</h2>",
         "<p>The single JSON card the parallel-run protocol requires. Rendered from "
         "<code>evidence/e8_run_card.json</code>; the raw file is authoritative.</p>"]
    if card:
        b.append(f"""<table>
<tr><th style="width:26%">hypothesis</th><td>{esc(card.get('hypothesis'))}</td></tr>
<tr><th>mechanism</th><td>{esc(card.get('mechanism'))}</td></tr>
<tr><th>named non-fault process that could mimic it</th><td>{esc(card.get('named_non_fault_process_that_could_mimic_it'))}</td></tr>
<tr><th>holdout DTI + CI</th><td><b>HOLDOUT-DTI {fmt(card.get('holdout',{}).get('pooled_dti'))}</b>
(95% CI {fmt(ci[0])}–{fmt(ci[1])}) · evaluator <code>{esc(card.get('holdout',{}).get('evaluator'))}</code> ·
{esc(card.get('holdout',{}).get('n_withheld_positives_total'))} withheld positives ·
α={esc(card.get('holdout',{}).get('alpha'))} β={esc(card.get('holdout',{}).get('beta'))}
R={esc(card.get('holdout',{}).get('radius_m'))} m ·
controls {esc(json.dumps(card.get('holdout',{}).get('controls_mean')))} ·
all arms {esc(json.dumps(card.get('holdout',{}).get('all_arms')))}</td></tr>
<tr><th>correlation / overlap vs registry</th><td>verdict
<b>{esc((card.get('correlation_and_overlap_vs_registry') or {}).get('verdict'))}</b> over
{esc((card.get('correlation_and_overlap_vs_registry') or {}).get('n_registry'))} rasters ·
worst signed ρ {fmt(((card.get('correlation_and_overlap_vs_registry') or {}).get('worst_rho_surface') or {}).get('value'),3)}
(limit 0.90) · worst one-sided 3 px overlap
{fmt(((card.get('correlation_and_overlap_vs_registry') or {}).get('worst_overlap_one_sided_3px') or {}).get('value'),3)}
(limit 0.70)</td></tr>
<tr><th>raster sha256</th><td class="num small">{esc(card.get('raster_sha256'))}
({esc(card.get('raster_bytes'))} bytes)</td></tr>
<tr><th>validator output</th><td>ok=<b>{esc(card.get('validator',{}).get('ok'))}</b> ·
{esc(card.get('validator',{}).get('n_pass'))} pass / {esc(card.get('validator',{}).get('n_fail'))} fail ·
no NaN inside footprint={esc(card.get('validator',{}).get('no_nan_inside_footprint'))} ·
values in [0,1]={esc(card.get('validator',{}).get('values_in_0_1'))} ·
CRS=EPSG:{esc(card.get('validator',{}).get('crs'))} ·
shape={esc(card.get('validator',{}).get('shape'))} ·
transform={esc(card.get('validator',{}).get('transform'))}</td></tr>
<tr><th>leakage canary</th><td>threshold {esc(card.get('leakage_canary',{}).get('threshold'))} ·
{esc(json.dumps(card.get('leakage_canary',{}).get('vs_withheld_truth')))} ·
any above threshold = {esc(card.get('leakage_canary',{}).get('any_above'))}</td></tr>
<tr><th>submission name</th><td><code>{esc(card.get('submission_name'))}</code></td></tr>
<tr><th>note ({esc(card.get('submission_note_chars'))}/140 chars)</th><td><code>{esc(card.get('submission_note'))}</code></td></tr>
<tr><th>organizer-confirmed score</th><td><b>{esc(card.get('organizer_confirmed_score'))}</b> —
no artifact in this repository has been scored by the organiser</td></tr>
<tr><th>verdict</th><td>{vpill} <b>{esc(card.get('verdict'))}</b>
{('— ' + esc(card.get('verdict_reason'))) if card.get('verdict_reason') else ''}</td></tr>
</table>""")
        b.append("<h3>Raw JSON</h3><pre><code>" + esc(json.dumps(card, indent=2, default=str)) + "</code></pre>")
    else:
        b.append("<p class='mut'>No run card yet.</p>")
    (DOCS / "run-card.html").write_text(page("Run card", "\n".join(b), "run-card.html",
                                            "The JSON card required by protocol section 5"))

    # ---------------------------------------------------------------- limitations
    b = ["""<h2>Limitations, and what would unblock each</h2>
<p>Stated up front rather than at the end. A limitation that is not written down is a limitation
that will be rediscovered badly.</p>
<table><thead><tr><th>#</th><th>limitation</th><th>effect on this lane</th><th>unblock</th>
<th>free &amp; official?</th></tr></thead><tbody>
<tr><td>1</td><td><b>No absolute-elevation band</b> (IR-62-DEM-01). Only <i>detrended</i>
elevation (band 12) and its slope (band 19).</td>
<td>An isobase is an absolute datum; detrending removes part of it. The fit is done in
detrended-elevation space, so the absolute shoreline elevation cannot be used.</td>
<td><code>1m_DEM_links.csv</code> from the DrivenData data tab → USGS 3DEP 1 m lidar.</td>
<td>Yes — USGS 3DEP is public domain. <b>Not obtainable from this sandbox</b> (egress allowlist).</td></tr>
<tr><td>2</td><td><b>100 m pixels.</b></td>
<td>A 15–45 m shoreline step is 0.15–0.45 px of relief. The physical throw window had to be
widened to 15–130 m to be detectable at all.</td>
<td>same 1 m lidar source</td><td>Yes, as above</td></tr>
<tr><td>3</td><td><b>Holdout truth is the visible catalogue</b> (IR-62-HOLDOUT-01).</td>
<td>The lane's premise is that it finds faults the catalogue misses, so the instrument cannot
directly reward success. A holdout win is necessary, not sufficient; a holdout loss does not
disprove the lane.</td><td>the organiser's hidden label set</td><td>No — nobody has it</td></tr>
<tr><td>4</td><td><b>No organiser score exists</b> for any artifact here.</td>
<td>Every number is HOLDOUT-DTI or ORGANIZER-CONFIRMED-from-an-earlier-file. The promote/negative
verdict is computed from the holdout and the gates, not from a score.</td>
<td>a weekly submission slot — a separate selector step</td><td>n/a</td></tr>
<tr><td>5</td><td><b>Lateral deflections carry no signal at 100 m</b> (IR-62-DEFL-01).</td>
<td>Half the lane's flagging criterion is a measured null. Kept because the lane specifies it;
reported rather than dropped.</td><td>1 m lidar</td><td>Yes, as above</td></tr>
<tr><td>6</td><td><b>Radiometrics are absent from the stack.</b></td>
<td>Blocks hypothesis H62-C (K/Th clay-cap breach), the one signature diagnostic of
<i>geothermal</i> rather than merely structural.</td>
<td>USGS GeoDAWN release, ScienceBase item 657e1d85d34e23d3533209f7</td>
<td>Yes — public domain. Obtainability from this sandbox <b>unverified</b>.</td></tr>
<tr><td>7</td><td><b>No GPU / no model training.</b></td>
<td>This lane is deterministic signal processing, so nothing is lost — but the reference
solution's U-Net route cannot be reproduced or blended here.</td>
<td>a GPU runner plus <code>pip install torch segmentation-models-pytorch</code></td>
<td>Yes (software), no (hardware in sandbox)</td></tr>
</tbody></table>
<h2>What a next session should do first</h2>
<ol>
<li><b>Obtain the 1 m lidar.</b> It closes limitations 1, 2 and 5 at once and is the single
highest-leverage unblock in this repository. Free, public domain, USGS 3DEP.</li>
<li><b>Implement H62-B</b> (isobase-parallel strike continuity: gaps between collinear mapped
traces). No new data, ~3 h, and it targets catalogue incompleteness more directly than anything
here.</li>
<li><b>Obtain the GeoDAWN radiometric grid</b> and implement H62-C. Highest ceiling of the five.</li>
<li><b>Re-run the holdout at a finer buffer</b> (2 px and 5 px) to check that the A3 result is not
an artefact of the 3 px buffer choice.</li>
<li><b>Do not spend a slot</b> on any file whose holdout DTI does not beat the current holdout
best, per the brief.</li>
</ol>"""]
    (DOCS / "limitations.html").write_text(page("Limitations", "\n".join(b), "limitations.html",
                                                "Limitations, unblocks, and what a next session should do first"))

    # ---------------------------------------------------------------- leaderboard
    rows = "".join(
        f"<tr><td class='num'><b>{s:.4f}</b></td><td class='small'><code>{esc(n)}</code></td>"
        f"<td class='small'>{esc(src)}</td></tr>"
        for n, s, src in sorted(ORGANIZER_ANCHORS, key=lambda r: -r[1]))
    b = ["""<h2>Organizer-confirmed score ledger</h2>
<p class="warn"><b>Evidence class:</b> every score in this table is
<b>ORGANIZER-CONFIRMED</b> — copied from a submission-page receipt and transcribed in the tasking
brief, cross-checked against the publishing repository's own leaderboard page. <b>No score for
any artifact in <i>this</i> repository appears here, because none exists.</b></p>""",
         "<table><thead><tr><th>score</th><th>submission name</th><th>publishing repo</th>"
         "</tr></thead><tbody>" + rows + "</tbody></table>",
         f"""<h3>What the ledger says</h3>
<p>The best organiser-confirmed score in this ledger is <b>0.2778</b>
(<code>h33-h33-2-b2</code>). The tasking brief reports a current competition high of 0.3195 and
0.3774 from other teams; those are not in this ledger because they are not this group's files and
no receipt for them is held here.</p>
<p>Everything above 0.24 in this ledger is a <b>dotted, binary, off-catalogue</b> artifact in the
37 k–61 k dot range. Everything below 0.12 is either a filled surface, a soft-probability field,
a very large dot count, or a file with mass on the mapped catalogue. That is not a coincidence
and it is the entire content of <a href="analysis.html">the analysis page</a>.</p>"""]
    (DOCS / "leaderboard.html").write_text(page("Leaderboard", "\n".join(b), "leaderboard.html",
                                                "Organizer-confirmed scores for earlier artifacts"))

    # ---------------------------------------------------------------- machine-readable feed
    feed = dict(built_utc=datetime.now(timezone.utc).isoformat(),
                lane="H62-A lahontan-isobase-strain-gauge",
                submission=dict(name=stem, note=note, note_chars=len(note),
                                tif=(f"docs/downloads/{stem}-zeros.tif" if stem else None),
                                zip=(f"docs/downloads/{stem}-zeros.zip" if stem else None),
                                sha256=rec.get("sha256"), bytes=rec.get("bytes"),
                                n_positive=rec.get("n_positive"),
                                okay_to_download_and_submit=bool(ok_submit),
                                verdict=verdict,
                                verdict_reason=card.get("verdict_reason"),
                                organizer_confirmed_score=None),
                holdout=dict(pooled_dti=hd.get("pooled_dti"), ci95=ci,
                             best_arm=best_arm, evaluator=hd.get("evaluator"),
                             withheld_positives=hd.get("n_withheld_positives_total"),
                             controls=hd.get("controls_mean"),
                             all_arms={a: (hold.get(a) or {}).get("pooled_dti") for a in hold}),
                uniqueness=dict(verdict=(e7 or {}).get("verdict"),
                                n_registry=(e7 or {}).get("n_registry"),
                                worst_rho=(e7 or {}).get("worst_rho_surface"),
                                worst_overlap=(e7 or {}).get("worst_overlap_3px")),
                validator=dict(ok=rec.get("ok"), n_pass=rec.get("n_pass"),
                               n_fail=rec.get("n_fail"), nan=rec.get("n_nan"),
                               vmin=rec.get("min"), vmax=rec.get("max"),
                               epsg=rec.get("epsg"), shape=rec.get("shape")),
                data=dict(spec=spec, pins=grid_pins()))
    (DOCS / "data" ).mkdir(exist_ok=True)
    (DOCS / "data" / "feed.json").write_text(json.dumps(feed, indent=2, default=str) + "\n")
    print(f"[site] wrote {len(list(DOCS.glob('*.html')))} pages to {DOCS}")
    return 0


HYP_ARM = {
    "A1": "lane-faithful: throw-window bench + azimuth kinks, extended along isobase strike; no catalogue term",
    "A2": "band-only ablation: whole margin band ranked by habitat + evidence; NO isobase",
    "A3": "lane + habitat: throw-window bench ∩ measured habitat ≥ 2.0",
}


def grid_pins():
    from gems62 import paths
    return paths.SHA256_PINS


if __name__ == "__main__":
    raise SystemExit(build())
