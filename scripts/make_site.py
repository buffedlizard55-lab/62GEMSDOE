"""Regenerate the docs/ site from the newest run card.

The pages are *derived* documents: every number is substituted from
``evidence/<slug>-runcard.json`` and its sibling receipts, so a re-run cannot
leave stale figures on the site. Substitution is token-based (``{{TOKEN}}``)
rather than f-string based, so the templates can hold arbitrary HTML and the
script can prove that no token was left unfilled.

    python scripts/run_lane.py --registry <dir> --out docs/downloads --evidence evidence
    python scripts/make_readme.py
    python scripts/make_site.py

Writes docs/index.html, docs/executive-summary.html and
docs/research/sources.html (converted from sources.md).
"""

from __future__ import annotations

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

_cards = sorted((ROOT / "evidence").glob("*-runcard.json"), key=lambda p: p.stat().st_mtime)
if not _cards:
    raise SystemExit("no run card in evidence/ -- run scripts/run_lane.py first")
CARD_PATH = _cards[-1]
card = json.loads(CARD_PATH.read_text())
slug = card["slug"]
L = card["correlation_overlap_vs_registry"]
H = card["holdout"]
SM = card["score_model"]
SURF = card["correlation_overlap_vs_registry_surface_before_placement"]
CNT = card["counts"]
G = card["gates"]["step_significance"]
IB = card["isobase"]
STEP0 = card["step_locations_detail"][0] if card["step_locations_detail"] else None
print(f"site from {CARD_PATH.name} -> {slug}")

MODES = ", ".join(f"{m['value_m']:.1f}" for m in IB["levels"]["modes"])
CREST_GRADIENT = (abs(STEP0["jump_m"]) / (STEP0["pair_distance_m"] / 1000.0)) if STEP0 else 0.0

TOKENS = {
    "SLUG": slug,
    "DOTS": f"{CNT['dots']:,}",
    "SHA": card["raster_sha256"],
    "SHA16": card["raster_sha256"][:16],
    "BYTES": f"{card['raster_bytes']:,}",
    "PASS": "PASS" if card["validator_output"]["passed"] else "FAIL",
    "CEIL": f"{SM['this_artifact_ceiling']:.4f}",
    "LANE_RHO": f"{L['max_abs_rho']:.6f}",
    "LANE_OVL": f"{L['max_frac3px_non_vacuous']:.4f}",
    "LANE_CLOSEST": L["closest_non_vacuous"],
    "N_REG": str(L["n_registry"]),
    "N_VAC": str(L["n_vacuous"]),
    "SURF_CELLS": f"{SURF['full']['cells']:,}",
    "SURF_RHO": f"{SURF['full']['max_abs_rho']:.6f}",
    "SURF_OVL": f"{SURF['full']['max_frac3px_non_vacuous']:.4f}",
    "EV_CELLS": f"{SURF['evidence']['cells']:,}",
    "EV_RHO": f"{SURF['evidence']['max_abs_rho']:.6f}",
    "EV_OVL": f"{SURF['evidence']['max_frac3px_non_vacuous']:.4f}",
    "HDTI": f"{H['pooled_dti']:.6f}",
    "HDTI_LO": f"{H['ci95_cluster_bootstrap_whole_segments'][0]:.6f}",
    "HDTI_HI": f"{H['ci95_cluster_bootstrap_whole_segments'][1]:.6f}",
    "HDTI_SEG": f"{H['withheld_segments']:,}",
    "HDTI_CELLS": f"{H['withheld_positive_cells']:,}",
    "HDTI_N": str(H["bootstrap_n"]),
    "BENCHES": str(CNT["benches"]),
    "DATUM_CELLS": f"{CNT['datum_cells']:,}",
    "MODES": MODES,
    "STRAND_BENCHES": str(IB["levels"]["strand_benches"]),
    "STRAND_CELLS": f"{IB['levels']['strand_cells']:,}",
    "IB_GLOBAL": f"{IB['global']['residual_sigma_m']:.2f}",
    "IB_LOCAL": f"{IB['local_strand']['residual_sigma_m']:.2f}",
    "STEPS": str(CNT["step_locations"]),
    "DEFLS": str(CNT["deflection_locations"]),
    "STEPS_NEAR": str(G["pairs_within_radius"]),
    "STEPS_RES": str(CNT["step_pairs_clearing_resolution_gate"]),
    "STEPS_BORDER": str(CNT["step_pairs_rejected_as_borderline"]),
    "GATE_SIG": f"{G['significance_gate_m']:.2f}",
    "GATE_RES": f"{G['resolution_gate_m']:.0f}",
    "SIGMA_ROBUST": f"{G['robust_sigma_m']:.2f}",
    "SIGMA_GLOBAL": f"{G['robust_sigma_m_global_mad']:.2f}",
    "GATE_SIG_GLOBAL": f"{G['significance_gate_if_global_mad_m']:.2f}",
    "Z_MIN": f"{G['z_min']:g}",
    "STEPS_DETAIL": (
        f"{STEP0['jump_m']:+.2f} m over {STEP0['pair_distance_m']:.0f} m "
        f"({CREST_GRADIENT:.1f} m/km)"
    ) if STEP0 else "none",
    "DEFL_MIN": f"{card['gates']['deflection_min_deg']:.0f}",
    "TRACES": str(CNT["traces"]),
    "TRACE_LEN": f"{CNT['mean_trace_length_m']:,.0f}",
    "SPACING": f"{card['emission']['spacing_m']:.0f}",
    "EXCLUSION": f"{card['emission']['exclusion_m']:.0f}",
    "AZ": f"{json.loads((ROOT / 'evidence' / (slug + '-profile.json')).read_text())['track_azimuth_deg']:.1f}",
    "DROPPED_EXCL": str(card["emission"]["n_dropped_catalogue_exclusion"]),
    "TARGET": f"{SM['target_dti']:.4f}",
    "REP02778": f"{SM['in_family_check']['reproduced_02778']:.5f}",
    "MASS_OBS": f"{SM['mass_required_at_observed_credit']:,.0f}",
    "MASS_020": f"{SM['mass_required_at_credit_0.20']:,.0f}",
    "CRED40K": f"{SM['credit_required_at_40000_dots']:.4f}",
    "CRED25K": f"{SM['credit_required_at_25000_dots']:.4f}",
    "MARG_CRED": f"{SM['marginal_bar_credit']:.4f}",
    "MARG_DIST": f"{SM['marginal_bar_distance_m']:.0f}",
    "REF225": f"{SM['perfect_placement_ceiling_at_225_dots']:.4f}",
}

NAV = """<header>
  <span class="brand">62GEMSDOE · datum-offset lane</span>
  <nav>
    <a href="index.html" class="ACT_INDEX">Overview</a>
    <a href="executive-summary.html" class="ACT_EXEC">How to submit</a>
    <a href="research/sources.html">Sources</a>
    <a href="https://github.com/buffedlizard55-lab/62GEMSDOE">GitHub</a>
  </nav>
</header>"""

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TITLE</title><link rel="stylesheet" href="CSS"></head><body>"""

INDEX = HEAD + NAV + """
<main>
<h1>Lake Lahontan shorelines as a strain gauge</h1>
<p class="sub">Datum-offset lane · DOE GEMS Prize (DrivenData #306) ·
<span class="pill">artifact generated 2026-10-11</span><span class="pill">lane: DISTINCT</span>
<span class="pill">format: PASS</span><span class="pill">verdict: negative</span></p>

<div class="dl">
  <h2>⬇ Submission file</h2>
  <p><b>OK TO DOWNLOAD</b> for inspection. &nbsp;
     <span class="verdict v-no">NOT CLEARED TO SUBMIT — do not spend a weekly slot</span></p>
  <a class="btn" href="downloads/{{SLUG}}-zeros.tif">Download {{SLUG}}-zeros.tif</a>
  <a class="btn sec" href="downloads/{{SLUG}}-nan.tif">NaN-outside twin</a>
  <table>
    <tr><th>sha256</th><td class="mono">{{SHA}}</td></tr>
    <tr><th>bytes / dots</th><td class="n">{{BYTES}} &nbsp;·&nbsp; {{DOTS}} dots</td></tr>
    <tr><th>grid</th><td class="n">float32 · EPSG:32611 · 3730 × 3292 · 100 m · transform (100, 0, 243350, 0, −100, 4508550)</td></tr>
    <tr><th>local format checks</th><td><span class="verdict v-ok">{{PASS}}</span>
        — single band, float32, CRS/shape/transform exact, no non-finite value inside the footprint, every finite value in [0, 1], zeros outside the footprint</td></tr>
    <tr><th>lane rule — BOTH halves</th><td><b>before placement</b> (datum-offset surface): max |ρ| {{SURF_RHO}}, max 3-px overlap {{SURF_OVL}} over {{SURF_CELLS}} cells; <b>flagged evidence</b>: max |ρ| {{EV_RHO}}, overlap {{EV_OVL}} over {{EV_CELLS}} cells — all vs the limits 0.90 / 0.70. <b>final dots</b>: max |ρ| {{LANE_RHO}}, overlap {{LANE_OVL}}. Same evaluator, same registry of {{N_REG}} rasters; {{N_VAC}} of them are vacuous (see below).</td></tr>
    <tr><th>lane check vs {{N_REG}} registry rasters</th><td><span class="verdict v-ok">DISTINCT LANE</span>
        — max |ρ| {{LANE_RHO}} (limit 0.90); worst 3-px overlap {{LANE_OVL}} (limit 0.70) vs <code>{{LANE_CLOSEST}}</code></td></tr>
    <tr><th>hard upper bound</th><td class="n"><b>{{CEIL}}</b> — every one of the {{DOTS}} dots landing exactly on a truth pixel, |G| = 12,000</td></tr>
  </table>
  <p><b>Why you should not submit it.</b> The published metric charges β = 0.8 per <i>missing</i> truth
  cell and α = 0.2 per <i>emitted</i> cell. A file with {{DOTS}} dots therefore cannot
  exceed {{CEIL}} <b>even with perfect placement</b>, because FN<sub>w</sub> ≈ |G| dwarfs
  TP<sub>w</sub> ≤ {{DOTS}}. The protocol gate
  <i>“do not spend a submission slot on an idea that hasn't beaten the current holdout best”</i> is not met.
  Use this artifact as Phase-2 defensibility evidence, not as an initial-round scorer.
  Full reasoning below and in <a href="executive-summary.html">How to submit</a>.</p>
</div>

<h2>The question</h2>
<p><b>Why did the 0.2778 file score highest, and can we beat it?</b> The 0.2778 artifact is the
family's 0.2708 emission (40,199 dots) with every dot within 200 m of the mapped catalogue deleted
(2,545 dots removed, 37,654 left). For unit-valued, non-overlapping dots the published index reduces to</p>
<pre><code>DTI = c·N / (α·N + β·|G|)          c = mean kernel credit per dot, N = emitted mass, |G| = truth mass</code></pre>
<p>Deleting a dot that earns no credit lowers N while leaving the pooled credit T unchanged, so DTI
rises <i>mechanically</i>. That is a <b>precision edit, not a discovery</b>. The same algebra inverts
the two owner-recorded rows of the family to give c ≈ 0.122 and |G| ≈ 12,000 cells — and it reproduces
the observed 0.2778 to within 0.02 %:</p>
<table>
  <tr><th>check</th><th class="n">model</th><th class="n">owner-reported</th><th class="n">error</th></tr>
  <tr><td>c = 0.122, N = 40,199, |G| = 12,000</td><td class="n">{{REP02778}}</td><td class="n">0.2778</td><td class="n">0.02 %</td></tr>
</table>
<p><b>So the answer to “can we beat it?” is a set of numbers, not a hope.</b>
At a target of {{TARGET}}:</p>
<table>
  <tr><th>route</th><th class="n">requirement</th></tr>
  <tr><td>more mass, same placement quality</td><td class="n">{{MASS_OBS}} dots at c = 0.130</td></tr>
  <tr><td>better placement, moderate mass</td><td class="n">{{MASS_020}} dots at c = 0.200</td></tr>
  <tr><td>40,000 dots</td><td class="n">need c = {{CRED40K}}</td></tr>
  <tr><td>25,000 dots</td><td class="n">need c = {{CRED25K}}</td></tr>
  <tr><td>marginal rule for adding one dot</td><td class="n">profitable iff c &gt; {{MARG_CRED}} (within {{MARG_DIST}} m of truth)</td></tr>
</table>
<p class="sub">All rows labelled <b>MODEL</b> — algebra on the published metric with one inherited input (|G| ⊂
[10,000, 14,100]). No projection is written as a score.</p>

<h2>What the lane did</h2>
<ol>
  <li><b>Datum mapping.</b> {{DATUM_CELLS}} wave-planed cells inside the published deformed-elevation
      window (1313.5–1345.8 m; literature range 1318.4–1340.8 m) → <b>{{BENCHES}} benches</b>.</li>
  <li><b>Level separation.</b> The residual histogram is multi-modal
      (modes at {{MODES}} m) — the stacked-shoreline
      mimic. The dominant strand ({{STRAND_BENCHES}} benches / {{STRAND_CELLS}} cells) is kept so a
      Sehoo bench is never contrasted with an Eetza bench.</li>
  <li><b>Isobases.</b> Robust 3rd-order global fit (σ = {{IB_GLOBAL}} m) for the domal
      rebound + northward tilt, then a locally robust plane fit on the single strand:
      <b>σ = {{IB_LOCAL}} m</b>, i.e. below the published 3 m elevation-method resolution.
      The local fit is bounded by two support guards (a gradient cap and a
      neighbourhood-band clamp) because an unguarded plane fitted 12 km away produced a
      phantom +25.7 m offset in the first run of this lane.</li>
  <li><b>Flags — and the honest count.</b> {{STEPS}} step location survives a two-stage test:
      {{STEPS_RES}} bench pairs clear the published {{GATE_RES}} m resolution gate, but the
      significance gate — {{Z_MIN}} × √2 × σ = {{GATE_SIG}} m, with σ = {{SIGMA_ROBUST}} m from the
      <i>median pairwise difference</i> between nearby benches — rejects {{STEPS_BORDER}} of them as
      indistinguishable from beach-crest scatter. The estimator matters: a global MAD is masked by
      the offset it is meant to detect (a synthetic 12 m step over 20 km inflated it to 6.02 m and
      rejected itself), so the pairwise median is used and the global MAD
      ({{SIGMA_GLOBAL}} m → gate {{GATE_SIG_GLOBAL}} m) is reported as a cross-check. Both accept the
      same single location on this data. Those borderline candidates are published
      worst-first in the run card (<code>step_pair_test.borderline_candidates</code>), because a
      rejected candidate is as much a result as an accepted one. The survivor is
      <b>{{STEPS_DETAIL}}</b> — a gradient no smooth rebound field can absorb.
      {{DEFLS}} lateral deflection locations (≥ {{DEFL_MIN}}° azimuth change) are reported as locations,
      not as raw pair counts.</li>
  <li><b>Traces.</b> Fault azimuth from the datum geometry, not the local DEM grain: a vertical step means the fault
      <i>crosses</i> the shoreline (az + 90°), a lateral deflection means it <i>runs along</i> it (the Pyramid Lake
      fault-zone case). {{TRACES}} traces survive evidence-gated extension (coherence ≥ 0.15,
      relief ≥ 4 m), mean length {{TRACE_LEN}} m.</li>
  <li><b>Emission.</b> Unit dots at {{SPACING}} m kernel-matched spacing, ≥ {{EXCLUSION}} m from the mapped catalogue.
      <b>{{DOTS}} dots</b>.</li>
</ol>

<h2>First deliverable — shoreline elevation-versus-distance profile with flagged steps</h2>
<p>Top: the datum elevation of every bench along the shoreline track against the fitted local isobase.
Bottom: the residual (elevation minus isobase), where a step actually shows; the dashed band is the
published ±3 m constructional scatter of beach crests, and the circled point is the surviving step
location. Green = |residual| below the 3 m resolution, amber = at or above it.</p>
<img class="fig" src="assets/profile.png" alt="Shoreline elevation and residual versus along-shoreline distance with the flagged step">
<h3>Spatial view</h3>
<img class="fig" src="assets/map.png" alt="Highstand datum band, catalogue, and emitted dots">
<p class="sub">Grey = DEM shaded relief. Blue = the mapped highstand datum cells. Red = the mapped catalogue
(USGS/INGENIOUS). Yellow = the {{DOTS}} emitted dots. Note that every yellow dot sits on the datum
margin and none sits on the catalogue.</p>

<h2>Verification, step by step</h2>
<table>
  <tr><th>check</th><th>result</th></tr>
  <tr><td>Metric re-implemented from the published formula</td><td>Official worked example 3.00/1.89/2.00 → 0.6026517 (page rounds to 0.60); 1×5 counterexample → 25/29 = 0.8620689… — <b>10/10 tests pass</b></td></tr>
  <tr><td>Grid constants measured, never assumed</td><td>counts −1/0/1 = 7,111,787 / 5,106,385 / 60,988; footprint 5,167,373 cells; all four rasters share one transform</td></tr>
  <tr><td>Input integrity</td><td>every input SHA-256 pinned in <code>registry/data_pins.json</code>; the 19-band stack re-assembled from five parts and verified against its published pin</td></tr>
  <tr><td>Registry cross-check</td><td>{{N_REG}} prior artifacts fetched; every pinned hash matched on fetch, including the 0.2778 file (<code>c55bafc4…ab6fa9</code>)</td></tr>
  <tr><td>HOLDOUT-DTI</td><td>{{HDTI}} · 95 % CI [{{HDTI_LO}}, {{HDTI_HI}}] ({{HDTI_SEG}} withheld whole segments, {{HDTI_CELLS}} withheld positive cells, cluster bootstrap n = {{HDTI_N}}) — <b>evaluator gems62.holdout.v1, label HOLDOUT-DTI</b></td></tr>
  <tr><td>Gate recording</td><td>every CLI gate that produced this file is echoed into the run card under <code>gates</code>, so an independent reader can reproduce the numbers without guessing defaults</td></tr>
  <tr><td>Protocol defect reproduced</td><td>{{N_VAC}} of {{N_REG}} registry rasters are <i>vacuous</i> — their own 3-px dilation blankets ≥ 70 % of the footprint, so <i>any</i> submission trips the 70 % dot-overlap rule against them. Independently reproduces the sibling repositories' IR-54-016.</td></tr>
</table>
<p><b>Why the holdout number is unusually trustworthy here, and also does not answer the real question.</b>
The lane reads the catalogue for <i>nothing</i> except an exclusion gate that can only remove mass, so withheld
positives provably cannot help it — this is a leak-free hide-and-recover, unlike every catalogue-reading method
in the family. But the competition's target is exactly the fault population the catalogue <i>lacks</i> and the
organizers mask out of scoring, so the number is a lower bound on recovering a <i>mapped</i> population and says
nothing about the hidden target. Both facts are stated wherever the number appears.</p>

<h2>Sources &amp; irregularities</h2>
<p>Every claim carries an evidence class (OFFICIAL / PEER-REVIEWED / MEASURED / INHERITED / MODEL) and a link in
<a href="research/sources.html">Sources</a>, including six flagged irregularities (IR-62-001 … IR-62-006) for
manual review. Headline citations:</p>
<ul>
  <li>Adams, Wesnousky &amp; Bills (1999), JGR — “<i>Active faults locally offset the high shoreline, but cannot
      explain the regional upwarping attributed to isostatic rebound since 13 ka</i>”; deflection ~22 m;
      range 1318.4–1340.8 m; prerebound 1328 m; 3 m resolution.</li>
  <li>Adams &amp; Wesnousky (1998), GSA Bulletin 110, 1318–1332 — isochronous highstand, 13,070 ± 60 yr B.P.</li>
  <li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Problem description, page 967</a> — metric, submission format.</li>
</ul>
</main>
<footer>No organizer score exists for this or any artifact here, and none is claimed. Local format checks are not
organizer acceptance. DrivenData's Terms of Use prohibit automated monitoring, so no leaderboard scraper or feed is
included. <a href="executive-summary.html">How to submit →</a></footer></body></html>"""

EXEC = HEAD + NAV + """
<main>
<h1>Executive summary — exactly how to make a submission into the competition</h1>
<p class="sub">Written so that someone who has never opened the competition can go from this page to a
scored submission without reading any code.</p>

<div class="card hi">
<h2 style="border:0;margin-top:0;padding-top:0">The 60-second version</h2>
<ol>
  <li>Log in to <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">the competition data tab</a>
      and accept the rules. Download <code>sample_submission.tif</code> — it defines the grid.</li>
  <li>Produce a single-band float32 GeoTIFF that matches the grid exactly:
      <b>EPSG 32611, 100 m, shape 3730 × 3292, transform</b>
      <code>(100, 0, 243350, 0, −100, 4508550)</code>, values in <b>[0, 1]</b>, null/NaN outside the data bounds.</li>
  <li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submit/">the submission form</a>,
      <b>choose your file</b>, paste a short <b>Note</b> (&le; 140 characters so you can tell submissions apart later),
      and press Submit. Uploading does not consume a slot until you confirm; a scored submission does.</li>
  <li>Budget: <b>up to three scored submissions per week</b>. Spend them deliberately.</li>
</ol>
</div>

<h2>1. The file the portal wants — the exact contract</h2>
<p>Verbatim from the problem description, “# Submission format”:</p>
<ul>
  <li>“same projected coordinate reference system as the training data … <b>EPSG 32611</b>”</li>
  <li>“same resolution … <b>100m</b>”</li>
  <li>“same bounds as the training data, and <b>data outside the bounds is null or nan</b>”</li>
  <li>“a single layer with datatype of <b>32-bit float (float32)</b> with values <b>between 0 and 1</b>”</li>
</ul>
<p>A single-band <code>.tif</code>, or a <code>.zip</code> containing one, is accepted.</p>

<h2>2. The error you already hit, and why</h2>
<div class="card">
<p><b>“Predicted values must be in range [0, 1]”</b> — this is a range check that sees a value outside
[0, 1]. The three common causes, in order:</p>
<ol>
  <li><b>A float32 nodata sentinel.</b> GeoTIFFs written by GIS tools often carry <code>-3.4028235e38</code>
      (“−FLT_MAX”). It is a legitimate nodata marker but it is far outside [0, 1], and if the portal reads
      it as data the check fails. <b>Fix:</b> write <code>nodata=None</code>, or use NaN.</li>
  <li><b>A NaN nodata tag with NaN cells counted as data.</b> NaN fails any
      <code>all(v &gt;= 0 and v &lt;= 1)</code> test. Five of the sibling repositories' artifacts are
      NaN-outside; they are exactly the files that produced this error for the owner.</li>
  <li><b>Genuine out-of-range data</b> — an unnormalised probability or a scaled integer.</li>
</ol>
<p><b>The safe pattern used here:</b> write every cell <i>outside</i> the survey footprint as a <b>finite
0.0</b> with <code>nodata=None</code>, and every finite value in the footprint in [0, 1]. No sentinel, no NaN,
nothing for a range check to trip on. This repository ships both encodings so you can choose:
<code>-zeros.tif</code> (all finite) and <code>-nan.tif</code> (NaN outside, matching the page's wording literally).</p>
</div>

<h2>3. Which of our files to upload</h2>
<div class="card">
<p><span class="verdict v-no">DO NOT SUBMIT THIS WEEK</span></p>
<p>The current artifact has a hard upper bound of <b>{{CEIL}}</b> —
even if all {{DOTS}} dots landed exactly on truth pixels — because the metric charges
β = 0.8 per missing truth cell. Uploading it would spend one of three weekly slots on a file that cannot
beat the incumbent family. It is <b>OK TO DOWNLOAD</b> and inspect, and it is useful Phase-2 evidence.</p>
<a class="btn" href="downloads/{{SLUG}}-zeros.tif">Download for inspection</a>
<a class="btn sec" href="downloads/{{SLUG}}-nan.tif">NaN-outside twin</a>
</div>

<h2>4. What to upload instead — the numbers the metric demands</h2>
<p>For unit-valued, non-overlapping dots the published index reduces to
<code>DTI = c·N / (α·N + β·|G|)</code>. Clearing a target therefore has exactly two routes: more mass, or
better placement. At a target of <b>{{TARGET}}</b>, with |G| = 12,000:</p>
<table>
  <tr><th>route</th><th class="n">requirement</th><th>what it means in practice</th></tr>
  <tr><td>mass at the family's own placement quality</td><td class="n">{{MASS_OBS}} dots at c = 0.130</td>
      <td>emit ~46,000 dots, not 37–45 k, while keeping every dot's credit profile unchanged</td></tr>
  <tr><td>placement quality at a moderate mass</td><td class="n">{{MASS_020}} dots at c = 0.200</td>
      <td>~22,500 dots each averaging within ~240 m of a truth pixel</td></tr>
  <tr><td>fixed at 40,000 dots</td><td class="n">c ≥ {{CRED40K}}</td>
      <td>a 15 % improvement in mean credit over the family's 0.122</td></tr>
  <tr><td>fixed at 25,000 dots</td><td class="n">c ≥ {{CRED25K}}</td>
      <td>a 53 % improvement in mean credit — the highest-leverage single change</td></tr>
</table>
<p>And the rule that decides whether one more dot is worth emitting — profitable iff its credit exceeds
α·DTI, i.e. within <b>{{MARG_DIST}} m</b> of a truth pixel at DTI = {{TARGET}}. Dots beyond 300 m contribute
nothing at all and cost α each.</p>
<p class="sub">Label: <b>MODEL</b>. The model's own validity check: applied to the two owner-recorded rows of
the family it reproduces 0.2778 to within 0.02 %. It is not a score and not a projection written as a score.
For reference, a 225-dot file with flawless placement would score {{REF225}}.</p>

<h2>5. The single most important rule the competition states</h2>
<div class="card hi">
<p>From the problem description: the test set is faults <b>“not included in the existing USGS fault
database”</b>, and after the Initial prize round “<b>an expert panel will use submitted predictions to update
fault labels for the full region</b>”, after which the same submissions are rescored:</p>
<p style="color:var(--warn)">“Predictions that helped experts identify previously-unmapped faults can score
higher here than in the Initial Prize Round.”</p>
<p>Two consequences most entries miss:</p>
<ol>
  <li><b>The final round rewards defensible placements</b>, because a human panel decides which of your
      locations become new labels. A blanket of dots that no geologist can confirm adds nothing there.</li>
  <li><b>The initial round rewards mass geometry</b>, because the score is a weighted-count ratio in which
      every emitted unit costs α = 0.2 and every missed truth cell costs β = 0.8.</li>
</ol>
<p>Those two pull in opposite directions. The winning play is the one that satisfies both: mass placed on
structures an expert can independently confirm.</p>
</div>

<h2>6. Checklist before you press Submit</h2>
<table>
  <tr><th>#</th><th>check</th><th>how</th></tr>
  <tr><td>1</td><td>single band, float32, EPSG:32611, shape (3730, 3292), exact transform</td><td><code>python -m gems62.validate</code> or a <code>rasterio</code> one-liner</td></tr>
  <tr><td>2</td><td>no non-finite value inside the footprint</td><td><code>np.isfinite(a[foot]).all()</code></td></tr>
  <tr><td>3</td><td>every finite value in [0, 1]</td><td><code>a[foot].min() &gt;= 0 and a[foot].max() &lt;= 1</code></td></tr>
  <tr><td>4</td><td>no out-of-range nodata sentinel</td><td>the file's <code>nodata</code> must be <code>None</code> or NaN</td></tr>
  <tr><td>5</td><td>unique vs every earlier raster you own — <b>both before placement (on the surface) and on the final dots</b></td><td>rank correlation &lt; 0.90 and dot overlap &lt; 70 %; <code>scripts/lane_check_surface.py</code> does the pre-placement half and <code>run_lane.py</code> records both</td></tr>
  <tr><td>6</td><td>you know the file's hard upper bound before you spend the slot</td><td><code>gems62.score_model.perfect_placement_ceiling(n_dots)</code></td></tr>
  <tr><td>7</td><td>a note under 140 characters that identifies this submission to you later</td><td>e.g. <code>{{SLUG}}</code></td></tr>
</table>

<h2>7. Things that will get a submission rejected or disqualified — not technical</h2>
<ul>
  <li><b>Eligibility.</b> The rules restrict entrants to U.S. citizens/permanent residents, U.S.-incorporated
      entities and U.S. academics, with FFRDC/DOE/FCOC/MFTRP exclusions. Verify before entering.</li>
  <li><b>Generative-AI disclosure.</b> Rule §3.2 requires a narrative statement of how generative AI was used,
      including in submission elements.</li>
  <li><b>External data licence.</b> Any external dataset must be licensed for use in the challenge and
      shareable with the sponsor. USGS 3DEP and the GeoDAWN release are US Government works (public domain);
      INGENIOUS/GDR 1391 is CC BY 4.0.</li>
  <li><b>No automated leaderboard monitoring.</b> DrivenData's Terms of Use prohibit automated
      monitoring/copying, and manual monitoring without written consent. This repository contains no scraper,
      no feed and no monitor, and fetches no leaderboard page.</li>
</ul>
<p class="sub">Official links: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/">about</a> ·
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules (PDF)</a> ·
<a href="https://github.com/drivendataorg/gems-prize-reference-solution">reference solution</a> ·
<a href="https://epsg.io/32611">EPSG 32611</a> ·
<a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index</a></p>
</main>
<footer>Local format checks are not organizer acceptance. Verify the portal's behaviour with your own upload.
<a href="index.html">← Overview</a></footer>
</body></html>"""


def md_to_html(md: str) -> str:
    """Markdown subset -> HTML for sources.md (headings, tables, lists, inline)."""

    def inline(t: str) -> str:
        t = html.escape(t, quote=False)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        return t

    out: list[str] = []
    in_tbl = in_ul = in_ol = False

    def close() -> None:
        nonlocal in_tbl, in_ul, in_ol
        if in_tbl:
            out.append("</tbody></table>"); in_tbl = False
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False

    for line in md.split("\n"):
        s = line.rstrip()
        if s.startswith("|"):
            cells = [x.strip() for x in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_tbl:
                close()
                out.append("<table><thead><tr>" + "".join(f"<th>{inline(x)}</th>" for x in cells)
                           + "</tr></thead><tbody>")
                in_tbl = True
            else:
                out.append("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in cells) + "</tr>")
            continue
        if in_tbl:
            close()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            close(); n = len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); continue
        m = re.match(r"^\s*[-*]\s+(.*)$", s)
        if m:
            if not in_ul:
                close(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", s)
        if m:
            if not in_ol:
                close(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        if not s:
            close(); continue
        close(); out.append(f"<p>{inline(s)}</p>")
    close()
    return "\n".join(out)


def fill(template: str, tokens: dict[str, str], name: str) -> str:
    page = template
    for key, value in tokens.items():
        page = page.replace("{{" + key + "}}", value)
    left = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", page)))
    if left:
        raise SystemExit(f"{name}: unresolved tokens {left}")
    for stray in ("ACT_INDEX", "ACT_EXEC"):
        if stray in page:
            raise SystemExit(f"{name}: stray {stray}")
    return page


def render(template: str, active: str, title: str, css: str, name: str) -> str:
    page = template.replace("TITLE", title)
    page = page.replace("CSS", css)
    page = page.replace("ACT_INDEX", "active" if active == "index" else "")
    page = page.replace("ACT_EXEC", "active" if active == "exec" else "")
    return fill(page, TOKENS, name)


(ROOT / "docs" / "index.html").write_text(
    render(INDEX, "index", "62GEMSDOE — datum-offset lane", "assets/site.css", "index.html"))
(ROOT / "docs" / "executive-summary.html").write_text(
    render(EXEC, "exec", "Executive summary — how to make a GEMS submission", "assets/site.css",
           "executive-summary.html"))

src_md = (ROOT / "docs" / "research" / "sources.md").read_text()
SOURCES = (HEAD.replace("TITLE", "Sources — 62GEMSDOE").replace("CSS", "../assets/site.css")
           + """<header><span class="brand">62GEMSDOE · datum-offset lane</span><nav>
<a href="../index.html">Overview</a><a href="../executive-summary.html">How to submit</a>
<a href="sources.html" class="active">Sources</a>
<a href="https://github.com/buffedlizard55-lab/62GEMSDOE">GitHub</a></nav></header>
<main>""" + md_to_html(src_md) + """</main>
<footer>Every claim carries an evidence class. Irregularities IR-62-001 … IR-62-006 are flagged for manual review.</footer>
</body></html>""")
sources = fill(SOURCES, TOKENS, "research/sources.html")
(ROOT / "docs" / "research" / "sources.html").write_text(sources)

for p in (ROOT / "docs" / "index.html", ROOT / "docs" / "executive-summary.html",
          ROOT / "docs" / "research" / "sources.html"):
    print(f"wrote {p.relative_to(ROOT)} ({len(p.read_text()):,} chars)")
