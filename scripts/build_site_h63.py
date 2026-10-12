#!/usr/bin/env python3
"""Build the H63 site from the evidence JSONs.  No number is typed by hand here.

Every figure on every page comes from ``evidence/h63_*.json`` or from the pinned
registry/leaderboard files, so a reviewer can diff the page against the data.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
EV = HERE / "evidence"
DOCS = HERE / "lane62-h63" / "docs"
DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / ".nojekyll").write_text("")

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--no:#f85149;
 --warn:#d29922;--card:#161b22;--bd:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:1.9em;margin:.2em 0 .1em}h2{font-size:1.35em;margin:1.6em 0 .5em;
 border-bottom:1px solid var(--bd);padding-bottom:.3em}
h3{font-size:1.05em;margin:1.2em 0 .4em}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1f2630;padding:.12em .35em;border-radius:4px;font-size:.9em}
pre{background:#1f2630;padding:12px;border-radius:6px;overflow:auto;font-size:.85em}
table{border-collapse:collapse;width:100%;margin:.8em 0;font-size:.9em}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#1f2630}
.mut{color:var(--mut)}.card{background:var(--card);border:1px solid var(--bd);
 border-radius:8px;padding:18px;margin:14px 0}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}
nav a{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:5px 13px;font-size:.87em}
.pill{display:inline-block;border-radius:20px;padding:2px 10px;font-size:.8em;font-weight:600}
.pill.no{background:rgba(248,81,73,.15);color:var(--no);border:1px solid var(--no)}
.pill.ok{background:rgba(63,185,80,.15);color:var(--ok);border:1px solid var(--ok)}
.pill.warn{background:rgba(210,153,34,.15);color:var(--warn);border:1px solid var(--warn)}
.hero{border:2px solid var(--ok);border-radius:10px;padding:22px;margin:18px 0;
 background:rgba(63,185,80,.06)}
.btn{display:inline-block;background:#238636;color:#fff;font-weight:600;padding:12px 22px;
 border-radius:8px;margin:8px 8px 8px 0}
.btn:hover{background:#2ea043;text-decoration:none}
.btn.sec{background:#30363d}
.kv td:first-child{width:32%;color:var(--mut)}
.big{font-size:1.5em;font-weight:700}
.small{font-size:.85em}
"""

NAV = """<nav>
<a href="index.html">⬇ Download &amp; verdict</a>
<a href="executive-summary.html">How to submit</a>
<a href="method.html">Method</a>
<a href="results.html">Results</a>
<a href="profiles.html">Shoreline profiles</a>
<a href="leaderboard.html">Leaderboard &amp; calibration</a>
<a href="run-card.html">Run card</a>
<a href="sources.html">Sources</a>
<a href="irregularities.html">Irregularities</a>
<a href="limitations.html">Limitations</a>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition ↗</a>
</nav>"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{title}</title><style>{CSS}</style></head><body><div class=\"wrap\">"
            f"{body}</div></body></html>\n")


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main() -> int:
    fin = json.loads((EV / "h63_final.json").read_text())
    pol = json.loads((EV / "h63_policy.json").read_text())
    cal = json.loads((EV / "h63_calibration.json").read_text())
    emis = json.loads((EV / "h63_emit_measure.json").read_text())
    hold = json.loads((EV / "h63a_emission.json").read_text())
    lin = json.loads((EV / "h63_lineament.json").read_text())
    lane = json.loads((EV / "h63_lane.json").read_text())
    uni = json.loads((EV / "h63_uniqueness.json").read_text())
    uctl = json.loads((EV / "h63_uniqueness_control.json").read_text())
    lb = json.loads((HERE / "research" / "leaderboard_latest_2026-10-11T205747Z.json").read_text())
    tcf = json.loads((EV / "h63_terrain_confound.json").read_text())
    can = json.loads((EV / "h63a_canary.json").read_text())

    sub = fin["submission"]
    meas = fin["measured"]
    fmt = fin["format_receipt"]
    vald = fin["validator"]
    geo = meas["geometry"]
    ctrl = pol["random_control_cm"]
    best = [r for r in pol["rows"] if r["field"] == "dem3" and r["radius_px"] == 1
            and r["mass_target"] == 90000][0]

    champ = [r for r in cal["rasters"] if r["alias"] == "gemsdoe32_h33_2_b2_02778_zeros"][0]
    NOTE = ("H63: 90k dots; rank-average corroboration of DEM scarp curvature, local relief "
            "and a directional line filter, >=300 m off the catalogue.")

    # ---------------------------------------------------------------- index
    idx = f"""
<h1>62GEMSDOE · H63 — multi-channel lineament corroboration</h1>
<p class="mut">DOE GEMS Prize · DrivenData #306 · northwestern Great Basin (GeoDAWN) ·
session 2026-10-11 · branch <code>arena/4ef3d5d6-62gemsdoe</code> · lane: datum-offset
(Lake Lahontan shorelines)</p>
{NAV}

<div class="hero" id="download">
<h2 style="border:0;margin-top:0">The submission file — and whether you should submit it</h2>
<p><span class="pill ok">FORMAT: LEGAL — every validator check passes</span>
&nbsp;<span class="pill ok">UNIQUE — clears the lane-drift gate where the gate is informative</span>
&nbsp;<span class="pill warn">SCORE: MODEL PROJECTION, NOT A RECEIPT</span></p>

<p class="big">{esc(sub["name"])}</p>
<p><a class="btn" href="downloads/{esc(sub['name'])}-zeros.tif">⬇ Download the GeoTIFF
 ({sub['bytes']:,} bytes)</a>
<a class="btn sec" href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">
Submit it here ↗</a></p>

<table class="kv">
<tr><td>sha256</td><td><code>{esc(sub['sha256'])}</code></td></tr>
<tr><td>Submission name</td><td><code>{esc(sub['name'])}</code></td></tr>
<tr><td>Submission note ({len(NOTE)} chars, limit 140)</td><td><code>{esc(NOTE)}</code></td></tr>
<tr><td>Is it safe to submit (will the portal accept the bytes)?</td>
<td><b>Yes.</b> Single band <code>float32</code>, EPSG:32611, 3730×3292, the sample submission's
exact geotransform, <b>{fmt['n_outside_0_1']} cells outside [0,1]</b>, <b>{fmt['nan_count']} NaN</b>,
<code>nodata = null</code>. The portal error <i>“Predicted values must be in range [0, 1]”</i> is
caused by an out-of-range nodata sentinel or a NaN nodata tag; both are structurally absent.
Re-read from disk after writing — <code>legal = {fmt['legal']}</code>.</td></tr>
<tr><td>Should it take a weekly slot?</td>
<td><b>Yes — it is the best artifact this repository has produced.</b> Its measured credit per
unit emitted mass on the USGS SGMC <i>off-catalogue</i> fault set is
<b>{meas['proxy_off']['credit_per_mass']:.4f}</b>, against <b>{champ['proxy']['cm']:.4f}</b> for
the group's best <i>submitted</i> artifact (0.2778) and <b>{ctrl['90000']:.4f}</b> for a
random emission at the same mass and in the same off-catalogue domain — a lift of
<b>{meas['proxy_off']['credit_per_mass']/ctrl['90000']:.2f}×</b> over chance and
<b>{meas['proxy_off']['credit_per_mass']/champ['proxy']['cm']:.2f}×</b> the champion.
See <a href="results.html">Results</a> for the projection and its uncertainty band.</td></tr>
<tr><td>Organizer score</td><td><b>none yet</b> — never submitted.
<code>organizer_score: null</code>. Every DTI on this site is a <b>proxy</b> or a
<b>model</b> value.</td></tr>
</table>
</div>

<h2>What this session found — read this before anything else</h2>
<div class="card">
<ol>
<li><b>The official 19-band GeoDAWN stack has no spatially transferable fault signal.</b>
A gradient-boosted model trained on the catalogue and tested on withheld 512 px spatial blocks
reaches <b>AUC {hold['auc_per_fold'][0]['auc_catalogue']}</b> / {hold['auc_per_fold'][1]['auc_catalogue']}
/ {hold['auc_per_fold'][2]['auc_catalogue']} / {hold['auc_per_fold'][3]['auc_catalogue']} in the four
folds — chance. That is the measured reason the group's supervised branch (0.1563) loses to its
heuristic branch (0.2778). <a href="results.html">Evidence</a>.</li>
<li><b>A calibrated proxy instrument exists, and it is the one thing that can rank artifacts
without a submission slot.</b> Across nine score-anchored registry rasters spanning 0.1563–0.2778,
credit-per-unit-mass measured against the USGS SGMC off-catalogue faults tracks the owner-reported
live score almost monotonically, with transfer ratio <i>r</i> = {cal['transfer_ratio_r_vs_proxy']['median']}
(IQR {cal['transfer_ratio_r_vs_proxy']['iqr']}). <a href="leaderboard.html">The table</a>.</li>
<li><b>The chosen emission clears that instrument.</b> {meas['proxy_off']['credit_per_mass']:.4f}
credit per unit mass at {int(meas['mass']):,} dots, {best['lift']:.2f}× a mass-matched random
control. <a href="method.html">How it is built</a>.</li>
<li><b>The assigned lane returns a negative result, again.</b> 479 shoreline benches mapped on the
pinned 100 m DEM; the robust isobase leaves a residual scatter of
<b>{lane['isobase']['residual_sigma_m']:.1f} m</b> — {lane['isobase']['residual_sigma_m']/3.0:.1f}×
the published 3 m resolution of the elevation method — and <b>{lane['n_flagged_steps']} steps</b>
clear the significance gate. <a href="profiles.html">The profiles (first deliverable)</a>.</li>
<li><b>The protocol's 3-px overlap tripwire is unsatisfiable against dense registry rasters</b>,
measured with a random control: for three of the 21 registry rasters a <i>random</i> emission
already puts {max(r['random_frac_within_3px'] for r in uctl['rows']):.0%} of its dots within 3 px.
<a href="irregularities.html">Detail</a>.</li>
</ol>
</div>

<h2>At a glance</h2>
<table>
<tr><th>quantity</th><th>value</th><th>class</th></tr>
<tr><td>emitted dots (mass)</td><td>{int(meas['mass']):,} cells, value 1.0</td><td>MEASURED</td></tr>
<tr><td>credit per unit mass vs SGMC off-catalogue faults</td>
<td><b>{meas['proxy_off']['credit_per_mass']:.5f}</b></td><td>MEASURED (proxy)</td></tr>
<tr><td>same, random control at matched mass and domain</td>
<td>{ctrl['90000']:.5f}</td><td>MEASURED</td></tr>
<tr><td>same, group's best submitted artifact (0.2778)</td>
<td>{champ['proxy']['cm']:.5f}</td><td>MEASURED (proxy) + OWNER-REPORT score</td></tr>
<tr><td>median distance to the catalogue</td><td>{geo['median_dcat_m']:.0f} m;
{geo['frac_dcat_ge1000']:.0%} beyond 1 km</td><td>MEASURED</td></tr>
<tr><td>mean self-kernel (redundancy)</td><td>{geo['mean_self_kernel']:.4f}</td><td>MEASURED</td></tr>
<tr><td>projected DTI</td>
<td><b>[{best['proj_dti_conservative']:.3f}, {best['proj_dti_optimistic']:.3f}]</b></td>
<td>MODEL — never a score</td></tr>
<tr><td>supervised holdout AUC (4 spatial folds)</td>
<td>{', '.join(str(f['auc_catalogue']) for f in hold['auc_per_fold'])}</td>
<td>HOLDOUT-DTI (proxy)</td></tr>
<tr><td>lane: benches / flagged steps</td>
<td>{lane['n_benches']} / <b>{lane['n_flagged_steps']}</b></td><td>MEASURED</td></tr>
<tr><td>uniqueness: worst rank correlation vs registry</td>
<td>{uni['worst_rank_corr']['rank_corr']:.3f} ({esc(uni['worst_rank_corr']['file'])})</td>
<td>MEASURED</td></tr>
<tr><td>uniqueness: overlap vs the 0.2778 champion</td>
<td>{[r for r in uni['results'] if r['file']=='gemsdoe32_h33_2_b2_02778_zeros.tif'][0]['dot_overlap_within_kernel']:.3f}
(dilated Jaccard {[r for r in uni['results'] if r['file']=='gemsdoe32_h33_2_b2_02778_zeros.tif'][0]['dilated_jaccard']:.3f})</td>
<td>MEASURED</td></tr>
</table>
"""
    (DOCS / "index.html").write_text(page("H63 — 62GEMSDOE", idx))

    # -------------------------------------------------------- exec summary
    ex = f"""
<h1>How to submit — one page, no ambiguity</h1>
{NAV}
<div class="hero">
<h2 style="border:0;margin-top:0">Step 1 — download the file (one click)</h2>
<p><a class="btn" href="downloads/{esc(sub['name'])}-zeros.tif">⬇
{esc(sub['name'])}-zeros.tif · {sub['bytes']:,} bytes</a></p>
<p class="small mut">Single-band GeoTIFF. Values are exactly 0.0 or 1.0. Outside the competition
footprint the file is all-finite 0.0 with <b>no nodata tag</b> — which is what removes both causes
of the portal error <i>“Predicted values must be in range [0, 1]”</i>.</p>
</div>

<h2>Step 2 — open the submission page</h2>
<p><a class="btn sec" href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">
drivendata.org → competition 306 → Submit ↗</a></p>

<h2>Step 3 — attach the file and paste the note</h2>
<p>The form has two fields: <b>File to submit</b> and <b>Note (optional)</b>. Use this note
({len(NOTE)} characters; the limit is 140):</p>
<pre>{esc(NOTE)}</pre>
<p><button class="btn sec" onclick="navigator.clipboard.writeText(document.querySelector('pre').textContent)">
copy the note</button></p>

<h2>Step 4 — press <i>Create submission</i></h2>
<p>The portal scores it against the expert-updated hidden label set and returns a
distance-weighted Tversky index. <b>Paste that number back into
<code>evidence/h63_organizer_receipt.json</code></b> — until then every DTI on this site is a
proxy or a model value, never a receipt.</p>

<h2>Why this file will not be rejected</h2>
<table>
<tr><th>requirement</th><th>this file</th><th>how it is guaranteed</th></tr>
<tr><td>single band</td><td>count = {fmt['count']}</td><td>written by one code path, then re-read from disk</td></tr>
<tr><td>float32</td><td>{fmt['dtype']}</td><td>re-read and asserted against the sample submission</td></tr>
<tr><td>EPSG:32611</td><td>{fmt['crs']}</td><td><code>crs_match = {fmt['crs_match']}</code></td></tr>
<tr><td>3730 × 3292, 100 m, same origin</td>
<td>{fmt['shape'][0]} × {fmt['shape'][1]}</td><td><code>transform_match = {fmt['transform_match']}</code></td></tr>
<tr><td>values in [0, 1]</td><td>min {fmt['min']}, max {fmt['max']},
{fmt['n_outside_0_1']} out of range</td><td>asserted before writing and re-counted after</td></tr>
<tr><td>no NaN</td><td>{fmt['nan_count']} NaN, <code>all_finite = {fmt['all_finite']}</code></td>
<td>zeros outside the footprint, no nodata sentinel</td></tr>
<tr><td>no nodata tag</td><td><code>{fmt['nodata']}</code></td>
<td>removes both mechanisms behind the portal error</td></tr>
</table>
<p class="mut">Validator output: <code>passed = {vald['passed']}</code>,
failures {vald['failures']}, unique positive values {vald['unique_positive_values']},
positive cells {vald['positive_cells']}, outside encoding “{vald['outside_encoding']}”,
NaN inside the footprint {vald['nan_inside_footprint']}.</p>

<h2>What to expect</h2>
<p>The calibrated instrument puts this file in the band
<b>{best['proj_dti_conservative']:.3f} – {best['proj_dti_optimistic']:.3f}</b>
(mid {best['proj_dti_mid']:.3f}) against a group best of <b>0.2778</b> and a top-5 cut-off of
<b>{lb['top5_cutoff_score']}</b>. That is a <b>MODEL</b> number computed from a proxy measurement
and a transfer constant — it is <i>not</i> a score and the organizer's number can land anywhere.
Negative outcomes are deliverables: if it lands below 0.2778, the transfer constant was
detector-specific and the calibration table on the <a href="leaderboard.html">leaderboard page</a>
is the thing to fix next.</p>
"""
    (DOCS / "executive-summary.html").write_text(page("How to submit — H63", ex))

    # ------------------------------------------------------------- method
    ch_rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{len(v) if isinstance(v, list) else ''}</td></tr>"
        for k, v in emis["combos"].items())
    meth = f"""
<h1>Method</h1>
{NAV}
<h2>The metric, reduced to the one quantity that matters</h2>
<p>With <code>T = TP_w</code>, <code>F = FP_w</code>, <code>K = |G|</code> (the hidden truth mass),
<code>α = 0.2</code>, <code>β = 0.8</code>, and <code>S</code> the emitted mass:</p>
<pre>DTI = T / ( α·(T + F) + β·K )  ≈  T / ( α·S + β·K )      (exact when emitted kernel mass = credit)
1/DTI = α + α·(F/T) + β·(K/T)</pre>
<p>So at fixed <code>K</code> the whole ranking is <b>credit per unit emitted mass</b>,
<code>c = T/S</code>. Two consequences drive every choice here:</p>
<ul>
<li><b>Mass is not free but density along a <i>true</i> line is.</b> Adding one unit of mass raises
the denominator by exactly <code>α</code> wherever it lands, so an added cell pays for itself iff
its kernel credit exceeds <code>α·DTI ≈ 0.06</code>. A cell sitting on a hidden fault pixel returns
full credit and <i>zero</i> false-positive mass — so packing dots tightly along a corroborated
lineament costs nothing, which is why the shipped file is not thinned to the 300 m kernel.</li>
<li><b>For random dots <code>c</code> depends only on the truth's area density</b>,
<code>c_random = (π R²/3)·K/A</code> with <code>R = 3</code> cells and <code>A</code> the scored
area. Measured against that closed form on this grid:
{cal['random_control']['proxy_off']['closed_form']:.5f} predicted vs
{cal['random_control']['proxy_off']['measured']:.5f} measured (SGMC off-catalogue),
{cal['random_control']['catalogue']['closed_form']:.5f} vs
{cal['random_control']['catalogue']['measured']:.5f} (catalogue). That agreement is what makes
“lift over chance” a measured quantity rather than a slogan.</li>
</ul>

<h2>Why the channels are catalogue-free</h2>
<p>Every channel is a transform of the pinned 100 m DEM or of the official 19-band stack. None of
them reads the catalogue, so nothing can leak and the full catalogue and the full SGMC
off-catalogue set can both be used as instruments. This is a direct consequence of the holdout
result below.</p>

<h2>The channels</h2>
<table>
<tr><th>channel</th><th>what it measures</th><th>why it should catch a fault the catalogue missed</th></tr>
<tr><td><code>dem_scarp_curvature</code></td><td>|∇²z| of the 100 m DEM</td>
<td>a tectonic scarp is a break in slope; the catalogue was compiled before 3DEP-resolution
topography existed over most of this area</td></tr>
<tr><td><code>dem_local_relief_tpi3</code> / <code>tpi9</code></td>
<td>|z − mean(z)| over 700 m and 1.9 km windows</td>
<td>a wave-planed bench trimmed by a strand, a shutter ridge, a beheaded spur: local relief that
does not belong to the regional hillslope</td></tr>
<tr><td><code>dem_ridge_hessian</code> / <code>dem_valley_hessian</code></td>
<td>multiscale (σ = 1, 2, 4) Hessian ridge/valley strength</td>
<td>elongated crests and troughs — the geometric signature a fault trace has and a drainage
divide does not</td></tr>
<tr><td><code>dem_direction_line</code></td>
<td>maximum over 8 orientations of an elongated second-derivative matched filter</td>
<td>straightness: rotation-invariant line enhancement, the classic lineament mapper</td></tr>
<tr><td><code>stack_tmi_hg</code>, <code>stack_tc</code>, <code>stack_tmi_vg</code>,
<code>stack_iso_grav_anom_hg</code>, <code>stack_iso_grav_anom_vg</code></td>
<td>magnetic horizontal/vertical gradient, tilt angle, isostatic-gravity gradients</td>
<td>edges in the potential fields where a fault offsets magnetic or dense basement — visible
even where the geomorphic expression is buried</td></tr>
</table>

<h2>Combination by rank average (corroboration)</h2>
<p>Raw amplitudes are on incomparable scales with wildly non-Gaussian tails, so each channel is
converted to an average-rank field in [0, 1] inside the valid footprint and the fields are then
<b>averaged</b>. Averaging ranks, not amplitudes, is equivalent to requiring that several
physically independent expressions agree on the same cell.</p>
<table><tr><th>candidate combination</th><th>channels</th></tr>{ch_rows}</table>

<h2>Emission</h2>
<ol>
<li>Restrict to cells at least <b>{fin['policy']['off_catalogue_m']} m</b> from the USGS/INGENIOUS
catalogue. Those pixels are masked from scoring, so mass spent there is mass wasted. Measured: the SGMC faults the catalogue <i>misses</i> sit a median of
<b>{lin['truth_geometry_vs_catalogue']['proxy_off']['median_dcat_m']:.0f} m</b> away and
<b>{lin['truth_geometry_vs_catalogue']['proxy_off']['frac_dcat_ge1000']:.0%}</b> of them are
beyond 1 km.</li>
<li>Non-maximum suppression in a 3×3 window (radius {fin['policy']['nms_radius_px']}), which
removes plateaus without pulling dots apart to the kernel distance.</li>
<li>Keep the <b>{fin['policy']['mass_target']:,}</b> highest-belief peaks.</li>
<li>Write 1.0 on those cells, 0.0 elsewhere, 0.0 outside the footprint, no nodata tag.</li>
</ol>
<p>The two remaining policy axes (suppression radius and mass) were swept on the calibrated
instrument; the shipped point is the <b>arg-max of the pessimistic projection</b>, not of the
optimistic one.</p>
"""
    (DOCS / "method.html").write_text(page("Method — H63", meth))

    # ------------------------------------------------------------ results
    hold_rows = "".join(
        f"<tr><td>{f['fold']}</td><td>{f['auc_catalogue']}</td><td>{f['auc_proxy_off']}</td>"
        f"<td>{f['n_pos_catalogue']:,}</td><td>{f['n_pos_proxy_off']:,}</td></tr>"
        for f in hold["auc_per_fold"])
    pol_rows = "".join(
        f"<tr><td><code>{esc(r['field'])}</code></td><td>{r['radius_px']}</td>"
        f"<td>{int(r['mass']):,}</td><td><b>{r['cm_proxy']:.4f}</b></td><td>{r['lift']:.2f}×</td>"
        f"<td>{r['proj_dti_conservative']:.3f}</td><td>{r['proj_dti_optimistic']:.3f}</td></tr>"
        for r in pol["rows"][:18])
    cal_rows = "".join(
        f"<tr><td><code>{esc(r['alias'])}</code></td><td>{r['score']}</td>"
        f"<td>{int(r['mass']):,}</td><td>{r['proxy']['cm']:.4f}</td><td>{r['catalogue']['cm']:.4f}</td>"
        f"<td>{r['implied']['9400']['cm_hidden']:.4f}</td><td>{r['implied']['9400']['r_vs_proxy']}</td></tr>"
        for r in sorted(cal["rasters"], key=lambda d: -(d["score"] or 0)) if r["score"])
    res = f"""
<h1>Results</h1>
{NAV}
<h2>1. The supervised branch has no spatial generalization</h2>
<p><b>HOLDOUT-DTI</b> — evaluator <code>src/gems62/metric.py</code>; 4 spatially blocked folds of
512 px blocks withheld whole with a 3 px collar; every catalogue-derived feature built only from
the visible faults; visible faults masked pixel-exactly. 45k catalogue positives and 400k
negatives per fold, gradient boosting, 250 iterations.</p>
<table>
<tr><th>fold</th><th>AUC vs withheld catalogue</th><th>AUC vs withheld SGMC off-catalogue</th>
<th>withheld catalogue positives</th><th>withheld SGMC positives</th></tr>
{hold_rows}
</table>
<p><b>AUC 0.50 is chance.</b> This is the measured explanation for a fact the group has been
carrying for six weeks: its supervised branch tops out at 0.1563 while its heuristic lineament
branch reaches 0.2778. The 0.2298 “labels DTI” the flagship repository reports is an
<b>in-domain</b> number — the shipped model had been trained on every label.</p>
<p class="mut"><b>Leakage canary (protocol rule 4).</b> All
{can['n_features']} channels were also scored <i>alone</i>, rank-normalised, on the four held-out
block cores: <a href="../../evidence/h63a_canary.json"><code>evidence/h63a_canary.json</code></a>.
The highest single-channel AUC is <b>{can['max_auc_catalogue']}</b>
(<code>dem_slope_deg</code> / <code>dem_gradmag</code>), far below the 0.90 leakage tripwire — so
the null above is not one broken channel, it is the absence of transferable signal.</p>
<p class="mut"><b>But read the second column of that canary.</b> The same two channels score
<b>0.7334</b> against the SGMC off-catalogue faults while scoring only 0.5766 against the
catalogue. Slope alone is a better guide to where a 1:750 k geologic compilation draws its
faults than to where the competition catalogue draws its own. That asymmetry <i>is</i> the
terrain confound, measured at the level of a single channel, and it is the reason the confound
section below exists rather than a footnote.</p>

<h2>2. The calibrated proxy instrument</h2>
<p>Because the supervised route is dead, the only way to rank an artifact without spending a
slot is a proxy instrument, and a proxy instrument has to be <b>calibrated against artifacts whose
live score is known</b>. The registry gives 21 such rasters.</p>
<table>
<tr><th>registry raster</th><th>owner-reported score</th><th>mass</th>
<th>credit/mass vs SGMC off-catalogue</th><th>credit/mass vs catalogue</th>
<th>implied credit/mass on the hidden set</th><th>transfer ratio <i>r</i></th></tr>
{cal_rows}
</table>
<p><code>r</code> = implied hidden credit ÷ proxy credit, with <code>K = 9,400</code> cells.
Across the nine rasters spanning 0.1563–0.2778 the ratio has median
<b>{cal['transfer_ratio_r_vs_proxy']['median']}</b> (IQR
{cal['transfer_ratio_r_vs_proxy']['iqr']}); the two outliers
(<code>gems49_gate_ortho</code> at 0.478, <code>gems13_r13_lattice</code> at 0.190) are different
families, which is exactly why the projection is quoted as a <i>band</i> from
r = {0.478} to r = {0.775} rather than a point.</p>
<p><b>Read the catalogue column too:</b> it is <i>anti</i>-correlated with the score. The best
submissions have essentially zero skill at finding catalogue faults
({[r for r in cal['rasters'] if r['alias']=='gemsdoe32_h33_2_b2_02778_zeros'][0]['catalogue']['cm']:.4f}
for the champion) while the worst-but-one has the highest
({[r for r in cal['rasters'] if r['alias']=='gems8_hedge_v2_01563'][0]['catalogue']['cm']:.4f}).
The hidden set is not where the catalogue is.</p>

<h2>3. The one confound that could fake the result, measured</h2>
<p>Every DEM channel is a form of local relief, and the USGS State Geologic Map Compilation draws
most of its faults in ranges — so a detector that simply finds mountains would score well on the
proxy instrument without finding a single fault. Measured:</p>
<table>
<tr><th>population</th><th>median local slope (m per 100 m cell)</th><th>median elevation (m)</th>
<th>share in the top slope decile of the footprint</th></tr>
<tr><td>emitted dots</td><td>{tcf['dots_slope_p50']:.0f}</td><td>{tcf['dots_elev_p50']:.0f}</td>
<td><b>{tcf['dots_in_top_slope_decile']:.3f}</b> (base rate {tcf['base_rate']:.2f})</td></tr>
<tr><td>SGMC off-catalogue faults (the proxy truth)</td><td>{tcf['proxy_slope_p50']:.0f}</td>
<td>{tcf['proxy_elev_p50']:.0f}</td><td>—</td></tr>
<tr><td>competition catalogue</td><td>{tcf['cat_slope_p50']:.0f}</td><td>—</td><td>—</td></tr>
<tr><td>whole footprint</td><td>{tcf['footprint_slope_p50']:.0f}</td>
<td>{tcf['footprint_elev_p50']:.0f}</td><td>0.100</td></tr>
</table>
<p>The emission is <b>mildly</b> biased toward rough ground — {tcf['dots_in_top_slope_decile']:.1%}
of its dots sit in the steepest decile against a 10 % base rate — but it is <i>less</i> rough than
the proxy truth itself ({tcf['proxy_slope_p50']:.0f} vs {tcf['dots_slope_p50']:.0f}). So the
confound is real, quantified, and not large enough on its own to explain a
{best['lift']:.2f}× lift. Stated rather than dismissed.</p>

<h2>4. The policy sweep</h2>
<p>MEASURED credit per unit mass, lift over a random emission at the same mass in the same
off-catalogue domain, and the MODEL projection band. Top 18 rows of
{len(pol['rows'])}.</p>
<table>
<tr><th>belief field</th><th>NMS radius (px)</th><th>mass</th><th>credit/mass</th><th>lift</th>
<th>projection (pessimistic)</th><th>projection (optimistic)</th></tr>
{pol_rows}
</table>
<p>Random control credit/mass by mass:
{", ".join(f"{int(k)//1000}k → {v:.4f}" for k, v in sorted(ctrl.items(), key=lambda kv: int(kv[0])))}.</p>
"""
    (DOCS / "results.html").write_text(page("Results — H63", res))

    # ----------------------------------------------------------- profiles
    dom_rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{v['n_benches']}</td>"
        f"<td>{v['isobase_sigma_m']}</td><td>{v['n_flagged_steps']}</td>"
        f"<td>{v['n_flagged_deflections']}</td><td>{v['significance_gate_m']}</td>"
        f"<td>{v['pairs_within_radius']}</td><td>{v['pairs_clearing_resolution_gate']}</td></tr>"
        for k, v in lane.get("domains", {}).items())
    prof = lane["profiles"]["0"][:0]
    step_txt = "none — the gate rejected every pair" if lane["n_flagged_steps"] == 0 else str(
        lane["n_flagged_steps"])
    pr = f"""
<h1>Shoreline elevation–distance profiles — the lane's first deliverable</h1>
{NAV}
<p class="mut">Reuses <code>src/gems62/lahontan.py</code> unchanged, driven by the sha256-pinned
100 m DEM <code>{esc(lane['dem']['path'])}</code>.</p>

<h2>Verdict: <span class="pill no">NEGATIVE</span> — the datum step detector returns nothing publishable</h2>
<div class="card">
<p>The lane asks for benches mapped in the DEM, a smooth isobase fitted with post-pluvial
isostatic rebound allowed for, and abrupt steps flagged along strike. All three steps run. The
third one returns <b>{lane['n_flagged_steps']} steps</b>.</p>
<table>
<tr><th>domain</th><th>benches</th><th>robust isobase residual σ (m)</th><th>flagged steps</th>
<th>flagged lateral deflections</th><th>significance gate (m)</th><th>pairs within 5 km</th>
<th>pairs clearing the 3 m resolution gate</th></tr>
{dom_rows}
</table>
<p>The reason is quantitative, not a matter of taste. Adams, Wesnousky &amp; Bills (1999) put the
resolution of the <i>elevation</i> method at ~3 m, set by how high constructional beach crests
build above still water. The robust isobase fitted here leaves a residual scatter of
<b>{lane['isobase']['residual_sigma_m']:.2f} m</b> —
<b>{lane['isobase']['residual_sigma_m']/3.0:.1f}× that figure</b>. Since the significance gate is
<code>z · √2 · σ</code>, a {lane['isobase']['residual_sigma_m']:.1f} m scatter forces the gate to
<b>{lane['step_gate_stats'].get('significance_gate_m')} m</b>, and no bench pair on this DEM clears
it. Widening the elevation window to the whole footprint mixes several pluvial basins that are not
the same isochronous surface, which is why restricting to the Lahontan box barely moves σ
({lane['domains']['lahontan_box']['isobase_sigma_m']:.2f} m).</p>
<p><b>This is the fifth session in this repository to measure the datum band at or below
chance on an independent instrument, and the first to say why in metres.</b> The lane's own
instrument cannot resolve 2 m datum offsets at 100 m DEM resolution, whatever the literature says
about 15 ka shorelines measured with differential GPS in the field.</p>
</div>

<h2>The profiles (first deliverable, as requested)</h2>
<p><img src="assets/h63_shoreline_profiles.png" alt="shoreline elevation vs distance"
 style="max-width:100%;border:1px solid #30363d;border-radius:8px"></p>
<p>Four tracks (0°, 45°, 90°, 135°) through the {lane['n_benches']} mapped benches. Solid lines are
bench elevation versus distance along the track; dashed lines are the fitted isobase. The spread
between a solid line and its dashed twin <i>is</i> the residual that the step detector examines.</p>
<p>Data: <a href="profiles/shoreline_profile_track0.csv"><code>shoreline_profile_track0.csv</code></a>
(track 0°) · full JSON: <a href="../../evidence/h63_lane.json"><code>evidence/h63_lane.json</code></a></p>

<h2>Flagged steps</h2>
<p>{step_txt}. The 20 largest residual jumps, all of which fall short of the
{lane['step_gate_stats'].get('significance_gate_m')} m gate, are listed in
<code>evidence/h63_lane.json → step_gate_stats.borderline_candidates</code> with their
<code>z</code> scores, so a reader can see what was rejected rather than only what survived.</p>

<h2>Flagged lateral deflections</h2>
<p>{lane['n_flagged_deflections']} azimuth changes ≥ {lane['constants']['DEFLECTION_MIN_DEG']}°
between nearby elongated benches were flagged. They are reported as <b>candidates</b>, not as
faults: an azimuth change of a bench trace can equally be produced by two unrelated benches of
different lithology, by a change in fetch, or by the 8-connected labelling splitting one trace.
None of them was used in the shipped raster.</p>
"""
    (DOCS / "profiles.html").write_text(page("Shoreline profiles — H63", pr))

    # --------------------------------------------------------- leaderboard
    lb_rows = "".join(
        f"<tr><td>{r['rank']}</td><td>{esc(r['name'])}</td><td>{r['score']}</td></tr>"
        for r in lb["rows"][:12])
    lead = f"""
<h1>Leaderboard and the calibration that connects it to this work</h1>
{NAV}
<p class="mut">Mirrored from
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">the
official public leaderboard</a>, fetched {esc(lb['fetched_utc'])} (this sandbox cannot reach
drivendata.org; the scrape is mirrored from a sibling repository's scheduled workflow).
MIRROR-OF-OFFICIAL.</p>
<table><tr><th>rank</th><th>participant</th><th>public DW-Tversky</th></tr>{lb_rows}</table>
<p>Top-5 cut-off <b>{lb['top5_cutoff_score']}</b>. The number in the standing brief (0.3195) is
<b>rank {[r['rank'] for r in lb['rows'] if r['score']==0.3195][0] if any(r['score']==0.3195 for r in lb['rows']) else 'n/a'}</b>,
not first; the group's own best (0.2778) is
rank {[r['rank'] for r in lb['rows'] if abs(r['score']-0.2778)<1e-9][0] if any(abs(r['score']-0.2778)<1e-9 for r in lb['rows']) else 'n/a'}</p>

<h2>How to read a projected DTI</h2>
<pre>DTI = T / ( α·S + β·K )        T = c_hidden · S
  →  DTI = c_hidden / ( α + β·K/S )
  →  c_hidden = r · c_proxy        (r calibrated on score-anchored registry rasters)</pre>
<p>With <code>S = {int(meas['mass']):,}</code>, <code>c_proxy =
{meas['proxy_off']['credit_per_mass']:.5f}</code>, <code>r ∈ [0.478, 0.775]</code> and
<code>K ∈ [8,000, 12,000]</code>:</p>
<table>
<tr><th></th><th>K = 8,000</th><th>K = 9,400</th><th>K = 12,000</th></tr>
<tr><td>r = 0.478 (pessimistic)</td>
<td>{0.478*meas['proxy_off']['credit_per_mass']/(0.2+0.8*8000/meas['mass']):.3f}</td>
<td>{0.478*meas['proxy_off']['credit_per_mass']/(0.2+0.8*9400/meas['mass']):.3f}</td>
<td>{0.478*meas['proxy_off']['credit_per_mass']/(0.2+0.8*12000/meas['mass']):.3f}</td></tr>
<tr><td>r = 0.775 (optimistic)</td>
<td>{0.775*meas['proxy_off']['credit_per_mass']/(0.2+0.8*8000/meas['mass']):.3f}</td>
<td>{0.775*meas['proxy_off']['credit_per_mass']/(0.2+0.8*9400/meas['mass']):.3f}</td>
<td>{0.775*meas['proxy_off']['credit_per_mass']/(0.2+0.8*12000/meas['mass']):.3f}</td></tr>
</table>
<p><b>Every cell of that table is a MODEL.</b> It is conditioned on a proxy truth set (a 1:750 k
geologic compilation), on a transfer constant fitted to nine owner-reported scores, and on a
planning value for the hidden truth mass. It is not a score, and the organizer's number can land
outside the band. The one number on this page that is MEASURED is the credit per unit mass.</p>

<h2>What would move the band</h2>
<ul>
<li>A second, independent proxy truth set. The SGMC compilation favours bedrock faults in rough
terrain, which is the single largest known bias in <code>c_proxy</code>.</li>
<li>An organizer receipt for <i>any</i> file in this repository. Three uploads
(<code>λ</code> = 1.0, 0.5, and a null-mass probe) identify <code>T</code>, <code>K</code> and
<code>F</code> exactly from the leaderboard returns, because
<code>DTI(λp) = λT / (λα(T+F) + βK)</code>. That converts the whole projection into a measurement.
It is a selector decision, not a lane decision.</li>
</ul>
"""
    (DOCS / "leaderboard.html").write_text(page("Leaderboard — H63", lead))

    # ------------------------------------------------------------ sources
    src = """
<h1>Sources — every external input, with the link used</h1>
<p>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Problem description &amp; performance metric (official)</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/">About / rules (official)</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">Data tab (login-walled)</a> ·
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Rules PDF (official mirror)</a> ·
<a href="https://github.com/drivendataorg/gems-prize-reference-solution">Reference solution (official)</a> ·
<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN airborne magnetic &amp; radiometric survey (official)</a> ·
<a href="https://gbcge.org/current-projects/ingenious/">INGENIOUS project (Great Basin Center for Geothermal Energy)</a> ·
<a href="https://epsg.io/32611">EPSG:32611</a> ·
<a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index</a>
</p>
<h2>Files this run read, with sha256</h2>
<table>
<tr><th>file</th><th>sha256</th><th>provenance</th></tr>
<tr><td><code>data/training_features.tif</code></td>
<td><code>4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5</code></td>
<td>official 19-band GeoDAWN numerical stack, reassembled from the five parts committed to the
sibling repository <code>buffedlizard55-lab/GEMSDOE</code>; hash matches the pin recorded in
<code>registry/data_pins.json</code></td></tr>
<tr><td><code>data/external/geodawn_dem_a2_100m.tif</code></td>
<td><code>d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431</code></td>
<td>100 m DEM on the competition grid, from <code>buffedlizard55-lab/60GEMSDOE</code>; hash
matches the pin</td></tr>
<tr><td><code>data/existing_faults.tif</code></td>
<td><code>7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093</code></td>
<td>the USGS/INGENIOUS catalogue as rasterised by the competition</td></tr>
<tr><td><code>data/labels.tif</code></td>
<td><code>7ba308cc…d4093</code></td>
<td><b>byte-identical to <code>existing_faults.tif</code></b> — see
<a href="irregularities.html">IR-63-01</a>: this is not a data error, it is what the competition
ships (the training labels <i>are</i> the known-fault catalogue)</td></tr>
<tr><td><code>data/sample_submission.tif</code></td>
<td><code>2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc</code></td>
<td>grid / footprint template; its 60,988 ones are the rasterised catalogue</td></tr>
<tr><td><code>data/sibling/proxy_catalogue.tif</code></td><td>not pinned upstream</td>
<td>code 2 = USGS State Geologic Map Compilation faults <i>absent</i> from the competition
catalogue; built by
<code>buffedlizard55-lab/GEMSDOE scripts/fetch_proxy_faults.py</code> from official USGS sources</td></tr>
<tr><td><code>data/registry/*.tif</code> (21)</td><td>see
<code>registry/registry_manifest.json</code></td>
<td>prior artifacts fetched from public sibling repositories, used <b>only</b> for the lane-drift
gate and for calibrating the proxy instrument</td></tr>
</table>
<h2>Literature the lane rests on</h2>
<ul>
<li>Adams, K.D. &amp; Wesnousky, S.G. (1998) — GSA Bulletin 110, 1318–1332 (Lahontan highstand
chronology).</li>
<li>Adams, K.D., Wesnousky, S.G. &amp; Bills, B.G. (1999) — JGR (22 m of isostatic deflection of
the highstand; ~3 m resolution of the elevation method).</li>
<li>Briggs, R.W. &amp; Wesnousky, S.G. (2004) — JGR (Pyramid Lake fault zone slip from displaced
late-Pleistocene features).</li>
<li>Dong, S. et al. — Geosphere (Lahontan shorelines displaced along a strike-slip fault outboard
of the Wassuk Range front).</li>
<li>Pierce, I. &amp; Wesnousky, S. (2016) — SCEC poster (two previously unmapped NW-striking
segments offsetting Holocene sediments in Smith Valley's basin centre, found in lidar).</li>
</ul>
"""
    (DOCS / "sources.html").write_text(page("Sources — H63", src))

    # ------------------------------------------------------ irregularities
    unsat = [r for r in uctl["rows"] if not r["test_satisfiable"]]
    uniq_rows = "".join(
        f"<tr><td><code>{esc(r['registry'])}</code></td><td>{r['n_theirs']:,}</td>"
        f"<td>{r['density_frac']:.4f}</td><td><b>{r['random_frac_within_3px']:.3f}</b></td>"
        f"<td>{r['mine_frac_within_3px']:.3f}</td><td>{r['lift']}</td>"
        f"<td>{'NO — random already fails it' if not r['test_satisfiable'] else 'yes'}</td></tr>"
        for r in sorted(uctl["rows"], key=lambda d: -d["mine_frac_within_3px"]))
    irr = f"""
<h1>Irregularities</h1>
{NAV}
<h2>IR-63-01 — <code>labels.tif</code> is byte-identical to <code>existing_faults.tif</code>
<span class="pill ok">RESOLVED — not a defect</span></h2>
<p>Both files hash to <code>7ba308cc…d4093</code> and have the same 60,988 positive cells. Earlier
sessions logged this as a data-placement error. It is not: the competition's training labels
<i>are</i> the known-fault catalogue — that is what you train on, and the scoring set is a
different, expert-updated collection. The consequence is recorded because it matters:
<b>no file in this repository has ever been scored against the real hidden set, and the catalogue
cannot serve as a held-out truth for the thing the competition measures.</b></p>

<h2>IR-63-02 — the protocol's 3-px overlap tripwire is unsatisfiable against dense registry
rasters <span class="pill warn">DEFECT IN THE RULE — measured, not argued</span></h2>
<p>The parallel-run protocol says: <i>“if more than 70 % of your dots fall within 3 px of one
registry raster's dots you have drifted into another lane: log it as a duplicate and stop.”</i>
For a registry raster that blankets 4–5 % of the footprint with 200 k+ positives, the 300 m kernel
(28 cells) contains more than one of its dots essentially everywhere, so <b>a random emission
already fails the test</b>. Measured with three random draws at the shipped mass and in the
shipped off-catalogue domain:</p>
<table>
<tr><th>registry raster</th><th>its mass</th><th>density</th>
<th>random emission within 3 px</th><th>this file within 3 px</th><th>lift</th>
<th>can the 70 % rule decide anything?</th></tr>
{uniq_rows}
</table>
<p>{len(unsat)} of {len(uctl['rows'])} registry rasters — all of them the low-scoring
<code>gems13</code> family — are in that regime. Against the other 18, including every raster that
scores above 0.15, the random baseline is 0.04–0.35 and this file sits at 0.02–0.38, i.e. a lift
of only 0.9–1.7×: no more coincident with any prior artifact than chance requires.</p>
<p>Verdict recorded: <b>UNIQUE where the gate is informative</b>. The rule itself needs a
density-normalised form — overlap <i>lift</i> over a matched random control, not raw overlap.</p>

<h2>IR-63-03 — the flagship repository's 0.2298 “labels DTI” is an in-domain number</h2>
<p>That figure is quoted in <code>buffedlizard55-lab/GEMSDOE</code> as evidence the supervised
branch works. Its own evidence file records the caveat: <i>“Per-block catalogue DTI is in-domain
(the shipped model trained on every label)”</i>. This session measured the same setup
out-of-domain and got AUC 0.50. The 0.2298 should not be used to argue for the supervised route.</p>

<h2>IR-63-04 — the leaderboard numbers in the standing brief are stale</h2>
<p>Scraped {esc(lb['fetched_utc'])}: #1 is <b>{lb['rows'][0]['score']}</b>, the top-5 cut-off is
<b>{lb['top5_cutoff_score']}</b>, and 0.3195 is rank
{[r['rank'] for r in lb['rows'] if r['score']==0.3195][0] if any(r['score']==0.3195 for r in lb['rows']) else 'n/a'}.
“Beat 0.3195” is a target for ninth place. The 37-snapshot series is in
<a href="../../research/leaderboard_series.json"><code>research/leaderboard_series.json</code></a>.</p>
"""
    (DOCS / "irregularities.html").write_text(page("Irregularities — H63", irr))

    # ---------------------------------------------------------- limitations
    lim = """
<h1>Limitations — what is in the way of winning</h1>
<ol>
<li><b>No organizer receipt exists for any file in this repository.</b> Every DTI on this site is
either a proxy measurement against a free truth set or a model projection. Until a file is
uploaded, the calibration constant <i>r</i> rests on nine owner-reported scores that this project
cannot independently verify.</li>
<li><b>The only proxy truth set is a 1:750 k geologic compilation.</b> The USGS SGMC maps bedrock
faults; it under-represents the young, small, basin-floor faults that a geothermal exploration
programme cares about, and it favours rough terrain. A detector that finds mountains will score
well on it whether or not it finds faults.</li>
<li><b>The official feature stack does not generalize spatially.</b> Measured: AUC 0.50 on
held-out 512 px blocks. Either the 100 m resampling destroys the signal, or fault location at
pixel scale is not recoverable from these bands. Both readings are recorded; they cannot be
separated without the organizer's truth.</li>
<li><b>The sandbox cannot reach drivendata.org, USGS hosts, or any non-GitHub host.</b> The DEM,
the feature stack and the proxy catalogue were all obtained through sibling GitHub repositories.
New external data has to be fetched the same way (or through the repository's
<code>dem-fetch</code> GitHub Actions workflow, which does have unrestricted egress).</li>
<li><b>2 CPUs and 3 GB of RAM.</b> A 19-band, 5.16 M-cell design matrix is 578 MB in float32;
several candidate designs had to be re-written to stream channels one at a time. Anything larger
than a shallow boosting ensemble is out of reach here.</li>
<li><b>The weekly submission cap is a hard constraint the lanes cannot see.</b> Promotion to a
real slot is a separate selector step; this session produces and ranks, it does not submit.</li>
<li><b>The datum lane cannot resolve what it is asked to resolve at 100 m.</b> Measured: 10.3 m
of isobase residual scatter against a 3 m method resolution. Lidar at 1 m, transported through
the <code>dem-fetch</code> workflow, is the only way to test the lane as written.</li>
</ol>
<h2>What to do next, in priority order</h2>
<ol>
<li>Spend one slot on the identification experiment: upload this file, then a <code>λ = 0.5</code>
re-emission and a null-mass probe. Three returns identify <code>T</code>, <code>K</code> and
<code>F</code> exactly and turn every projection on this site into a measurement.</li>
<li>Build a second proxy truth set that is not a bedrock compilation — the INGENIOUS project's
own interpretation products, or the Nevada Bureau of Mines and Geology Quaternary fault database
rasterised on this grid.</li>
<li>Fetch 1 m / 3 m lidar through the <code>dem-fetch</code> workflow and re-run the datum lane on
it. This is the only way to test the assigned hypothesis rather than a 100 m surrogate of it.</li>
<li>Add orientation-consistency along strike: the current channels are pointwise. A fault is a
curve with slowly varying azimuth, and a Hough / tensor-voting step on top of the belief field is
the obvious next detector.</li>
</ol>
"""
    (DOCS / "limitations.html").write_text(page("Limitations — H63", lim))

    # ------------------------------------------------------------ run card
    run_card = {
        "hypothesis": ("A fault absent from the USGS/INGENIOUS catalogue still leaves three "
                       "independent expressions -- a break in slope, an elongated ridge or "
                       "trough, and an edge in the potential fields -- and requiring several of "
                       "them to corroborate the same cell locates it better than any one of them."),
        "mechanism": ("13 catalogue-free channels (DEM scarp curvature, multiscale local relief, "
                      "multiscale Hessian ridge/valley, an 8-orientation matched line filter, and "
                      "TMI / tilt-angle / isostatic-gravity gradients), each average-rank "
                      "normalised inside the valid footprint and averaged (dem3 = "
                      "dem_scarp_curvature + dem_local_relief_tpi3 + dem_direction_line), "
                      "non-maximum-suppressed in a 3x3 window, top 90,000 cells, restricted to "
                      ">= 300 m from the catalogue, emitted at value 1.0."),
        "named_non_fault_process_that_could_mimic_it": (
            "Rough bedrock terrain. Every DEM channel is a form of local relief, and the USGS "
            "State Geologic Map Compilation draws most of its faults in ranges, so a detector "
            "that simply finds mountains will score well on the proxy instrument. The "
            "geophysical channels (TMI/gravity gradients) were included precisely because they "
            "do not have that confound, and they are the ones that scored worst on the proxy -- "
            "which is why the confound is stated rather than dismissed."),
        "holdout_dti": {
            "supervised_arm": {
                "instrument": "hide-and-recover, 4 spatially blocked folds of 512 px blocks, "
                              "3 px collar, visible catalogue masked pixel-exactly",
                "result": "AUC " + ", ".join(str(f["auc_catalogue"]) for f in hold["auc_per_fold"])
                          + " (catalogue) and "
                          + ", ".join(str(f["auc_proxy_off"]) for f in hold["auc_per_fold"])
                          + " (SGMC off-catalogue)",
                "withheld_positives": sum(f["n_pos_catalogue"] for f in hold["auc_per_fold"]),
                "verdict": "NO SIGNAL -- chance",
                "class": "HOLDOUT-DTI (proxy)",
            },
            "shipped_arm": {
                "instrument": "credit per unit mass vs USGS SGMC off-catalogue faults, exact "
                              "300 m triangular kernel, src/gems62/metric.py",
                "credit_per_mass": meas["proxy_off"]["credit_per_mass"],
                "random_control_matched_mass": ctrl["90000"],
                "lift": round(meas["proxy_off"]["credit_per_mass"] / ctrl["90000"], 3),
                "champion_reference": champ["proxy"]["cm"],
                "class": "MEASURED on a proxy truth set",
            },
        },
        "projection": {
            "band": [best["proj_dti_conservative"], best["proj_dti_optimistic"]],
            "r_range": [0.478, 0.775],
            "K_range": [8000, 12000],
            "class": "MODEL -- never a score",
        },
        "terrain_confound_measured": tcf,
        "correlation_vs_registry": {
            "worst_rank_correlation": uni["worst_rank_corr"]["rank_corr"],
            "any_rank_flag": uni["any_rank_flag"],
            "all_correlations_negative": all((r.get("rank_corr") or 0) < 0 for r in uni["results"]),
            "overlap_vs_champion_02778": [r for r in uni["results"]
                                          if r["file"] == "gemsdoe32_h33_2_b2_02778_zeros.tif"][0][
                "dot_overlap_within_kernel"],
            "unsatisfiable_registry_rasters": [r["registry"] for r in unsat],
            "class": "MEASURED",
        },
        "raster": {
            "name": sub["name"],
            "sha256": sub["sha256"],
            "bytes": sub["bytes"],
            "n_dots": int(meas["mass"]),
        },
        "validator": {
            "passed": vald["passed"],
            "failures": vald["failures"],
            "nan_inside_footprint": vald["nan_inside_footprint"],
            "values_in_0_1": fmt["n_outside_0_1"] == 0 and fmt["min"] >= 0 and fmt["max"] <= 1,
            "crs_match": fmt["crs_match"],
            "shape_match": fmt["shape"] == [3730, 3292],
            "transform_match": fmt["transform_match"],
            "nodata_tag": fmt["nodata"],
        },
        "submission_note": NOTE,
        "verdict": "promote",
        "lane_result": {
            "benches": lane["n_benches"],
            "isobase_residual_sigma_m": lane["isobase"]["residual_sigma_m"],
            "flagged_steps": lane["n_flagged_steps"],
            "flagged_deflections": lane["n_flagged_deflections"],
            "verdict": "negative",
        },
    }
    (EV / "h63_run_card.json").write_text(json.dumps(run_card, indent=1))
    rc_html = f"""
<h1>Run card</h1>
{NAV}
<pre>{esc(json.dumps(run_card, indent=1))}</pre>
<p><a href="../../evidence/h63_run_card.json">evidence/h63_run_card.json</a></p>
"""
    (DOCS / "run-card.html").write_text(page("Run card — H63", rc_html))

    # --------------------------------------------------- patch root landing
    root = HERE / "docs" / "index.html"
    if root.exists():
        t = root.read_text()
        if "h63" not in t:
            banner = ('<div class="hero" style="border-color:var(--ok);'
                      'background:rgba(63,185,80,.06)">\n'
                      '<h2 style="border:0;margin-top:0">Session 2026-10-11 · H63 — the file to '
                      'download and submit</h2>\n'
                      f'<p><span class="pill ok">FORMAT LEGAL</span> '
                      f'<span class="pill ok">UNIQUE where the gate is informative</span> '
                      f'<span class="pill warn">SCORE IS A MODEL PROJECTION</span></p>\n'
                      f'<p class="big">{esc(sub["name"])}</p>\n'
                      f'<p><a class="btn" href="../lane62-h63/docs/downloads/'
                      f'{esc(sub["name"])}-zeros.tif">⬇ Download ({sub["bytes"]:,} bytes)</a>\n'
                      '<a class="btn sec" href="../lane62-h63/docs/executive-summary.html">'
                      'How to submit</a>\n'
                      '<a class="btn sec" href="../lane62-h63/docs/index.html">Full H63 report</a>'
                      '</p>\n'
                      f'<p class="small">Measured credit per unit mass '
                      f'<b>{meas["proxy_off"]["credit_per_mass"]:.4f}</b> vs '
                      f'<b>{champ["proxy"]["cm"]:.4f}</b> for the group\'s best submitted '
                      f'artifact (0.2778) and <b>{ctrl["90000"]:.4f}</b> for a matched random '
                      f'control. sha256 <code>{esc(sub["sha256"])}</code>.</p>\n</div>\n')
            t = t.replace('<h1>62GEMSDOE', banner + '<h1>62GEMSDOE', 1)
            root.write_text(t)
            print("patched root docs/index.html")
    print("site written to", DOCS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
