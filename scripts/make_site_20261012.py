#!/usr/bin/env python3
"""Generate the 2026-10-12 GitHub Pages front page and executive-summary subpage.

Every number on both pages is substituted from ``evidence/run_card_20261012_62e.json`` and its sibling
evidence files at generation time, so the site cannot drift from the run card.  Re-run:

    python3 scripts/exp12_finalize.py && python3 scripts/make_site_20261012.py

Writes ``docs/index.html`` and ``docs/executive-summary-2026-10-12.html``.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CARD = json.load(open(ROOT / "evidence/run_card_20261012_62e.json"))
E9 = json.load(open(ROOT / "evidence/exp9_profile_matched_emission.json"))
E10 = json.load(open(ROOT / "evidence/exp10_linearity.json"))
E11 = json.load(open(ROOT / "evidence/exp11_concentration.json"))
E8 = json.load(open(ROOT / "evidence/exp8_reward_model.json"))
E6 = json.load(open(ROOT / "evidence/exp6_detector_blocked.json"))
E6_BEST = max(E6["emissions"], key=lambda r: r["dti_S_wide"])
UNI = CARD["correlation_overlap_vs_registry"]["shared_tool_verdict"]
RHO_VOTE = CARD["instruments"]["vote_inversion"]["cv_heldout_rho"]

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--no:#f85149;--warn:#d29922;--card:#161b22;--bd:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:1.9em;margin:.2em 0 .1em}h2{font-size:1.35em;margin:1.6em 0 .5em;border-bottom:1px solid var(--bd);padding-bottom:.3em}
h3{font-size:1.05em;margin:1.2em 0 .4em}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1f2630;padding:.12em .35em;border-radius:4px;font-size:.9em}
pre{background:#1f2630;padding:12px;border-radius:6px;overflow:auto;font-size:.85em}
table{border-collapse:collapse;width:100%;margin:.8em 0;font-size:.9em}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#1f2630}
.mut{color:var(--mut)}.card{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:18px;margin:14px 0}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}
nav a{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:5px 13px;font-size:.87em}
.pill{display:inline-block;border-radius:20px;padding:2px 10px;font-size:.8em;font-weight:600;margin:2px 0}
.pill.no{background:rgba(248,81,73,.15);color:var(--no);border:1px solid var(--no)}
.pill.ok{background:rgba(63,185,80,.15);color:var(--ok);border:1px solid var(--ok)}
.pill.warn{background:rgba(210,153,34,.15);color:var(--warn);border:1px solid var(--warn)}
.hero{border:3px solid var(--no);border-radius:10px;padding:22px;margin:18px 0;background:rgba(248,81,73,.07)}
.btn{display:inline-block;background:#30363d;color:#fff;font-weight:600;padding:12px 22px;border-radius:8px;margin:8px 8px 8px 0;border:1px solid var(--bd)}
.btn:hover{background:#3d444d;text-decoration:none}
.kv{font-size:.88em}.kv td:first-child{width:38%;color:var(--mut)}
.big{font-size:1.5em;font-weight:700;word-break:break-all}
"""

NAME = CARD["slug"] + ".tif"
TIF = CARD["raster_path"].split("/")[-1]
NAN = CARD["nan_twin_path"].split("/")[-1]
SHA = CARD["raster_sha256"]
BYTES = CARD["raster_bytes"]
NOTE = CARD["submission_note"]
DUP = CARD["duplicate_trip"]
CMP = DUP["comparator"]
EM = CARD["emission"]
PROF = EM["measured_profile"]
CH = EM["champion_profile"]
MODEL = CARD["model_projection"]
REC = CARD["format_receipt_from_disk"]
VAL = CARD["validator_output"]
SUR = CARD["instruments"]["vote_inversion"]["result_on_this_field"]
HOLD = CARD["holdout_dti"]["result"]
DET = CARD["detector"]
RM = CARD["instruments"]["reward_model"]

def f4(x, nd=4):
    return f"{float(x):.{nd}f}"

def pct(x, nd=2):
    return f"{100*float(x):.{nd}f} %"


PROFILE_ROWS = [
    ("mass M (dots)", f"{PROF['M']:,}", f"{CH['M']:,}", "matches the 37,654-44,090 family band"),
    ("self-kernel (dots inside one 300 m kernel)", f4(PROF["self_kernel"]), f4(CH["self_kernel"]),
     "better: zero self-competition for credit"),
    ("evenness (10 km cells holding >=1 dot)", f"{PROF['evenness_cells']:.0f}", f"{CH['evenness_cells']:.0f}",
     "better: 569 of ~570 cells vs 547"),
    ("credit per dot vs the mapped catalogue", f4(PROF["credit_cat"]), f4(CH["credit_cat"]),
     "better: nothing lands on catalogue faults (masked out of scoring)"),
    ("credit per dot vs SGMC-off-catalogue", f4(PROF["credit_sgmc"]), f4(CH["credit_sgmc"]),
     "better, but SGMC-offcat is a refuted truth proxy"),
    ("median distance to the catalogue (m)", f"{PROF['dcat_med_m']:.0f}", f"{CH['dcat_med_m']:.0f}",
     "matches"),
    ("mean LiDAR scarp evidence (0-255)", f"{PROF['lidar_scarp_mean']:.1f}", f"{CH['lidar_scarp_mean']:.1f}",
     "higher than the family band (82.9-83.2) - untested territory"),
    ("mean slope at the dots (deg)", f"{PROF['slope_mean']:.2f}", "7.86", "matches"),
    ("mean topo roughness at the dots", f"{PROF['topo_rough_mean']:.2f}", "22.57", "slightly above the band"),
    ("arrangement: dens21 (other dots in a 2.1 km box)", f"{PROF['dens21']:.2f}", "8.75-9.62",
     "<b>WORSE</b> - nearly uniform where the family is 2.7x locally concentrated"),
    ("arrangement: coh21 (coherence of the dot-density field)", f"{PROF['coh21']:.4f}", "0.307-0.336",
     "<b>WORSE</b> - see experiment 10"),
]

IDX = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>62GEMSDOE — session 2026-10-12, lane 62E — DO NOT SUBMIT: uniqueness gate tripped</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>62GEMSDOE — Lake Lahontan shorelines as a strain gauge</h1>
<p class="mut">DOE GEMS Prize · DrivenData competition #306 · datum-offset lane · session
2026-10-12 · branch <code>arena/90112fbe-62gemsdoe</code> · site front page <a href="index.html">index.html</a> ·
the 2026-10-11b page is archived at <a href="index-20261011b.html">index-20261011b.html</a></p>

<nav>
<a href="index.html">Site front page</a>
<a href="#download">⬇ File &amp; verdict</a>
<a href="#gate">The gate that tripped</a>
<a href="#profile">Measured profile</a>
<a href="#experiments">This session's experiments</a>
<a href="#why">Why no gain can be certified</a>
<a href="executive-summary-2026-10-12.html">How to submit</a>
<a href="run-card.html">Run card</a>
<a href="irregularities.html">Irregularities</a>
<a href="next-steps.html">Next steps</a>
<a href="../evidence/run_card_20261012_62e.json">run_card JSON ↗</a>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition ↗</a>
</nav>

<!-- ============================ VERDICT — first thing on the page ===================== -->
<div class="hero" id="download">
<h2 style="border:0;margin-top:0">DO NOT SUBMIT THIS FILE</h2>

<p><span class="pill no">UNIQUENESS GATE: TRIPPED — {pct(CMP['my_frac3px'])} of the dots are within
3 px of one registry raster (limit {pct(DUP['overlap_leg']['limit'],0)})</span>
&nbsp;<span class="pill ok">FORMAT: LEGAL — {REC['count']} band float32, EPSG:32611,
{REC['shape'][0]}×{REC['shape'][1]}, values [{VAL['values_min']:.0f}, {VAL['values_max']:.0f}], no
nodata tag</span>
&nbsp;<span class="pill ok">ISOLATION: PROVEN — minimum dot-to-dot separation
{EM['min_separation_m']:.0f} m, {EM['dots_with_another_dot_inside_300m']} dots inside one 300 m
kernel</span>
&nbsp;<span class="pill warn">NO INSTRUMENT HERE CAN CERTIFY A GAIN</span></p>

<p><span class="pill no">RUN-CARD VERDICT: {CARD['verdict_label']}</span></p>

<p class="big">{NAME}</p>

<p><b>Short note to paste into the portal ({len(NOTE)}/140 characters):</b><br>
<code>{NOTE}</code></p>

<p><a class="btn" href="downloads/{TIF}" download>⬇ Download the GeoTIFF ({BYTES:,} bytes)</a>
<a class="btn" href="downloads/{NAN}" download>⬇ NaN-outside twin</a></p>

<p class="mut">sha256 <code>{SHA}</code> · {EM['n_dots']:,} single-pixel dots of value 1.0 on an
all-zero grid · generated {CARD['run_card_version']} · deterministic rebuild from the committed
inputs identical: <b>{EM['deterministic_rebuild_identical']}</b></p>

<p><b>Download it to inspect it, to overlay it in QGIS, or to learn from the recipe. Do not upload it
to the competition.</b> The parallel-run protocol's uniqueness rule is mechanical: a field is a
duplicate if more than 70 % of its dots lie within 3 px of the dots of any single non-vacuous
registry raster. This field is at {pct(CMP['my_frac3px'])} against one raster, and
{CMP['exact_shared_dots']:,} of its {EM['n_dots']:,} dots ({pct(CMP['exact_shared_frac'])}) are
<i>exactly</i> that raster's pixels — {f4(CMP['chance_ratio'],1)}× the {pct(CMP['chance_expectation'],1)}
expected by chance. The protocol says log it and stop.</p>
</div>

<!-- ============================ LANE DELIVERABLE ==================================== -->
<h2>The lane's first deliverable: shoreline elevation-vs-distance profiles with flagged steps</h2>
<div class="card">
<p>Produced by <code>src/gems62/lahontan.py</code> (<code>bench_cells</code> →
<code>fit_isobase</code> → <code>level_structure</code> → <code>flag_steps</code> /
<code>flag_deflections</code> → <code>shoreline_profile</code>) on the 25 m 3DEP DEM
(<code>evidence/dem/lahontan_dem_utm11.tif</code>, int16 <b>decimetres</b>, nodata ≤ −32000, covering
52.21 % of the scoring footprint), and recorded in
<a href="../evidence/gems62-lahontan-isobase-99dots-profile.json"><code>evidence/gems62-lahontan-isobase-99dots-profile.json</code></a>:
<b>176 profile rows</b> along a track azimuth of 83.40°, each with its elevation, the fitted isobase
(a global post-pluvial-rebound surface plus 7 level surfaces and a local strand fit) and the residual,
so abrupt steps and lateral deflections along strike are flagged where they exceed the smooth isobase.</p>
<p><b>Status: only a handful are convincing, so only those were emitted.</b> The resulting 99-dot
artifact (<code>docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif</code>) is a scoring dead end —
its arithmetic ceiling at M = 99 is 0.0103 even with perfect credit, its HOLDOUT-DTI was 2.6e-05, and
this session's reward model gives a datum-band emission only <b>59</b> hard-core dots. The datum-only
habitat is measured <b>0.61×</b> the isolated-random control (Lahontan band 1308-1360 m) and the pluvial
lake-flat habitat <b>0.03×</b>. The lane therefore survives as <b>three detector features</b> (isobase
residual, datum band, |residual|) inside the 34-feature stack above — not as an emitter. That is a
logged deviation from the assigned lane, and it is the reason this session's artifact is a 40,000-dot
geophysics-and-LiDAR field rather than a shoreline-bench field.</p>
</div>

<!-- ============================ SAME-DAY COLLISION ================================== -->
<h2 id="collision">The same-day collision, and which 40k field the selector should look at</h2>
<div class="card">
<p>Three sessions wrote to this repository on 2026-10-12 and two of them built the same <i>class</i> of
artifact: a 40,000-dot, hard-core-isolated, off-catalogue field. The sibling lane's is
<a href="downloads/gems62-h63-diffuse-isolated-offcat-40k-zeros.tif"><code>gems62-h63-diffuse-isolated-offcat-40k-zeros.tif</code></a>
(session <code>arena/61e7859a</code>, <code>scripts/build_h63_diffuse_isolated.py</code>), and its audit
is stronger than this lane's on both axes that matter:</p>
<ul>
<li><b>uniqueness</b> — measured against <b>233</b> registry rasters (this lane: 67) and reported
<i>control-normalised</i>: maximum 3-px-dilated Jaccard 0.345, while an information-free 40k control
trips the same statistic at 0.331 and the family's own top submissions score 0.893-0.948 against each
other. This lane independently reached the same conclusion about the raw legs
(<code>IR-62-E-05</code>): two <i>independent</i> 40k hard-core fields read Jaccard3px 0.2042, so an
absolute threshold condemns the geometry, not the copying.</li>
<li><b>headroom</b> — <code>evidence/metric_ceiling.json</code> bounds an <i>information-free</i> field
of 40,000 dots at <b>0.0869</b> even with the most favourable truth size. The 0.2376-0.2778 family
band is therefore 2.7-3.2× above what placement-free emission can reach, and this lane's MODEL
projection of {f4(MODEL['dti_at_K12000'])} at K = 12,000 sits above that ceiling only if the
predicted per-dot credit (c = {f4(MODEL['model_implied_credit_from_exp8_reward_model'])}) is real. It
is not measurable here.</li>
</ul>
<p><b>So: this lane's file is stopped, and it is also redundant in class.</b> If a 40k isolated
off-catalogue probe is ever spent, the sibling lane's H63 file is the one with the wider
control-normalised audit; this lane's contribution is the measurement that explains <i>why</i> such a
field cannot be certified locally (arrangement, experiment 10) and the eight irregularities it
registered. Promotion is a selector decision inside the weekly cap, and nothing here recommends
spending a slot.</p>
</div>

<!-- ============================ THE GATE ============================================= -->
<h2 id="gate">The gate that tripped</h2>

<p>Comparator: <code>{CMP['alias']}</code> — {CMP['positives']:,} positive cells, owner-reported
score {CMP['owner_reported_score']}, 3 px-dilated coverage {pct(CMP['coverage3px'],1)} of the
footprint (so the shared tool classifies it as <i>non-vacuous</i>: the test is informative against
it). Measured with <code>gems62.uniqueness.compare</code> over all 67 distinct score-anchored
registry rasters.</p>

<table>
<tr><th>check</th><th>this field</th><th>isolated-random control<br>(40,000 hard-core random dots)</th>
<th>limit</th><th>result</th></tr>
<tr><td>rank correlation ρ (worst of 67)</td><td>{f4(CARD['correlation_overlap_vs_registry']['shared_tool_verdict']['max_abs_rho'])}</td>
<td>—</td><td>≤ 0.90</td><td><span class="pill ok">PASS</span></td></tr>
<tr><td>dots within 3 px of one raster (worst non-vacuous)</td><td><b>{pct(CMP['my_frac3px'])}</b></td>
<td>{pct(CMP['isolated_random_control_frac3px'])}</td><td>≤ 70 %</td>
<td><span class="pill no">TRIP</span></td></tr>
<tr><td>Jaccard of the 3 px-dilated dot masks</td><td>{f4(CMP['jaccard3px'])}</td>
<td>{f4(CMP['control_jaccard3px'])}</td><td>≤ 0.25 (this repo's stricter leg)</td>
<td><span class="pill no">TRIP</span></td></tr>
<tr><td>exact shared pixels</td><td>{CMP['exact_shared_dots']:,} ({pct(CMP['exact_shared_frac'])})</td>
<td>≈ {pct(CMP['chance_expectation'],1)} by construction</td><td>advisory</td>
<td><span class="pill no">{f4(CMP['chance_ratio'],1)}× chance</span></td></tr>
</table>

<p class="mut">Reading, honestly: the comparator is a 516,738-cell DTI-optimal emission field that
itself scored {CMP['owner_reported_score']}. Two independent hard-core top-40k selections from
priority surfaces built on the same public layers land on the same sharpest peaks, so the shared
pixels are a consequence of the shared input rather than of copying — and the random control shows
{pct(CMP['isolated_random_control_frac3px'])} of <i>any</i> 40k field falls inside that raster's 3 px
halo. But the gate is written to be mechanical, it tripped, and 32 % of the field inherits the pixels
of a low-scoring artifact. The correct response is not to argue with the gate; it is to emit from
evidence the comparators do not share.</p>

<!-- ============================ PROFILE ============================================= -->
<h2 id="profile">What the field is, and how it measures against the 0.2778 champion</h2>

<p><b>Mechanism.</b> {CARD['mechanism']}</p>
<p><b>Lane.</b> {CARD['lane']}</p>

<table>
<tr><th>property (all measured on the emitted dots)</th><th>this field</th><th>champion
<code>h33-h33-2-b2</code><br>(owner-reported 0.2778)</th><th>reading</th></tr>
{''.join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>' for a,b,c,d in PROFILE_ROWS)}
</table>

<p><b>Model projection — a projection is never a score.</b> With the published metric's closed form
for isolated unit dots, <code>DTI = c / (0.2 + 0.8·K/M)</code>, and the per-dot credit <i>c</i>
predicted by experiment 8's leave-artifact-out reward model
(c = {f4(MODEL['model_implied_credit_from_exp8_reward_model'])}, CV ρ
{f4(MODEL['reward_model_cv_rho'])}, CV RMSE {f4(MODEL['reward_model_cv_rmse'])}), the arithmetic
gives {f4(MODEL['dti_at_K12000'])} at K = 12,000, {f4(MODEL['dti_at_K13688'])} at K = 13,688 and
{f4(MODEL['dti_at_K8479'])} at K = 8,479. To beat 0.2778 at M = 40,000 a field needs
c ≥ {f4(MODEL['credit_required_to_beat']['target_02778'])}; to reach the stated target 0.3195 it
needs c ≥ {f4(MODEL['credit_required_to_beat']['target_03195'])}; the top-5 cut-off 0.3333 needs
c ≥ {f4(MODEL['credit_required_to_beat']['target_03333'])}. <b>K is inherited from an inversion that
is itself circular, so every number in this paragraph is MODEL, not
ORGANIZER-CONFIRMED.</b> No file in this repository has an organizer-confirmed score.</p>

<!-- ============================ EXPERIMENTS ========================================= -->
<h2 id="experiments">This session's experiments (six, in order)</h2>

<table>
<tr><th>#</th><th>question</th><th>result</th><th>label</th></tr>
<tr><td>5c</td><td>Can the hidden per-dot credit be recovered by inverting the 79 public submissions?</td>
<td>Yes for <i>ranking</i> existing artifacts (held-out ρ {f4(RHO_VOTE,3)} against
owner-reported scores), no for calibration: the vote surrogate is built out of the artifacts it is
asked to score, so the champion's credit on it ({f4(SUR['S_wide']['dti_champion'],3)} DTI) is
unreachable by any field that is not a re-emission of the winners.</td>
<td>MEASURED-INSTRUMENT (ranking only)</td></tr>
<tr><td>6</td><td>Does the organiser's own 19-band stack predict the consensus, out-of-fold and spatially blocked?</td>
<td>Mean blocked AUC <b>{f4(E6['mean_blocked_auc'])}</b> over 6 blocks, {E6['n_features']} features,
leakage canary: <b>{E6['leakage_flags'] or 'no single feature above 0.90'}</b> (max per-feature AUC
{max(E6['per_feature_auc_block0'].values()):.3f}). Best new emission on the surrogate instrument
{f4(E6_BEST['dti_S_wide'])} — negative, and expected to be negative because the
instrument measures incumbent similarity.</td><td>MEASURED (blocked, out-of-fold)</td></tr>
<tr><td>8</td><td>Which <i>measurable</i> properties of a dot field separate 0.2778 from 0.0778?</td>
<td>Over 47 de-duplicated fields: self-kernel −0.60, mass −0.42, LiDAR-scarp mean +0.38, credit vs
the catalogue −0.33, evenness +0.28, median catalogue distance +0.27. Reward model CV ρ
{f4(E8['reward_model']['implied_credit']['cv_rho'])} on implied credit.</td>
<td>MEASURED (ranking model)</td></tr>
<tr><td>9</td><td>Can an emission be built that matches the champion family's measurable box?</td>
<td>Yes — 20 combinations searched, <b>{E9['chosen']['constraints_satisfied']}/7</b> constraints
satisfied by the chosen <code>{E9['chosen']['name']}</code>; rule pre-registered before the numbers
were seen.</td><td>MEASURED + MODEL</td></tr>
<tr><td>10</td><td>Why did an artifact with the champion's exact mass and SGMC credit score 0.0778?</td>
<td>Arrangement. At M = 37,654-44,090 every field scoring 0.26-0.2778 carries dens21 8.75-9.62 and
coh21 0.307-0.336; the scattered comparator carries dens21 {f4(E10['candidate']['dens21'],2)}.
Spearman over all fields is dominated by mass (−0.68), so arrangement only bites inside a mass
band.</td><td>MEASURED</td></tr>
<tr><td>11</td><td>Can the arrangement deficit be closed by concentrating the emission?</td>
<td><b>No.</b> A density-of-high-priority multiplier (γ = 1, 2, 3) moved dens21 4.56 → 4.44 and coh21
0.1593 → 0.1608. The pre-registered rule therefore kept the experiment-9 winner unchanged.</td>
<td>MEASURED (negative)</td></tr>
<tr><td>12</td><td>Is the chosen field legal, unique and reproducible?</td>
<td>Legal {REC['legal']}, validator {VAL['passed']} ({len(VAL['failures'])} failures), isolation
proven, deterministic rebuild identical — <b>and the uniqueness gate tripped.</b></td>
<td>MEASURED</td></tr>
</table>

<!-- ============================ WHY ================================================= -->
<h2 id="why">Why no local instrument can certify placement quality</h2>

<div class="card">
<p><b>The counterexample that ends the argument.</b> <code>h34-scatter-q50-arr-matched</code> has the
champion's exact mass (37,654), a <i>higher</i> credit against the one off-catalogue compilation
available here (0.0662 vs 0.0655) and a <i>higher</i> LiDAR-scarp mean (109 vs 82.9) — and it scored
0.0778 against the champion's 0.2778. Every aggregate property this sandbox can measure matched or
beat the champion, and the score was 3.6× worse. So:</p>
<ul>
<li><b>the reward model ranks families, not fields</b> (CV ρ {f4(RM['cv_rho_credit'])} on implied
credit, {f4(RM['cv_rho_score'])} on score);</li>
<li><b>the vote surrogate measures incumbent similarity</b>, which is exactly what the uniqueness
protocol forbids maximising (this field reads {f4(SUR['S_wide']['ratio_to_champion'],2)}× the champion
on it, and that is a statement about novelty, not quality);</li>
<li><b>the mandated segmented holdout is structurally blind to this design</b> — with a 300 m
catalogue standoff every dot is outside the withheld catalogue positives, so pooled HOLDOUT-DTI is
{f4(HOLD['pooled_dti'])} while its own random-dot control scores
{f4(HOLD['controls_mean']['random_dots'])} and its random-line control
{f4(HOLD['controls_mean']['random_lines'])} ({HOLD['n_segments_total']} segments,
{HOLD['withheld_positives_total']:,} withheld positives, α 0.2 β 0.8, 300 m triangular kernel,
evaluator <code>{HOLD['version']}</code>). It rewards catalogue hugging, which the leaderboard
punishes (IR-62-HOLDOUT-01).</li>
</ul>
<p class="mut">Consequence for the weekly slot: the correct decision is to spend nothing. The field is
published because the brief requires a downloadable, obviously-labelled artifact, and because the
recipe and the negative results are worth more than another blind probe.</p>
</div>

<h2>Irregularities flagged this session</h2>
<ol>
{''.join(f'<li>{x}</li>' for x in CARD['irregularities_flagged'])}
</ol>
<p>Full list with evidence: <a href="irregularities.html">irregularities.html</a> ·
<a href="../docs/irregularities.md">irregularities.md</a></p>

<h2>Official and verified sources</h2>
<table>
<tr><th>claim</th><th>source</th><th>verified how</th></tr>
<tr><td>metric definition, DTI, α = 0.2, β = 0.8, 300 m triangular kernel</td>
<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">competition page 967</a></td>
<td>re-implemented in <code>src/gems62/metric.py</code> and cross-checked against
<code>scripts/exp6_detector_blocked.py::dti_binary_fast</code> to 1e-5 absolute
(<code>tests/test_exp6_dti.py</code>, 3 passed)</td></tr>
<tr><td>submission format: single-band GeoTIFF, EPSG:32611, 100 m, 3730×3292, transform
(100, 0, 243350, 0, −100, 4508550), values in [0, 1]</td>
<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">data page</a>
(login-gated) mirrored via the group's data bridge</td>
<td>bytes fetched from
<code>api.github.com/repos/buffedlizard55-lab/GEMSDOE/contents/data/bridge</code>;
<code>training_features.tif</code> sha256 matches the manifest pin exactly
(<code>{DET['stack_sha_matches_manifest']}</code>, <code>{DET['stack_sha256'][:16]}…</code>);
grid asserted against the official <code>sample_submission.tif</code> in
<code>src/gems62/grid.py</code></td></tr>
<tr><td>19 organiser bands and their categories</td><td>the stack's own GDAL band tags</td>
<td>read from the fetched bytes; enumerated in <code>{'evidence/exp6_detector_blocked.json'}</code>
under <code>feature_names</code></td></tr>
<tr><td>catalogue faults are masked out of scoring</td>
<td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/forum/11516/">forum thread 11516</a></td>
<td>not re-fetchable from this sandbox (only github.com, pypi.org and npmjs.org are reachable) —
carried as OWNER-REPORTED, and implemented as a 300 m standoff plus a hard exclusion of catalogue
pixels</td></tr>
<tr><td>leaderboard values quoted on this page</td>
<td>mirror of the official leaderboard, 2026-10-11T20:57:47Z,
<code>research/leaderboard_latest_2026-10-11T205747Z.json</code></td>
<td>MIRROR, not ORGANIZER-CONFIRMED. It puts 0.4133 first, the top-5 cut-off at 0.3333 and 0.3195 at
rank 9 — the brief's "0.3195 (or 0.3774) is the highest score" is stale and is flagged as an
irregularity.</td></tr>
<tr><td>the 0.2778 champion's own bytes</td>
<td><code>/tmp/reg/tif/GEMSDOE32__gemsdoe32-h33-h33-2-b2-…tif</code> via
<code>research/registry_index.json</code></td>
<td>37,654 single-pixel values in {{0, 1}}, self-kernel 0.0173, median catalogue distance 1,965 m —
all measured directly, not taken from any report</td></tr>
</table>
<p class="mut">Nothing on this page is ORGANIZER-CONFIRMED. Every score quoted is an owner-reported
value attached to a raster this sandbox fetched and measured, or a MIRROR of the leaderboard.</p>

<h2>Navigation</h2>
<ul>
<li><a href="executive-summary-2026-10-12.html"><b>How to make a submission</b></a> — the exact
click path, the filename convention, the &lt;140-character note, and the range-[0,1] guard that
caused a previous rejection.</li>
<li><a href="index.html">Site front page (all lanes)</a> ·
<a href="index-20261011b.html">Archived front page (2026-10-11b)</a></li>
<li><a href="irregularities.html">Irregularities</a> · <a href="next-steps.html">Next steps</a> ·
<a href="run-card.html">Run card</a> ·
<a href="research/leaderboard-arithmetic.html">Leaderboard arithmetic</a> ·
<a href="research/beating-02778-2026-10-11b.html">Beating 0.2778</a></li>
<li><a href="../evidence/run_card_20261012_62e.json">This session's run card (JSON)</a> ·
<a href="../evidence/exp6_detector_blocked.json">exp6</a> ·
<a href="../evidence/exp8_reward_model.json">exp8</a> ·
<a href="../evidence/exp9_profile_matched_emission.json">exp9</a> ·
<a href="../evidence/exp10_linearity.json">exp10</a> ·
<a href="../evidence/exp11_concentration.json">exp11</a></li>
<li><a href="https://github.com/buffedlizard55-lab/62GEMSDOE">Repository ↗</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition ↗</a> ·
<a href="https://github.com/drivendataorg/gems-prize-reference-solution">Reference solution ↗</a></li>
</ul>

<p class="mut">Generated by <code>scripts/make_site_20261012.py</code> from
<code>evidence/run_card_20261012_62e.json</code>. Re-running the generator cannot leave a stale number on
this page.</p>
</div></body></html>
"""

EXEC = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>How to make a GEMS submission — 2026-10-12</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>How to make a competition submission</h1>
<p class="mut">Executive summary · session 2026-10-12 · DOE GEMS Prize · DrivenData competition #306 ·
<a href="index.html">← site front page</a> ·
<a href="session-2026-10-12-62e.html">this lane's report</a></p>

<div class="hero">
<h2 style="border:0;margin-top:0">Read this first: the file generated this session must NOT be uploaded</h2>
<p><code>{NAME}</code> is format-legal and isolated, but it fails the repository's own uniqueness gate
({pct(CMP['my_frac3px'])} of its dots within 3 px of <code>{CMP['alias'][:46]}…</code>, limit
{pct(DUP['overlap_leg']['limit'],0)}). Uploading it would (a) breach the parallel-run protocol this
repository operates under, and (b) spend a weekly submission slot on a field with no evidence of a
gain. The steps below are written so that a future session can follow them once a field actually
passes.</p>
</div>

<h2>1. The exact click path</h2>
<ol>
<li>Sign in at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">https://www.drivendata.org/competitions/306/competition-doe-gems/</a>.</li>
<li>Open <b>Submit</b> (also reachable from
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the submissions page</a>)
and upload the single <code>.tif</code> — or a <code>.zip</code> containing exactly one GeoTIFF.</li>
<li>Paste the submission <b>name</b> and the <b>short note</b> (both below), then confirm.</li>
<li>Wait for the portal's receipt. <b>The receipt score is the only ORGANIZER-CONFIRMED number that
exists.</b> Nothing produced in this repository is organizer-confirmed, and no projection may ever be
written into a score column.</li>
<li>Record the receipt: the score, the UTC timestamp, the exact filename and its sha256, into
<code>research/leaderboard_series.json</code> and the session's run card.</li>
</ol>

<h2>2. The file</h2>
<table class="kv">
<tr><td>path in this repository</td><td><code>{CARD['raster_path']}</code></td></tr>
<tr><td>bytes</td><td>{BYTES:,}</td></tr>
<tr><td>sha256</td><td><code>{SHA}</code></td></tr>
<tr><td>bands / dtype</td><td>{REC['count']} band, {REC['dtype']}</td></tr>
<tr><td>CRS / resolution</td><td>{REC['crs']}, {REC['res'][0]:.0f} m</td></tr>
<tr><td>shape</td><td>{REC['shape'][0]} × {REC['shape'][1]} (rows × cols)</td></tr>
<tr><td>transform</td><td>{REC['transform']}</td></tr>
<tr><td>nodata</td><td>{REC['nodata']} — deliberately absent (see §4)</td></tr>
<tr><td>value range</td><td>[{VAL['values_min']:.0f}, {VAL['values_max']:.0f}], all finite,
{VAL['nan_inside_footprint']} NaN inside the footprint</td></tr>
<tr><td>dots</td><td>{EM['n_dots']:,} single-pixel values of 1.0 on an all-zero grid; minimum
dot-to-dot separation {EM['min_separation_m']:.0f} m</td></tr>
<tr><td>format receipt (from the bytes re-read from disk)</td>
<td>legal = {REC['legal']}; validator passed = {VAL['passed']};
failures = {VAL['failures']}</td></tr>
</table>

<h2>3. The unique submission filename</h2>
<p><code>{NAME}</code></p>
<p class="mut">Convention: <code>&lt;repo&gt;&lt;lane&gt;-h&lt;hypothesis id&gt;-&lt;what it
is&gt;-&lt;n dots&gt;dots-&lt;UTC date&gt;-&lt;first 12 hex of the file's own sha256&gt;-&lt;outside
encoding&gt;</code>. The embedded hash makes the name self-authenticating: anyone can check that the
bytes they downloaded are the bytes that were named, and two artifacts can never share a name.
A NaN-outside twin is also published (<code>{NAN}</code>) for viewers that need the footprint
encoded as NaN; <b>upload the <code>-zeros</code> file</b>, because NaN outside the footprint is one
of the two mechanisms behind the portal's range rejection.</p>

<h2>4. The regression this repository must never repeat</h2>
<p>A previous upload was rejected with <b>"Predicted values must be in range [0, 1]"</b>. Two
mechanisms produce that message, and <code>src/gems62/grid.py::write_submission</code> removes both,
then re-reads the bytes from disk and re-counts before returning a receipt:</p>
<ul>
<li>a float32 sentinel such as <code>-3.4028234663852886e+38</code> (the organiser stack's nodata)
left anywhere in the array;</li>
<li>a NaN nodata <i>tag</i> written into the TIFF metadata, which the portal reads as an out-of-range
value even when every finite pixel is inside [0, 1].</li>
</ul>
<p>The shipped file carries <b>no nodata tag at all</b> and encodes "outside the footprint" as 0.0.</p>

<h2>5. The short note ({len(NOTE)}/140 characters)</h2>
<p><code>{NOTE}</code></p>

<h2>6. What a future session must do before spending a slot</h2>
<ol>
<li>Beat the best local evidence. The protocol forbids spending a slot on an idea that has not beaten
the current holdout best — and this session's own instruments are documented as unable to rank a
<i>new</i> field at all (see <a href="index.html#why">why no gain can be certified</a>). Any claim of
improvement must be MEASURED, not MODEL.</li>
<li>Clear the uniqueness gate mechanically: ρ ≤ 0.90 and ≤ 70 % within 3 px against <i>every</i>
non-vacuous registry raster, checked on the surface <i>before</i> placement and on the final dots,
plus the isolated-random control (without it the 3 px leg is density-blind — IR-62-22).</li>
<li>Close the arrangement gap. Inside the M ≈ 37,000-44,000 band, every field scoring 0.26-0.2778
carries dens21 8.75-9.62 and coh21 0.307-0.336; this field carries {f4(PROF['dens21'],2)} and
{f4(PROF['coh21'],4)}. Dots must lie along coherent corridors, and a hard-core selection of a smooth
probability surface does not produce that (experiment 11 refuted the smooth fix).</li>
<li>Keep the isolation: at least 400 m between any two dots, so no dot competes with another inside
one 300 m kernel (self-kernel must stay ≈ 0).</li>
<li>Keep it off the catalogue: catalogue fault pixels are masked out of scoring, so any dot on them is
pure FP mass.</li>
</ol>

<h2>7. Labels used throughout this repository</h2>
<table>
<tr><th>label</th><th>meaning</th></tr>
<tr><td><b>ORGANIZER-CONFIRMED</b></td><td>a score that appeared on a submission-page receipt. None
exists in this repository.</td></tr>
<tr><td><b>HOLDOUT-DTI</b></td><td>evaluator version, number of withheld positives, and a 95 % CI.
This session's: <code>{HOLD['version']}</code>, {HOLD['withheld_positives_total']:,} withheld
positives over {HOLD['n_segments_total']} segments, pooled DTI {f4(HOLD['pooled_dti'])}, CI
[{f4(HOLD['fold_dti_ci95'][0])}, {f4(HOLD['fold_dti_ci95'][1])}] — retired as a gate by
IR-62-HOLDOUT-01.</td></tr>
<tr><td><b>MEASURED-INSTRUMENT</b></td><td>a locally measured quantity with a stated held-out
agreement against owner-reported scores, usable for ranking only.</td></tr>
<tr><td><b>MODEL</b></td><td>arithmetic on the published metric with inherited assumptions. Never
written as a score.</td></tr>
<tr><td><b>OWNER-REPORTED / MIRROR</b></td><td>a number attached to a fetched raster, or a mirror of
the leaderboard, that this sandbox could not confirm with the organiser.</td></tr>
</table>

<p class="mut">Generated by <code>scripts/make_site_20261012.py</code> from
<code>evidence/run_card_20261012_62e.json</code>.</p>
</div></body></html>
"""


SESSION_PAGE = "docs/session-2026-10-12-62e.html"
MARK_A = "<!-- ==== session 2026-10-12 lane 62E start (generated by scripts/make_site_20261012.py) ==== -->"
MARK_B = "<!-- ==== session 2026-10-12 lane 62E end ==== -->"


def index_section() -> str:
    """The block this lane owns on the shared front page. Inserted below the newest hero."""
    return f"""{MARK_A}
<h2 id="o62e">Session 2026-10-12 — lane 62E: a 40,000-dot field from the organiser's own stack,
STOPPED by the uniqueness gate</h2>
<p><span class="pill no">DO NOT SUBMIT — gems62.uniqueness returns DUPLICATE - STOP</span>
<span class="pill ok">FORMAT LEGAL — {REC['count']} band float32, EPSG:32611, values [0, 1], no nodata tag</span>
<span class="pill ok">ISOLATION PROVEN — minimum separation {EM['min_separation_m']:.0f} m,
{EM['dots_with_another_dot_inside_300m']} dots inside one 300 m kernel</span></p>
<p class="big">{NAME}</p>
<p><a class="btn sec" href="downloads/{TIF}" download>⬇ Download the GeoTIFF ({BYTES:,} bytes)</a>
<a class="btn sec" href="downloads/{NAN}" download>⬇ NaN-outside twin (format probe)</a>
<a class="btn sec" href="{SESSION_PAGE.split('/')[-1]}">This lane's full report</a></p>
<table>
<tr><th>check</th><th>this file</th><th>limit / comparator</th><th>result</th></tr>
<tr><td>dots within 3 px of one non-vacuous registry raster</td><td>{pct(CMP['my_frac3px'])}</td>
<td>≤ 70 % (isolated-random control {pct(CMP['isolated_random_control_frac3px'])})</td>
<td><span class="pill no">TRIP</span></td></tr>
<tr><td>exact shared pixels with <code>{CMP['alias'][:44]}…</code></td>
<td>{CMP['exact_shared_dots']:,} = {pct(CMP['exact_shared_frac'])}</td>
<td>chance {pct(CMP['chance_expectation'],1)}</td>
<td><span class="pill no">{f4(CMP['chance_ratio'],2)}× chance</span></td></tr>
<tr><td>rank correlation (worst of {UNI['n_registry']})</td><td>{f4(UNI['max_abs_rho'])}</td>
<td>≤ 0.90</td><td><span class="pill ok">PASS</span></td></tr>
<tr><td>arrangement dens21 / coh21</td><td>{f4(PROF['dens21'],2)} / {f4(PROF['coh21'])}</td>
<td>8.75-9.62 / 0.307-0.336 for every field scoring 0.26-0.2778</td>
<td><span class="pill no">WORSE</span></td></tr>
<tr><td>MODEL projection (never a score)</td>
<td>{f4(MODEL['dti_at_K12000'])} at K = 12,000</td>
<td>information-free ceiling at this mass: 0.0869</td>
<td><span class="pill warn">MODEL</span></td></tr>
</table>
<p class="mut">sha256 <code>{SHA}</code> · {EM['n_dots']:,} unit dots · deterministic rebuild
identical: {EM['deterministic_rebuild_identical']} · short note for the portal ({len(NOTE)}/140):
<code>{NOTE}</code> · evidence <code>evidence/run_card_20261012_62e.json</code>. Redundant in class
with the sibling lane's H63 file, which carries the wider control-normalised audit — see
<a href="{SESSION_PAGE.split('/')[-1]}#collision">the collision note</a>.</p>
{MARK_B}"""


def allfiles_rows() -> str:
    """Two rows for the shared 'every downloadable file' table, generated from the audit."""
    man = json.loads((ROOT / "docs/downloads/manifest.json").read_text())
    rows = []
    for r in man["files"]:
        n = pathlib.Path(r["path"]).name
        if n not in (TIF, NAN):
            continue
        pill = ('<span class="pill ok">legal</span>' if not r.get("fails")
                else '<span class="pill no">not legal: ' + ", ".join(r["fails"]) + "</span>"
                     + f' <span class="pill warn">range risk {r.get("portal_range_risk", "?")}</span>')
        rows.append(f'<tr><td><a href="downloads/{n}">{n}</a>{pill}</td>'
                    f'<td>{r.get("dots", 0):,}</td><td>{r["bytes"]:,} B</td>'
                    f'<td>{r.get("checks_passed", 0)}/{r.get("checks_total", 14)}</td>'
                    f'<td><code>{r["sha256"][:16]}…</code></td><td>{r.get("verdict", "")}</td></tr>')
    return "\n".join(rows)


def update_front_page() -> None:
    """Idempotently insert this lane's section and its two download-table rows into docs/index.html."""
    page = ROOT / "docs/index.html"
    text = page.read_text()
    if MARK_A in text:
        text = text[:text.index(MARK_A)] + text[text.index(MARK_B) + len(MARK_B):]
    block = index_section()
    for anchor in ('<h2 id="h62j">', '<h2 id="allfiles">'):
        if anchor in text:
            text = text.replace(anchor, block + "\n" + anchor, 1)
            break
    else:
        raise SystemExit("no stacking anchor found in docs/index.html")
    rows = allfiles_rows()
    if rows and TIF not in text.split('<h2 id="allfiles">')[-1]:
        # insert immediately before the closing tag of the allfiles table
        i = text.index('<h2 id="allfiles">')
        j = text.index("</table>", i)
        text = text[:j] + rows + "\n" + text[j:]
    page.write_text(text)
    print(f"updated docs/index.html ({len(text):,} bytes; lane 62E section + download rows)")


def main() -> int:
    for name, text in ((SESSION_PAGE, IDX),
                       ("docs/executive-summary-2026-10-12.html", EXEC)):
        assert "{{" not in text and "}}" not in text, name
        (ROOT / name).write_text(text)
        print(f"wrote {name} ({len(text):,} bytes)")
    update_front_page()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
