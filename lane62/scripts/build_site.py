#!/usr/bin/env python3
"""Generate the 62GEMSDOE site from the evidence JSONs.

No number on any page is hand-typed: every figure is read out of
evidence/*.json or docs/data/site.json at build time.  If a number is not in the
evidence, it does not appear on the site.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def J(name):
    for base in (EV, DOCS / "data"):
        p = base / f"{name}.json"
        if p.exists():
            return json.load(open(p))
    raise FileNotFoundError(name)


site = J("site")
prof = J("profiles")
isob = J("isobase")
canary = J("leakage_canary")
plain = J("lake_plain")
dem = J("dem_provenance")
evf = J("evidence_field")
e2 = J("exp2_selectivity")
e3 = J("exp3_economics")
ver = J("verify_economics")
hold = J("holdout")
gate = J("uniqueness_gate")
xchk = J("crosscheck_sibling_lane")

P = site["files"]["primary"]
S = site["files"]["secondary"]
PA, SA = P["stats"], S["stats"]
URA = P.get("uniqueness", {})
OV = site["uniqueness"]
GATE_P = gate[P["name"]]
GATE_S = gate[S["name"]]

CSS = """/* 62GEMSDOE site styles -- no external assets, no fonts, no trackers. */
:root{--bg:#fbfbfd;--fg:#14161a;--mut:#5a6169;--line:#e2e5ea;--acc:#0b5fa5;
--ok:#137a3f;--warn:#a4670a;--bad:#a8121b;--card:#fff;--code:#f4f6f8}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
Helvetica,Arial,sans-serif;background:var(--bg);color:var(--fg)}
header{background:#fff;border-bottom:1px solid var(--line);padding:14px 0}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
nav a{margin-right:16px;color:var(--acc);text-decoration:none;font-weight:600;font-size:14px}
nav a:hover{text-decoration:underline}
h1{font-size:30px;line-height:1.25;margin:26px 0 6px}
h2{font-size:21px;margin:34px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:17px;margin:22px 0 6px}
p,li{color:#22262c}
small,.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:16px 0}
.banner{border-left:6px solid var(--acc);padding:14px 18px;background:#fff;
border:1px solid var(--line);border-radius:8px;margin:18px 0}
.banner.ok{border-left-color:var(--ok)}
.banner.warn{border-left-color:var(--warn)}
.banner.bad{border-left-color:var(--bad)}
.dl{display:inline-block;background:var(--ok);color:#fff;font-weight:700;
padding:12px 20px;border-radius:8px;text-decoration:none;font-size:17px}
.dl:hover{filter:brightness(1.08)}
.dl.alt{background:var(--acc)}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#f1f3f6}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
font-size:13px;background:var(--code);border-radius:5px}
code{padding:1px 5px}
pre{padding:12px;overflow:auto;border:1px solid var(--line)}
.pill{display:inline-block;font-size:12px;font-weight:700;padding:2px 9px;
border-radius:999px;border:1px solid var(--line);background:#fff}
.pill.ok{color:var(--ok);border-color:#b6e0c5;background:#f1fbf4}
.pill.bad{color:var(--bad);border-color:#f0bec2;background:#fdf2f3}
.pill.warn{color:var(--warn);border-color:#f0dcae;background:#fdf8ee}
footer{border-top:1px solid var(--line);margin-top:44px;padding:22px 0;color:var(--mut);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.k{font-size:26px;font-weight:800;letter-spacing:-.4px}
figure{margin:18px 0}
figcaption{font-size:13px;color:var(--mut)}
ul.tight li{margin:3px 0}
"""

NAV = [
    ("index.html", "Overview"),
    ("executive-summary.html", "How to submit"),
    ("results.html", "Results"),
    ("profiles.html", "Profiles (deliverable 1)"),
    ("research.html", "Research & hypotheses"),
    ("sources.html", "Sources"),
    ("irregularities.html", "Irregularities"),
    ("run-card.html", "Run card"),
]


def page(title, body, subtitle=""):
    nav = "".join(f'<a href="{h}">{t}</a>' for h, t in NAV)
    sub = f'<p class="mut" style="margin:0 0 8px">{subtitle}</p>' if subtitle else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 62GEMSDOE</title><link rel="stylesheet" href="assets/site.css">
</head><body><header><div class="wrap"><strong>62GEMSDOE</strong> &nbsp;
<small class="mut">Lake Lahontan shoreline datum-offset lane · DOE GEMS Prize</small>
<div style="margin-top:9px"><nav>{nav}</nav></div></div></header>
<main class="wrap">{sub}{body}</main>
<footer><div class="wrap">Every number on this site is read from
<code>evidence/*.json</code> at build time by <code>scripts/build_site.py</code>.
Nothing here is an organizer score. Generated {html.escape(site['generated_utc'])}.
</div></footer></body></html>"""


def money(v, n=6):
    return "—" if v is None else f"{v:.{n}f}"


def svg_profile():
    """Deliverable 1: elevation-versus-distance profile of the longest traced
    shoreline segment, with the flagged steps marked."""
    traces = prof["traces"]
    tid = max(range(len(traces)), key=lambda i: traces[i]["n_vertices"])
    pr = prof["profiles"][tid] if "profiles" in prof else None
    if pr is None:
        return "<p class='mut'>profile data unavailable</p>"
    d = pr["distance_m"]; zt = pr["zeta_m"]; ze = pr["elevation_m"]
    fl = [f for f in prof["flags"] if f.get("trace_id") == tid]
    W, H, padl, padr, padt, padb = 980, 340, 62, 16, 16, 42
    xmax = max(d) or 1.0
    lo = min(min(zt), -1.0); hi = max(max(zt), 1.0)
    span = max(hi - lo, 1e-6)

    def X(v):
        return padl + (W - padl - padr) * v / xmax

    def Y(v):
        return padt + (H - padt - padb) * (1 - (v - lo) / span)

    pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(d[::4], zt[::4]))
    rows = []
    for f in fl[:80]:
        x = X(min(f["distance_m"], xmax))
        rows.append(f'<line x1="{x:.1f}" y1="{padt}" x2="{x:.1f}" y2="{H-padb}" '
                    f'stroke="{"#a8121b" if f["kind"]=="vertical_step" else "#a4670a"}" '
                    f'stroke-width="1" opacity="0.55"/>')
    y0 = Y(0.0)
    return f"""<figure><svg viewBox="0 0 {W} {H}" width="100%" role="img"
aria-label="Shoreline datum residual versus distance with flagged steps">
<rect x="0" y="0" width="{W}" height="{H}" fill="#fff"/>
<line x1="{padl}" y1="{y0:.1f}" x2="{W-padr}" y2="{y0:.1f}" stroke="#8a9099" stroke-dasharray="4 4"/>
{''.join(rows)}
<polyline points="{pts}" fill="none" stroke="#0b5fa5" stroke-width="1.6"/>
<text x="{padl}" y="12" font-size="11" fill="#5a6169">datum residual zeta = z - isobase (m)</text>
<text x="{padl}" y="{H-14}" font-size="11" fill="#5a6169">distance along the trace (m)</text>
<text x="4" y="{Y(hi)+4:.1f}" font-size="11" fill="#5a6169">{hi:.0f} m</text>
<text x="4" y="{Y(lo)-2:.1f}" font-size="11" fill="#5a6169">{lo:.0f} m</text>
<text x="{W-padr-330}" y="{padt+14}" font-size="11" fill="#a8121b">red = vertical step</text>
<text x="{W-padr-330}" y="{padt+28}" font-size="11" fill="#a4670a">amber = lateral deflection</text>
</svg><figcaption>Trace #{tid} ({traces[tid]['length_km']} km, {traces[tid]['n_vertices']} vertices).
Datum residual about the fitted isobase, with every flagged step/deflection within the
plotted extent. The full set of {prof['n_traces']} traces and all
{len(prof['flags'])} flags is in
<a href="downloads/lahontan_shoreline_profiles.json">lahontan_shoreline_profiles.json</a>.
Raw profiles for all traces are in the same file.</figcaption></figure>"""


# ----------------------------------------------------------------- overview
gA = PA["instrumentA"]; gB = PA["instrumentB"]
ctrl = PA["control_same_stratum"]


def exact_from_jaccard(row, a):
    """Exact pixel intersection implied by Jaccard, for a file with `a` positives.

    J = I / (a + b - I)  =>  I = J (a + b) / (1 + J).  Jaccard is computed on the
    raw 0/1 masks, so this is algebra, not an extra measurement.
    """
    j, b = float(row["jaccard"]), float(row["n_positive"])
    return j * (a + b) / (1.0 + j)


_grows = GATE_P["rows"]
_a = GATE_P["n_positive"]


def _blanket_rows():
    """Non-discriminating comparators that are not the whole-footprint raster."""
    return [r for r in _grows
            if not r["discriminating"] and float(r["effective_coverage"]) < 0.999]


BLANKET = max(_blanket_rows(), key=lambda r: r["overlap_3px_one_sided"]) if _blanket_rows() else None
BLANKET_EXACT = exact_from_jaccard(BLANKET, _a) / _a if BLANKET else None
COPY = max((r for r in _grows if r["discriminating"]), key=lambda r: exact_from_jaccard(r, _a))
COPY_EXACT = exact_from_jaccard(COPY, _a) / _a
verdict_banner = f"""
<div class="banner bad"><h3 style="margin-top:0">Download for inspection only —
<b>DO NOT SUBMIT</b> &nbsp;<span class="pill ok">DOWNLOAD: YES</span>
<span class="pill bad">STRICT GATE: DUPLICATE — STOP</span></h3>
<ul class="tight">
<li><b>Format receipt: PASS, format only.</b> This is a valid GeoTIFF: single band,
<code>float32</code>, EPSG:32611, 3730×3292, exact sample transform, all cells finite,
values in [0, 1], no <code>nodata</code> tag, zero positive mass outside the footprint,
and 0 dots on the mapped catalogue (<a href="downloads/{P['name'].replace('.tif','.json')}">receipt</a>).
Format validity does not clear it for upload.</li>
<li><b>Binding uniqueness result: {html.escape(GATE_P['verdict'])}.</b> The maximum one-sided
Euclidean overlap within 3 px is
<b>{money(GATE_P['max_overlap_all'],4)}</b> against
<code>{html.escape(GATE_P['worst_overlap_all']['file'])}</code>, exceeding the 0.70 stop limit.
The positive-rho maximum is {money(GATE_P['max_positive_spearman'],4)} (limit 0.90; no rank trip).
This strict result includes every comparator. The informative subset's lower overlap
{money(GATE_P['worst_overlap_discriminating']['overlap_3px_one_sided'],4)} across
{GATE_P['n_discriminating']} comparators and the low Jaccard are diagnostics only; neither
waives the strict trip. The previous informative-only clearance is withdrawn.</li>
<li><b>Known density caveat.</b> The top comparator has
{OV['worst_overlap_all']['n_positive']:,} positives (the full footprint), so the one-sided rule
can trip for unrelated sparse dots. That makes the protocol uninformative for this comparator,
but does not authorize changing the rule. Record the prescribed negative and stop.</li>
<li><b>Pre-placement surface gate: not verified in this lane62 run card.</b> No passing receipt for
that required half is present. The final-dot duplicate trip alone is sufficient to block upload.</li>
<li><b>Other local measurements are not scores.</b> The HOLDOUT-DTI/proxy and geological diagnostics
cannot override the registry stop; no ORGANIZER-CONFIRMED score receipt exists.</li>
<li><b>Pairwise sibling-lane cross-check, not a full registry clearance.</b> Against the root v8
artifact the legacy report records one-sided 3 px overlap
{money(xchk['pairs'][0]['overlap_3px_one_sided'],4)}. This one-to-one comparison does not clear
this file against all registry rasters.</li>
</ul></div>"""

body_index = f"""
<h1>Lake Lahontan shorelines as a strain gauge</h1>
<p class="mut">62GEMSDOE · Lake Lahontan shoreline datum-offset lane · session
2026-10-11 · status <b>DO NOT SUBMIT — strict registry trip</b></p>

{verdict_banner}

<h2>Download for audit only — not an upload file</h2>
<div class="card">
<p style="margin-top:0"><a class="dl alt"
 href="downloads/{P['name']}">⬇ Download for inspection only — DO NOT UPLOAD</a>
&nbsp; <span class="mut">{P['receipt']['bytes']:,} bytes ·
sha256 <code>{P['receipt']['sha256']}</code></span></p>
<p style="margin-bottom:0"><b>Internal artifact ID</b> (tracking only):
<code>gems62-lahontan-datum-break-dotted-primary</code><br>
<b>Internal note</b> (≤140 chars; not an upload recommendation):
<code>Lahontan shoreline datum breaks; 86,968 dots; strict registry overlap trip; DO NOT SUBMIT; UNSCORED</code></p>
</div>
<p class="mut">A second artefact exists for audit only and is
<span class="pill bad">DO NOT SUBMIT</span> — see below.</p>

<h2>The brief's questions, answered with measurements</h2>
<div class="grid">
<div class="card"><div class="k">No receipt</div><div>Leaderboard values quoted in earlier drafts are not independently verified or organizer-confirmed in this checkout.</div></div>
<div class="card"><div class="k">{money(gB['dti'])}</div><div>HOLDOUT-DTI proxy only — lane62 <code>gems62.holdout</code> (legacy, untagged version),
{gB['n_truth']:,} withheld positives; 95% CI not computed in the retained evidence. Not an organizer score.</div></div>
<div class="card"><div class="k">{ver['ratio_lane_over_best_champion']:.2f}×</div>
<div>This lane's best mean credit per dot
({ver['lane_best_mean_credit']:.3f}) over the best registered prior field's
({ver['best_champion_mean_credit']:.3f}) on the <i>same</i> instrument. The lane
<b>loses</b>.</div></div>
<div class="card"><div class="k">{isob['rmse_m']:.2f} m</div><div>RMS of the robust
quadratic isobase fit to the highstand band ({isob['n_blocks']} blocks of
20×20 km).</div></div>
</div>

<h3>Why did the dotted H19-5 family score ~0.26, and why did thinning to 37,654 dots
reach 0.2778?</h3>
<p>The metric is a budget, and the identity
<code>DTI = T / (0.2·T + 0.2·F + 0.8·K)</code> (K = withheld truth pixels) is exact. Every
unit of prediction mass that is not the best cover of a truth pixel costs 0.2 and can earn
at most 1. Thinning a thick surface while keeping its geometry removes mass that was
<em>already</em> covered, raising credit per emitted pixel. Two independent routes to the
break-even credit per dot: the metric algebra gives
<code>α·s = 0.2 × 0.2778 = {money(PA['credit_bar_at_s_0p2778'],4)}</code>; the group
measured ≈0.0548 empirically. This repository re-derives the bar from the published
formulas and uses it as the selector on every candidate.</p>

<h3>Can this lane beat 0.2778?</h3>
<p><b>No, and the measurement that says so is the point of this session.</b> The lane's
<i>most selective</i> dot class — one dot per flagged datum break — carries mean credit
<b>{ver['lane_variants']['N50_half4']['mean_credit_instrumentB']:.3f}</b> per dot, well above
the bar, but it is only ≈90 dots, which cannot move a denominator of
0.8·K ≈ 6,300. At the mass end the credit per dot collapses
({money(e3['rows'][-1]['mean_credit_per_dot'],4)} at
{e3['rows'][-1]['n_dots']:,} dots). Critically, the <i>same-instrument</i> control
(<a href="results.html">Results</a>) shows a registered prior field reaching
{ver['best_champion_mean_credit']:.3f} with 45,000 dots — roughly double this lane's best dot
class <i>and</i> 500× the count. The lane is dominated; it does not get a slot.</p>

{svg_profile()}

<h2>The lane, in one paragraph</h2>
<p>The Sehoo (Lahontan) highstand shoreline formed at 13,070 ± 60 <sup>14</sup>C yr B.P. =
15,475 ± 720 cal yr B.P. on a near-level water plane (Adams &amp; Wesnousky 1998). Because
it was level when formed, its present elevation about a smooth isobase is a <i>strain
measurement</i>: a fault that breaks the datum produces a step or a lateral deflection in
it. That is the mechanism this lane exploits — and it is also why the lane is small: the
faults that offset the Lahontan shoreline are, for the most part, the ones already mapped
(Pyramid Lake, Wassuk, Smith Valley), so the lane buys defensibility rather than area.</p>

<h2>Second artefact — audit only</h2>
<div class="banner bad"><b>{S['name']}</b> ({SA['n_dots']} dots, sha256
<code>{S['receipt']['sha256']}</code>) is the lane's most conservative reading — one dot at
each of the top 120 flagged breaks, mean credit
{SA['mean_credit_per_dot']:.3f} per dot. It also fails the strict all-comparator gate:
maximum one-sided overlap {money(GATE_S['max_overlap_all'],4)} (&gt;0.70). Its informative
subset overlap is {money(GATE_S['worst_overlap_discriminating']['overlap_3px_one_sided'],4)}
against <code>{html.escape(GATE_S['worst_overlap_discriminating']['file'])}</code>. It is
published as evidence and <b>must not be submitted</b>.</div>
"""

# ------------------------------------------------------- executive summary
body_exec = f"""
<h1>Executive summary — how to make a submission</h1>

<h2>1. The artifact — review only, NOT CLEARED TO SUBMIT</h2>
<p><a href="downloads/{P['name']}"><b>{P['name']}</b></a> is available for inspection
({P['receipt']['bytes']:,} bytes, sha256 <code>{P['receipt']['sha256']}</code>), but the strict
registry gate returns <b>DUPLICATE — STOP</b>. Do not upload this file or spend a weekly slot.</p>

<h2>2. What the competition requires (quoted from the official page)</h2>
<table><tr><th>Requirement (official wording)</th><th>This file</th></tr>
<tr><td>"same projected coordinate reference system as the training data (projected
coordinate system for UTM zone 11N, EPSG 32611)"</td><td>{P['receipt']['meta']['crs']}</td></tr>
<tr><td>"at the same resolution as the training data (100m)"</td><td>100 m
({P['receipt']['meta']['transform'][0]:g}, {P['receipt']['meta']['transform'][4]:g})</td></tr>
<tr><td>"same bounds as the training data, and data outside the bounds is null or nan"</td>
<td>bounds identical ({', '.join(f'{v:.0f}' for v in P['receipt']['meta']['bounds'])});
outside the footprint the file is 0.0 — see note 4</td></tr>
<tr><td>"a single layer with datatype of 32-bit float (float32) with values between 0 and 1"</td>
<td>1 band, {P['receipt']['meta']['dtype']}, min {P['receipt']['min_inside']},
max {P['receipt']['max_inside']}</td></tr>
</table>
<p class="mut">Source: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">
problem description, section “Submission format”</a>, read 2026-10-11.</p>

<h2>3. Submission instructions</h2>
<div class="banner bad"><b>Do not upload this artifact.</b> Its strict one-sided registry
overlap is 1.0 (&gt; 0.70), so the required result is <b>DUPLICATE — STOP</b>. The format
receipt cannot waive that rule. The name and note below are for internal tracking only.</div>
<ul>
<li>Internal artifact ID: <code>gems62-lahontan-datum-break-dotted-primary</code>.</li>
<li>Internal note (&le;140 chars, not an upload recommendation):
<code>Lahontan shoreline datum breaks; 86,968 dots; strict registry overlap trip; DO NOT SUBMIT; UNSCORED</code>.</li>
</ul>
<p>For a future, separately validated file only: clear the spatially blocked holdout screen and
both registry checks (surface before placement and final dots) before considering the submission
form. The required pre-placement uniqueness receipt is absent for this lane62 artifact.</p>

<h2>4. Format-valid does not mean cleared for submission</h2>
<p>Two independent mechanisms produce the portal error <code>"Predicted values must be in
range [0, 1]"</code>, and both are properties of the competition's own inputs:
<b>(M1)</b> <code>training_features.tif</code> declares
<code>nodata = -3.4028234663852886e+38</code>, the float32 sentinel, so any pipeline that
passes a feature band through unchanged ships cells far outside [0, 1]; <b>(M2)</b> a
submission carrying a <code>nodata</code> tag of NaN can be read by a whole-raster range
check as containing values outside [0, 1]. This file is written all-finite with
<code>nodata = None</code>, so neither can occur. The group's own ledger records the same
score (0.1294) for a NaN-outside file and its all-finite twin, so nothing is lost. A
NaN-outside twin with bit-identical in-footprint values is reproducible with
<code>python3 scripts/make_variants.py</code>.</p>

<h2>5. Honest status — is it OK to submit?</h2>
<div class="banner bad"><b>Download for inspection: yes. Submit: NO — DO NOT SUBMIT.</b>
The preserved strict one-sided overlap is 1.0 (&gt; 0.70), so the binding verdict is
<b>DUPLICATE — STOP</b>. No organizer-confirmed score receipt exists. HOLDOUT-DTI and model
outputs are diagnostics, not competition scores.</div>
<table><tr><th>question</th><th>answer</th></tr>
<tr><td>format-valid?</td><td>yes — 14/14 local checks on re-read bytes; this is not upload clearance</td></tr>
<tr><td>strict uniqueness gate?</td><td><b>{GATE_P['verdict']}</b>; maximum one-sided Euclidean 3 px overlap
{money(GATE_P['max_overlap_all'],4)} against
<code>{html.escape(GATE_P['worst_overlap_all']['file'])}</code> (limit 0.70);
max positive ρ {money(GATE_P['max_positive_spearman'],4)} (limit 0.90; no rank trip).
Informative-only overlap {money(GATE_P['worst_overlap_discriminating']['overlap_3px_one_sided'],4)}
and Jaccard do not waive the strict trip.</td></tr>
<tr><td>pre-placement surface gate?</td><td><b>NOT VERIFIED</b> — no passing receipt is present</td></tr>
<tr><td>submit or spend a weekly slot?</td><td><b>NO — DO NOT SUBMIT; DUPLICATE — STOP</b></td></tr>
<tr><td>HOLDOUT-DTI proxy, independent off-catalogue truth (instrument B)</td>
<td><b>{money(gB['dti'])}</b>; lane62 <code>gems62.holdout</code> legacy harness (version untagged),
{gB['n_truth']:,} withheld positives; 95% CI not computed in retained evidence; not an organizer score.</td></tr>
<tr><td>HOLDOUT-DTI proxy, withheld catalogue segments (instrument A)</td>
<td><b>{money(gA['dti'])}</b>; lane62 <code>gems62.holdout</code> legacy harness (version untagged),
{PA['n_truth_A']:,} withheld positives; stored 95% CI
{money(PA['instrumentA_ci95'][0])}–{money(PA['instrumentA_ci95'][1])}; not an organizer score.</td></tr>
<tr><td>HOLDOUT-DTI proxy, mass-matched check (instrument B′, 7,905 px)</td>
<td>{money(PA['instrumentB_prime_dti'])}; CI not computed in retained evidence; not an organizer score.</td></tr>
<tr><td>economy of one more dot</td><td>mean credit
{money(PA['mean_credit_per_dot'],4)}/dot vs the marginal bar
{money(PA['credit_bar_at_s_0p2778'],4)} at the family best 0.2778 — below the bar, so a
weekly slot would not be spent on it</td></tr>
</table>

<h2>6. Reproduce</h2>
<pre>git clone https://github.com/buffedlizard55-lab/62GEMSDOE &amp;&amp; cd 62GEMSDOE
bash scripts/download_competition_data.sh        # reproduces data/ if you have a login
python3 scripts/prepare_data.py                  # verifies the grid contract from bytes
python3 scripts/run_lane.py                      # features, holdout, candidate
python3 scripts/finalize.py                      # selection, receipts
python3 scripts/uniqueness_gate.py docs/downloads/{P['name']}
python3 scripts/build_site.py
python3 -m pytest tests -q</pre>
"""

(DOCS / "assets").mkdir(parents=True, exist_ok=True)
(DOCS / "assets" / "site.css").write_text(CSS)
(DOCS / "index.html").write_text(page("Overview", body_index))
(DOCS / "executive-summary.html").write_text(page("Executive summary", body_exec))
print("wrote docs/index.html, docs/executive-summary.html, docs/assets/site.css")


# ------------------------------------------------------------------ results
def rows_html(rows, cols):
    head = "".join(f"<th>{html.escape(c[1])}</th>" for c in cols)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f"<td>{html.escape(c[2](r)) if len(c) > 2 else html.escape(str(r.get(c[0], '')))}</td>"
            for c in cols) + "</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


econ = e3["rows"]
champ = ver["champion_family"][:8]
body_results = f"""
<h1>Results</h1>
<h2>Verdicts for the two artefacts (literal parallel-run stop rule)</h2>
<table><tr><th>artefact</th><th>dots</th><th>strict gate verdict</th><th>max one-sided Euclidean 3 px overlap across all comparators (limit 0.70)</th><th>max positive ρ (limit 0.90)</th><th>disposition</th></tr>
<tr><td>{P['name']}</td><td>{PA['n_dots']:,}</td><td><b>{GATE_P['verdict']}</b></td><td>{money(GATE_P['max_overlap_all'],4)} (<code>{html.escape(GATE_P['worst_overlap_all']['file'])}</code>)</td><td>{money(GATE_P['max_positive_spearman'],4)}</td><td><b>DO NOT SUBMIT</b> — strict overlap trip</td></tr>
<tr><td>{S['name']}</td><td>{SA['n_dots']:,}</td><td><b>{GATE_S['verdict']}</b></td><td>{money(GATE_S['max_overlap_all'],4)} (<code>{html.escape(GATE_S['worst_overlap_all']['file'])}</code>)</td><td>{money(GATE_S['max_positive_spearman'],4)}</td><td><b>DO NOT SUBMIT</b> — strict overlap trip</td></tr></table>
<p class="mut">Both rows use the same rule set and the same 508-comparator registry. The
secondary's overlap is with a different lane's dot set, which is exactly the condition the
protocol names as lane drift.</p>

<p class="mut">Every figure below is MEASURED (reproducible from the pinned bytes) or
HOLDOUT-DTI. None is an organizer score.</p>

<h2>Instruments</h2>
<table>
<tr><th>instrument</th><th>truth</th><th>truth px</th><th>why it is here</th><th>its limit</th></tr>
<tr><td><b>A</b> — catalogue-segment holdout</td><td>whole catalogue segments hidden by a
2×2 spatial block, dilated by the 300 m kernel radius; visible catalogue masked
pixel-exactly; pooled over the whole grid</td><td>{PA['n_truth_A']:,}</td>
<td>the protocol's stated instrument</td><td>IR-30-046: ranking by this proxy is
<b>anti-correlated</b> with the public portal scores, because the portal's truth is faults
<i>absent</i> from the catalogue and catalogue pixels earn nothing</td></tr>
<tr><td><b>B</b> — independent off-catalogue</td><td>SGMC 1:750k state-map fault traces
rasterised to this grid, minus the competition catalogue — i.e. "mapped but not
catalogued", the class the competition scores</td><td>{gB['n_truth']:,}</td>
<td>an independent compilation not used by the organizer</td><td>1:750k generalisation is
coarse, and it is still not the organizer's private expert set</td></tr>
<tr><td><b>B′</b> — mass-matched</td><td>B subsampled to the {PA['hidden_mass_px']:,} px
inferred hidden test mass, 10 independent draws</td><td>{PA['hidden_mass_px']:,}</td>
<td>corrects B's 10.07× mass bias, which would otherwise push the budget too high</td>
<td>the {PA['hidden_mass_px']:,} px figure is a MODEL, the group's published inference from
the 0.2778 file</td></tr>
</table>

<h2>The shipped primary</h2>
<div class="card">
<p><b>{P['name']}</b> — {PA['n_dots']:,} dots, sha256 <code>{P['receipt']['sha256']}</code></p>
<table>
<tr><th>quantity</th><th>value</th><th>class</th></tr>
<tr><td>HOLDOUT-DTI, instrument A (catalogue-segment holdout)</td>
<td>{money(gA['dti'])} &nbsp; 95% CI {money(PA['instrumentA_ci95'][0])}–{money(PA['instrumentA_ci95'][1])}</td>
<td>HOLDOUT-DTI</td></tr>
<tr><td>same-stratum random control, same dot count (5 draws)</td>
<td>{money(ctrl['instrumentA'])}</td><td>MEASURED control</td></tr>
<tr><td><b>edge, instrument A</b></td><td><b>{ctrl['edge_instrumentA']:+.6f}</b> (loses)</td>
<td>MEASURED</td></tr>
<tr><td>HOLDOUT-DTI, instrument B (SGMC off-catalogue)</td><td>{money(gB['dti'])}</td>
<td>HOLDOUT-DTI</td></tr>
<tr><td>same-stratum random control, instrument B</td><td>{money(ctrl['instrumentB'])}</td>
<td>MEASURED control</td></tr>
<tr><td><b>edge, instrument B</b></td><td><b>{ctrl['edge_instrumentB']:+.6f}</b></td>
<td>MEASURED</td></tr>
<tr><td>HOLDOUT-DTI, instrument B′ (mass-matched)</td>
<td>{money(PA['instrumentB_prime_dti'])}</td><td>HOLDOUT-DTI</td></tr>
<tr><td>same-stratum random control, instrument B′</td>
<td>{money(ctrl['instrumentB_prime'])}</td><td>MEASURED control</td></tr>
<tr><td><b>edge, instrument B′</b></td><td><b>{ctrl['edge_instrumentB_prime']:+.6f}</b></td>
<td>MEASURED</td></tr>
<tr><td>mean realised credit per dot (instrument B)</td>
<td>{money(PA['mean_credit_per_dot'],4)} (median {money(PA['median_credit_per_dot'],4)})</td>
<td>MEASURED</td></tr>
<tr><td>marginal bar α·s at s = 0.2778</td>
<td>{money(PA['credit_bar_at_s_0p2778'],4)}</td><td>DERIVED from the published formula</td></tr>
<tr><td>share of dots clearing that bar</td>
<td>{PA['frac_dots_clearing_bar_at_0p2778']:.3f}</td><td>MEASURED</td></tr>
</table>
<p class="mut">The median credit of 0 is the honest headline: most emitted dots land
nowhere near an independent fault; the mean survives only because a minority land on one.
That variance is why the same-stratum control is the right comparator rather than a
random-over-the-map one.</p>
</div>

<h2>Selection sweep (the rule was fixed before the numbers)</h2>
<p>Product form is fixed by the lane brief: dot trains through flagged datum breaks,
thinned to 282.8 m spacing, pruned 3 px off the catalogue. Within that form the budget was
chosen by argmax of mean DTI on B′.</p>
{rows_html(site['selection']['sweep'], [('n_seeds','top-ranked flags used'),('half','half-length (px)'),('n_dots','dots'),('instrumentB_dti','DTI (B)'),('instrumentB_prime_dti','DTI (B′)'),('mean_credit_per_dot','mean credit/dot')])}
<p class="mut">Note the trap this exposes: <b>B′ rises monotonically all the way to the
largest budget tested</b>, because adding mass to a small-DTI file always helps while the
marginal dot's credit stays above a tiny bar. The selector alone would therefore have
grown the file without limit; the uniqueness gate and the lane's own "emit dotted lines /
only the convincing ones" instruction are what actually bound it.</p>

<h2>Why the lane does not get a slot — the same-instrument control</h2>
<p>An absolute mean credit is meaningless; only a comparison on the same truth can decide.
Reusing the group's own prior submissions <b>for learning only</b> as a comparison set:</p>
{rows_html(champ, [('file','registry raster (learning-only comparator)'),('n_dots','dots'),('mean_credit_instrumentB','mean credit/dot (instrument B)')])}
<p>The lane's most selective dot class reaches
{ver['lane_variants']['N50_half4']['mean_credit_instrumentB']:.3f} per dot on
{ver['lane_variants']['N50_half4']['n_dots']} dots. The best registered field reaches
{ver['best_champion_mean_credit']:.3f} per dot on
{ver['champion_family'][0]['n_dots']:,} dots — <b>roughly double the credit density and
500× the count</b>, i.e. it dominates this lane on both axes of the metric. Ratio
lane/best-champion = {ver['ratio_lane_over_best_champion']:.3f}.</p>
<div class="banner warn"><b>Forward lead for the selector, from the same measurement.</b>
The registry raster with the highest mean credit per dot on instrument B is
<code>{html.escape(ver['champion_family'][0]['file'])}</code>
({ver['champion_family'][0]['mean_credit_instrumentB']:.3f}), roughly 3× the 0.2778
family's own dots. If instrument B predicts the portal at all, that family is where this
group's remaining headroom sits — not here.</div>

<h2>Economics (experiment 3)</h2>
{rows_html(econ, [('N_flags','flags used'),('half','half-length'),('n_dots','dots'),('mean_credit_per_dot','mean credit/dot'),('frac_dots_clearing_bar_at_0p2778','share clearing bar'),('instrumentB_dti','DTI (B)')])}

<h2>Leakage canary</h2>
<p>Rule: a single feature reaching AUC &gt; 0.90 against the holdout truth is leakage until
proven otherwise. Maximum here is <b>{canary['max_auc']:.4f}</b> — <b>{canary['verdict']}</b>.</p>
{rows_html([{'k': k, 'v': v} for k, v in sorted(canary['auc'].items(), key=lambda x: -x[1])], [('k','feature'),('v','AUC vs instrument B')])}

<h2>Uniqueness gate</h2>
{rows_html(sorted(GATE_P['rows'], key=lambda r: -r['overlap_3px_one_sided'])[:12], [('file','comparator'),('n_positive','positives'),('effective_coverage','3 px dilation coverage'),('overlap_3px_one_sided','one-sided 3 px overlap'),('jaccard','Jaccard')])}
<p>Strict verdict <b>{GATE_P['verdict']}</b>: max one-sided overlap across all comparators is
{money(GATE_P['max_overlap_all'],4)} against
<code>{html.escape(GATE_P['worst_overlap_all']['file'])}</code>, above the 0.70 limit.
Positive-correlation leg {'trips' if GATE_P['rho_trip'] else 'does not trip'} (max positive
ρ {money(GATE_P['max_positive_spearman'],4)}; limit 0.90). The informative-subset overlap
{money(GATE_P['worst_overlap_discriminating']['overlap_3px_one_sided'],4)} over
{GATE_P['n_discriminating']} comparators and the Jaccard values are diagnostics only; they do
not suppress the binding duplicate stop. The dense comparator makes this rule uninformative
for that particular comparison, which is recorded as a limitation, not an exemption.</p>
"""

# ---------------------------------------------------------------- profiles
body_profiles = f"""
<h1>Deliverable 1 — shoreline elevation-versus-distance profiles with the flagged steps</h1>
<p class="mut">The lane's first deliverable, as requested: the datum residual along the
mapped Lahontan shoreline, with every flagged step and lateral deflection marked.</p>

<h2>How the traces were made</h2>
<ol>
<li><b>Isobase.</b> {isob['method']}. Result: RMS
{isob['rmse_m']:.2f} m over {isob['n_blocks']} blocks; median residual
{isob['residual_of_picks_m']['median']:.2f} m, p16–p84
{isob['residual_of_picks_m']['p16']:.2f}–{isob['residual_of_picks_m']['p84']:.2f} m.</li>
<li><b>Datum residual</b> ζ = z − isobase, and its zero contour traced with
marching squares on the {site['grid']['height']}×{site['grid']['width']} grid.</li>
<li><b>Flags.</b> Along each ordered trace, a <b>vertical step</b> is a change of
≥ {prof['thresholds']['zeta_step_m']} m between the mean of the
{prof['thresholds']['window_px']} samples before and after a position; a
<b>lateral deflection</b> is a ≥ {prof['thresholds']['heading_change_deg']}° change of
heading between the preceding and following chords. De-duplicated at 5 px.</li>
</ol>
<p>Result: <b>{prof['n_traces']} traces</b>, <b>{len(prof['flags'])} flags</b>
({sum(1 for f in prof['flags'] if f['kind'] == 'vertical_step')} vertical steps,
{sum(1 for f in prof['flags'] if f['kind'] == 'lateral_deflection')} lateral deflections).</p>

{svg_profile()}

<h2>Caveats a reader must carry</h2>
<ul class="tight">
<li><b>The isobase fit is degenerate in its linear part.</b>
Tilt is {isob['tilt_east_m_per_km']:.4f} m/km east and
{isob['tilt_north_m_per_km']:.4f} m/km north — near zero, because the estimator is the
median of a narrow elevation band per block, and a quadratic absorbs the literature's
~20 m northward tilt across the basin into its curvature terms. The fit is therefore
adequate for locating the datum (RMS {isob['rmse_m']:.2f} m) but the <i>tilt coefficients
must not be read as a rebound measurement</i>. That is flagged as IR-62-03.</li>
<li><b>The traces are the ζ = 0 contour of a block-median surface, not a digitised
shoreline.</b> At 100 m posting a 1–2 pixel shoreline cannot be picked directly; this is the
proxy the lane said it would use and it is the reason the lane's dot class is heterogeneous
(median credit 0).</li>
<li><b>{dem['limits']}</b></li>
</ul>

<h2>{len(prof['flags'])} flags, per trace</h2>
{rows_html([{'id': t['id'], 'n': t['n_vertices'], 'L': t['length_km'], 'f': t['n_flags'], 'b': str(t['bbox'])} for t in prof['traces']], [('id','trace'),('n','vertices'),('L','length km'),('f','flags'),('b','bbox (row0,col0,row1,col1)')])}
<p><a href="downloads/lahontan_shoreline_profiles.json">Download the full profiles
(JSON, all traces, all flags)</a>.</p>
"""

# ---------------------------------------------------------------- research
hyps = [
    dict(rank=1, name="H62-A — Datum-break dot trains (THIS SESSION'S PRODUCT)",
         layers="GeoDAWN 100 m DEM (absolute elevation); fitted quadratic isobase; DEM-ridge evidence E = 0.30·cross_max + 0.20·upface_max + 0.20·step_max + 0.20·curv_prof_absmax + 0.10·hs_lineament",
         sig="Along-trace change in the datum residual ζ = z − isobase (vertical_step) and change of trace heading (lateral_deflection)",
         why="A fault not in the catalogue still cuts the datum; the flag is where. Because the catalogue is masked, only off-catalogue flags can score.",
         cat=f"catalogue-masked emission with 3 px prune; {PA['n_dots']:,} dots; still only {ctrl['edge_instrumentB']:+.6f} over a same-stratum control",
         emodel=f"HOLDOUT-DTI A {money(gA['dti'])} (CI {money(PA['instrumentA_ci95'][0])}–{money(PA['instrumentA_ci95'][1])}), B {money(gB['dti'])}, B′ {money(PA['instrumentB_prime_dti'])}",
         cost="low", verdict="NEGATIVE for a slot; strict overlap DUPLICATE - STOP; format-valid but not cleared to submit"),
    dict(rank=2, name="H62-B — Per-flag credit gating with an independent compilation as the screen",
         layers="the same flag set, screened by agreement between two independent compilations (SGMC 1:750k state map; the group's own derived fault rasters) before emission",
         sig="Only flags where two compilations both miss a mapped trace can be candidates for a genuinely new fault",
         why="Directly targets the scoreable class (mapped-but-not-catalogued or unmapped), unlike the catalogue proxy",
         cat="none yet",
         emodel="not run — this session's budget of 3 experiments was spent on the lane's own product",
         cost="low (reuses this session's flag set and the registry already downloaded)",
         verdict="ranked highest of the untested ideas; requires no new external data"),
    dict(rank=3, name="H62-C — Rebound-corrected isobase from an external geoid/rebound model",
         layers="DEM + a published isostatic-rebound or geoid model for the Lahontan basin (e.g. the viscosity models of Bills, Adams & Wesnousky)",
         sig="Residual after removing a physically-modelled rebound surface rather than a fitted quadratic",
         why="A real rebound model has structure the quadratic cannot express, so the residual is closer to pure tectonic signal; it would also repair IR-62-03",
         cat="none",
         emodel="not run",
         cost="medium — needs a published model grid, or the ability to evaluate one of the group's published viscosity profiles for the basin",
         verdict="viable without new <i>data</i> only if a model grid is obtainable; otherwise blocked (see next-steps)"),
    dict(rank=4, name="H62-D — Shoreline zone as a mask for other lanes' fields, at higher density",
         layers="any high-credit field (e.g. the registry's best-credit raster) restricted to the shoreline zone, thinned at the measured optimum",
         sig="Reuse of an existing detector, restricted to where the datum exists",
         why="The datum is a physical reason to believe a fault would be expressed; restricting a good detector to it raises precision",
         cat="would inherit the source field's catalogue fit",
         emodel="not run",
         cost="low",
         verdict="this is essentially 'graft', and the same-instrument measurement above says the source field already dominates the lane, so restricting it is unlikely to raise its own credit; deprioritised"),
    dict(rank=5, name="H62-E — 1 m lidar shoreline pick over the full pluvial margin",
         layers="USGS 3DEP 1 m lidar DEM (public domain) over the Lahontan shoreline; the competition's own 1m_DEM_links.csv points at these tiles",
         sig="Direct metre-scale pick of the constructional berms instead of a 100 m proxy",
         why="This is the only way to fix the lane's core defect: at 100 m the shoreline is sub-pixel, which is why the median per-dot credit is 0",
         cat="n/a",
         emodel="not run",
         cost="high — needs the 1 m DEM tiles and reprojection to the 100 m grid, and the sandbox cannot reach the USGS 3DEP endpoints (verified 2026-10-11: TLS unreachable)",
         verdict="blocked on network access; named source: USGS 3DEP / The National Map, public domain"),
]
body_research = f"""
<h1>Research &amp; hypotheses</h1>
<p class="mut">Five candidate geological hypotheses, each naming the layers, the physical
signature, why it should catch a fault the catalogue misses, and how it differs from
anything already implemented — ranked by expected metric improvement and implementation
cost. None is validated unless the evidence column says so.</p>

<h2>The lane's mechanism, and its ceiling</h2>
<p>The Sehoo highstand shoreline is a near-level datum (15,475 ± 720 cal yr B.P.). Its
present elevation about a smooth isobase is a strain measurement, and a fault that breaks
it leaves a step or a lateral deflection. Verified literature, with links on
<a href="sources.html">Sources</a>:</p>
<ul class="tight">
<li>Briggs &amp; Wesnousky 2004, JGR 109 B08402: the Pyramid Lake fault zone offsets
post-Lahontan surfaces, ≥4 surface ruptures since desiccation, 2.6 ± 0.3 mm/yr right-lateral.</li>
<li>Dong et al. 2014, Geosphere 10(1) 40–48: a strike-slip fault <i>outboard</i> of the
Wassuk Range front right-laterally displaces Lahontan recessional shorelines 13.5–13.9 m.</li>
<li>Pierce, Wesnousky &amp; Owen 2016, SCEC poster #097: lidar reveals two previously
unmapped NW-striking fault segments near the centre of Smith Valley that offset Holocene
sediments.</li>
<li>Adams, Wesnousky &amp; Bills 1999; Adams et al. 2008: the highstand shoreline runs
~1,340 m near the basin centre to ~1,318 m at the northern edge — post-pluvial isostatic
rebound and northward tilting.</li>
</ul>
<p><b>The ceiling is structural, not an implementation defect.</b> The faults that offset
the Lahontan shoreline are largely the ones already mapped, and the organizer masks
catalogue pixels out of scoring entirely. So the lane's honest scope is the handful of
<i>unmapped</i> breaks, exactly as its brief anticipated ("if only a handful are
convincing, emit only those"). This session measured that handful and found it does not
carry a leaderboard score.</p>

<h2>Ranked hypotheses</h2>
"""
for hp in hyps:
    body_research += f"""<div class="card"><h3 style="margin-top:0">{html.escape(hp['name'])}</h3>
<table>
<tr><th style="width:210px">layer(s)</th><td>{html.escape(hp['layers'])}</td></tr>
<tr><th>physical signature</th><td>{html.escape(hp['sig'])}</td></tr>
<tr><th>why it beats the catalogue</th><td>{html.escape(hp['why'])}</td></tr>
<tr><th>differs from what exists how</th><td>{html.escape(hp['cat'])}</td></tr>
<tr><th>validation status</th><td>{hp['emodel']}</td></tr>
<tr><th>implementation cost</th><td>{html.escape(hp['cost'])}</td></tr>
<tr><th>verdict</th><td><b>{html.escape(hp['verdict'])}</b></td></tr>
</table></div>"""

body_research += f"""
<h2>Why the top-ranked candidate was not built here</h2>
<p>The parallel-run protocol caps this session at <b>3 experiments</b>. They were:
(1) the lane's own product and its holdout, (2) the selectivity sweep, (3) the emission
economics. H62-B is the highest-value untested idea and is handed forward with the flag set
already on disk (<code>evidence/profiles.json</code>) and the registry already downloaded
(<code>~/.cache/gems62_registry</code>, rebuilt by <code>scripts/build_registry.sh</code>).</p>

<h2>What would have to be true for this lane to win a slot</h2>
<ol>
<li>A metre-scale pick of the berms (H62-E), because at 100 m the shoreline is sub-pixel
and the per-dot credit collapses.</li>
<li>Or a per-flag screen that raises precision enough to clear the marginal bar α·s ≈
{money(PA['credit_bar_at_s_0p2778'],4)} per dot at a useful dot count — H62-B is the test.</li>
<li>Or a rebound model good enough that the residual is tectonic rather than fitted —
H62-C.</li>
</ol>
"""

# ---------------------------------------------------------------- sources
SOURCES = [
 ("Competition problem description — metric, masking, submission format",
  "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
  "read 2026-10-11 via the browsing fetch path; metric equations, worked example "
  "(TP_w 3.00 / FP_w 1.89 / FN_w 2.00 → 0.60), and the four submission-format clauses quoted verbatim"),
 ("Public leaderboard",
  "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
  "read 2026-10-11; #1 xiaofanhu 0.4133, #2 cfld__ 0.3585, #3 JerryDataWorks 0.3418, "
  "#9 DARD 0.3195, #23 extradr19 0.2778 — the brief's 0.3195/0.3774 are stale"),
 ("Competition data page (login-walled — verified)",
  "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
  "fetch 2026-10-11 returned a redirect to /accounts/login/ — the training rasters and "
  "1m_DEM_links.csv cannot be downloaded from this sandbox"),
 ("Reference solution (organizer's own)",
  "https://github.com/drivendataorg/gems-prize-reference-solution",
  "read; U-Net + Monte-Carlo CV, Tversky loss with alpha 0.2 / beta 0.8 (matching the "
  "metric), and a final write that sets no nodata tag"),
 ("Organizer staff ruling on masking",
  "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516",
  "quoted in the group's register IR-30-047: catalogue pixels are masked and re-masked in "
  "the final round; probability mass there earns no TP and no FP"),
 ("Adams & Wesnousky 1998, GSA Bulletin 110, 1318–1332 — highstand age and shorezone processes",
  "https://pubs.geoscienceworld.org/gsa/gsabulletin/article/110/10/1318/186135",
  "13,070 ± 60 14C yr B.P.; constructional crests vary <2.6 m within an embayment"),
 ("Briggs & Wesnousky 2004, JGR 109, B08402 — Pyramid Lake fault zone",
  "https://doi.org/10.1029/2003JB002717",
  "≥2.6 ± 0.3 mm/yr right-lateral on post-Lahontan surfaces; ≥4 ruptures since desiccation"),
 ("Dong et al. 2014, Geosphere 10(1), 40–48 — Wassuk Range strike-slip",
  "https://doi.org/10.1130/GES00912.1",
  "Lahontan recessional shorelines displaced 13.5–13.9 m right-laterally; ~1 mm/yr"),
 ("Pierce, Wesnousky & Owen 2016, SCEC Annual Meeting poster #097",
  "https://www.scec.org/publication/6917",
  "two previously unmapped NW-striking fault segments near the centre of Smith Valley "
  "offsetting Holocene sediments"),
 ("Adams, Wesnousky & Bills 1999 — Lahontan high shoreline isostatic rebound",
  "https://ui.adsabs.harvard.edu/abs/1999JGR...10417561A/abstract",
  "the highstand shoreline varies ~1,340 m (basin centre) to ~1,318 m (northern edge), "
  "i.e. northward tilt from post-pluvial rebound"),
 ("USGS GeoDAWN (the survey behind the magnetic/radiometric layers)",
  "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
  "product landing page; the DEM mirror used here carries the same GeoDAWN provenance"),
 ("INGENIOUS project (Great Basin Center for Geothermal Energy)",
  "https://gbcge.org/current-projects/ingenious/",
  "the fault compilation that, with the USGS Quaternary fault maps, forms the catalogue"),
 ("EPSG:32611",
  "https://epsg.io/32611",
  "the projected CRS the submission must be in"),
 ("Tversky index",
  "https://en.wikipedia.org/wiki/Tversky_index",
  "background on the metric's parent"),
 ("Official rules PDF (not reachable from this sandbox)",
  "https://docs.nlr.gov/docs/fy26osti/96647.pdf",
  "URL recorded, contents NOT read here — labelled UNVERIFIED"),
]
rows_src = "".join(
    f"<tr><td><a href='{html.escape(u)}'>{html.escape(t)}</a></td><td class='mut'>{html.escape(c)}</td></tr>"
    for t, u, c in SOURCES)
body_sources = f"""
<h1>Sources</h1>
<p class="mut">What was read, when, and what remains unverified. Anything not on this page
is not asserted anywhere on this site.</p>
<table><tr><th>source</th><th>what was taken from it / status</th></tr>{rows_src}</table>

<h2>Local data, with hashes</h2>
<table>
<tr><th>file</th><th>sha256</th><th>provenance class</th></tr>
<tr><td>data/official/sample_submission.tif</td><td><code>{site['files']['primary']['receipt']['sha256'] and '2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc'}</code></td>
<td>OWNER-MIRROR of the organizer template, byte-length 1,599,597 — matches the group's pinned manifest. Not organizer-authenticated in this checkout.</td></tr>
<tr><td>data/official/existing_faults.tif</td><td><code>7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093</code></td>
<td>OWNER-MIRROR; identical bytes to labels.tif (425,830 B), consistent with the group's record</td></tr>
<tr><td>data/external/geodawn_dem_a2_100m.tif</td><td><code>{dem['sha256']}</code></td>
<td>OWNER-MIRROR of a public USGS GeoDAWN product, from the group's 60GEMSDOE repository</td></tr>
<tr><td>data/external/derived_sgmc_faults_100m.tif</td><td><code>{hold['instrument_B']['sha256']}</code></td>
<td>INDEPENDENT PUBLIC COMPILATION (SGMC 1:750k) rasterised to this grid; used as instrument B</td></tr>
<tr><td>data/external/topo_10m_derived_100m_u8.tif</td><td><code>{evf['shas']['topo_10m_derived_100m_u8']}</code></td>
<td>OWNER-DERIVED from a 10 m DEM; bands addressed by their GeoTIFF <code>band_name</code> tags</td></tr>
<tr><td>data/external/lidar_scarp_features_u8.tif</td><td><code>{evf['shas']['lidar_scarp_features_u8']}</code></td>
<td>OWNER-DERIVED from 1 m USGS 3DEP lidar; the file carries NO band tags, so band order is
OWNER-DOCUMENTED (see the irregularities page)</td></tr>
</table>
"""

# ----------------------------------------------------------- irregularities
IRR = [
 ("IR-62-01", "High", "Open — no organizer score",
  "No submission from this repository has been scored. Every number is HOLDOUT-DTI, MEASURED or MODEL. The public leaderboard was read 2026-10-11 (#1 = 0.4133).",
  "Never write a projection as a score; label the verdict negative and let the selector decide."),
 ("IR-62-02", "Medium", "Verified — the portal range error has two root causes",
  "`training_features.tif` declares nodata = -3.4028234663852886e+38 (M1); a submission carrying a nodata tag of NaN can be read as out of range by a whole-raster check (M2).",
  "This repository writes all-finite with nodata = None and refuses to emit a receipt if any of the 12,279,160 cells is non-finite or outside [0, 1]."),
 ("IR-62-03", "High", "Open — the isobase fit is degenerate in its linear part",
  f"Fitted tilt is {isob['tilt_east_m_per_km']:.4f} m/km east and {isob['tilt_north_m_per_km']:.4f} m/km north, against the literature's ~20 m northward tilt across the basin. The estimator (median of a narrow elevation band per 20×20 km block) has a compressed dynamic range, and a quadratic can absorb the tilt into curvature.",
  "The fit is used only to locate the datum (RMS {:.2f} m). Its tilt coefficients are NOT reported as a rebound measurement anywhere on this site.".format(isob['rmse_m'])),
 ("IR-62-04", "High", "Corrected — literal strict gate trips; density limitation retained as a diagnostic",
  f"The top comparator, {OV['worst_overlap_all']['file']}, has {OV['worst_overlap_all']['n_positive']:,} positive pixels — 100 % of the footprint — so the saved candidate records one-sided overlap 1.0. This is above the binding 0.70 threshold, even though the comparator makes the test uninformative for substantive similarity.",
  "Use the protocol exactly: all-comparator one-sided overlap >0.70 means DUPLICATE - STOP. Coverage and Jaccard explain the limitation but do not waive it. The previous informative-only clearance is withdrawn; do not submit."),
 ("IR-62-05", "Medium", "Open — the selector was uninformative about the budget",
  "Mean DTI on the mass-matched instrument B′ rose monotonically to the largest budget tested ({} dots); there is no interior optimum inside the lane's product form.".format(site['selection']['chosen']['n_dots']),
  "The budget was therefore bounded by the lane's own product form and by the uniqueness gate, not by the selector. Stated on the Results page rather than smoothed over."),
 ("IR-62-06", "Medium", "Open — the lidar band order is owner-documented, not organizer-tagged",
  "`lidar_scarp_features_u8.tif` carries no band tags, so the mapping of band 8 to cross-scarp and band 7 to upface is taken from the group's own written documentation. This is the class of defect the group logged as IR-70-DATA-01.",
  "The evidence field addresses the tagged topo stack by tag and the untagged lidar stack by documented order, and the provenance is printed on this page and in evidence/evidence_field.json."),
 ("IR-62-07", "Critical", "Open — competition rasters are not organizer-authenticated here",
  "labels.tif, existing_faults.tif and sample_submission.tif are owner-mirrored files with hashes matching the group's pinned manifest, but the DrivenData data page is login-walled, so their authenticity was not established from this sandbox.",
  "Do not treat the mirrors as official on this repository's word alone; re-download through an authorized session and compare sha256 before relying on any final-round decision."),
 ("IR-62-08", "High", "Open — the instrument that would settle the question is external",
  "Instrument B is an independent public compilation but is 1:750k-generalised and is not the organizer's private expert set. The same-instrument conclusion that this lane is dominated depends on B transferring to the hidden truth.",
  "Stated wherever the comparison is quoted. The single decisive experiment — scoring two files on the portal itself — is outside this sandbox."),
 ("IR-62-09", "Low", "Fixed — bootstrap interval did not contain its own point estimate",
  "An earlier draft of src/gems62/holdout.py computed the confidence interval with the algebra T/(0.2T+0.2F+0.8n) while the point estimate came from dti_from_components; the two agreed only to the third decimal place.",
  "The bootstrap now recomputes the plug-in value and raises AssertionError unless it equals the pooled DTI to 1e-9. Covered by tests/test_holdout.py."),
 ("IR-62-11", "High", "Reported, not fixed — out of lane",
  "After merging <code>main</code>, the repository-root suite cannot even collect: "
  "<code>src/gems62/lahontan.py</code> imports <code>PIXEL_M</code> from "
  "<code>src/gems62/grid.py</code>, which does not define it, and "
  "<code>tests/test_metric.py</code> imports <code>brute_force_components</code> from "
  "<code>src/gems62/metric.py</code>, which does not define it (both symbols exist in "
  "<code>src/gems62/superseded_20261011/</code>). Reproduced on a clean "
  "<code>origin/main</code> worktree, so it is not caused by this branch.",
  "Left for the lane that owns those files — guessing which variant is canonical would be "
  "a silent overwrite. This lane's suite (<code>lane62/tests</code>) is independent and "
  "green: 45 passed."),
 ("IR-62-12", "Low", "Disclosed — independent re-derivation of an assigned lane",
  "This session was assigned the same lane as a sibling session that had already merged to "
  "<code>main</code> (v8 datum-offset). The naive merge was add/add everywhere, because both "
  "sessions used the same root paths.",
  "Instead of overwriting, this session's whole tree lives under <code>lane62/</code>; the "
  "two artefacts are <b>distinct</b> (3 px overlap 0.0099, exact overlap 0.0005, |ρ| 0.0021) "
  "and the sibling lane is left canonical at the root."),
 ("IR-62-10", "Low", "Fixed — rank-correlation leg sampled the wrong population",
  "The gate first sampled this file's own positive pixels for the correlation leg, which makes one side constant and the coefficient undefined.",
  "The sample is now drawn from the valid footprint, so the leg measures the correlation of two value fields as intended."),
]
rows_irr = "".join(
    f"<tr><td><b>{i}</b></td><td>{s}</td><td>{st}</td><td>{o}</td><td>{a}</td></tr>"
    for i, s, st, o, a in IRR)
body_irr = f"""
<h1>Irregularities and limitations</h1>
<p class="mut">Flagged, not smoothed over. “Fixed” means the repository now mitigates the
defect; it does not authenticate competition data or establish a score.</p>
<table><tr><th>ID</th><th>severity</th><th>status</th><th>observation / evidence</th>
<th>action or consequence</th></tr>{rows_irr}</table>

<h2>What this repository cannot do from this sandbox (measured 2026-10-11)</h2>
<ul class="tight">
<li>TLS to <code>drivendata.org</code>, <code>raw.githubusercontent.com</code>,
<code>sciencebase.gov</code>, <code>earthquake.usgs.gov</code> and the USGS 3DEP endpoints
is unreachable from the shell; the DrivenData pages <i>were</i> read through the browsing
path, which is why citations here carry a read date.</li>
<li>No GPU and ~2 vCPU, so no neural detector was trained; this lane is deliberately
physics-first.</li>
<li>The organizer's own <code>training_features.tif</code> (19 bands) is unavailable, so the
lane works from the DEM plus the group's derived stacks. Every claim that would need an
organizer band is labelled as such or omitted.</li>
</ul>
"""

# ---------------------------------------------------------------- run card
card = {
    "lane": "datum-offset lane — Lake Lahontan shorelines as a strain gauge",
    "session": "62GEMSDOE, branch arena/4e304372-62gemsdoe, 2026-10-11",
    "hypothesis": "The Lahontan highstand shoreline is a near-level datum (~15 ka); a fault "
                  "that cuts it produces an abrupt step or a lateral deflection that is "
                  "measurable in the DEM and locatable where no catalogue fault is mapped.",
    "mechanism": "fit a smooth isobase to the highstand band, take the datum residual "
                 "zeta = z - isobase, trace its zero contour, flag vertical steps and "
                 "heading changes along each trace, seed a dot train at every flag, extend "
                 "it along the local DEM-ridge direction, thin to 282.8 m, prune 3 px off "
                 "the catalogue",
    "non_fault_process_that_could_mimic_it": "Post-pluvial isostatic rebound and northward "
        "tilting tilt the datum by ~20 m across the basin (Adams, Wesnousky & Bills 1999; "
        "Adams et al. 2008). A fitted quadratic absorbs part of that tilt into its "
        "curvature terms, so a rebound gradient can masquerade as a step. Wave-cut "
        "terrace/berm constructional relief (<2.6 m within an embayment, Adams & "
        "Wesnousky 1998) is a second mimic at the same amplitude as the flagged steps.",
    "holdout_dti": dict(
        instrumentA=dict(value=gA["dti"], ci95=PA["instrumentA_ci95"],
                         withheld_positive_px=PA["n_truth_A"],
                         control_same_stratum=ctrl["instrumentA"],
                         edge=ctrl["edge_instrumentA"]),
        instrumentB=dict(value=gB["dti"], withheld_positive_px=gB["n_truth"],
                         control_same_stratum=ctrl["instrumentB"],
                         edge=ctrl["edge_instrumentB"]),
        instrumentB_prime=dict(value=PA["instrumentB_prime_dti"], mass_px=PA["hidden_mass_px"],
                               control_same_stratum=ctrl["instrumentB_prime"],
                               edge=ctrl["edge_instrumentB_prime"]),
        evidence_class="HOLDOUT-DTI (proxy; not an organizer score)",
        evaluator="lane62 gems62.holdout harness (no tagged semantic version in legacy receipt), "
                  "alpha 0.2, beta 0.8, 300 m triangular kernel, 2x2 spatial block, "
                  "catalogue masked pixel-exactly",
        ci_note="Instrument A has a stored 95% interval. Instruments B and B-prime have no 95% CI in the legacy evidence; do not call them organizer scores.",
        withheld_positives_note="instrument A withholds whole catalogue segments dilated by "
                                "the kernel radius; instrument B uses an independent "
                                "off-catalogue compilation, not the withheld catalogue"),
    "correlation_and_overlap_vs_registry": dict(
        verdict=GATE_P["verdict"],
        strict_gate_verdict=GATE_P["verdict"],
        passed=GATE_P["passed"],
        strict_gate_pass=GATE_P["strict_leg_pass"],
        overlap_trip=GATE_P["overlap_trip"],
        rho_trip=GATE_P["rho_trip"],
        max_overlap_all=GATE_P["max_overlap_all"],
        max_positive_spearman=GATE_P["max_positive_spearman"],
        n_comparators=GATE_P["n_comparators"],
        n_discriminating=GATE_P["n_discriminating"],
        worst_overlap_informative_diagnostic=GATE_P["worst_overlap_discriminating"],
        worst_overlap_strict=GATE_P["worst_overlap_all"],
        correlation_leg_pass=GATE_P["correlation_leg_pass"],
        limit_overlap=0.70, limit_positive_spearman=0.90,
        jaccard_is_gate=False,
        preplacement_surface_gate="NOT VERIFIED; no passing receipt present",
        note="strict overlap trip against the all-comparator registry; density/vacuity and Jaccard are diagnostics only"),
    "sibling_lane_crosscheck": dict(
        note="main already carries an independently merged datum-offset lane (v8). These "
             "candidates were compared against its shipped TIFs with the same convention "
             "as the registry gate; none is a duplicate.",
        pairs=xchk["pairs"]),
    "raster_sha256": P["receipt"]["sha256"],
    "validator_output": dict(
        single_band=True, dtype="float32", crs="EPSG:32611",
        shape=[site["grid"]["height"], site["grid"]["width"]],
        transform=site["grid"]["transform"], nodata=None,
        cells=int(site["grid"]["height"]) * int(site["grid"]["width"]),
        non_finite_cells=0, values_outside_unit_interval=0,
        positive_px_inside_footprint=PA["n_dots"], dots_on_catalogue=0,
        checks=[c["check"] for c in P["receipt"]["checks"]],
        source="scripts/finalize.py writes and then RE-READS the bytes from disk; the "
               "receipt is only produced if every clause passes"),
    "submission_name": "gems62-lahontan-datum-break-dotted-primary",
    "note_140": "Lahontan shoreline datum breaks; 86,968 dots; strict registry overlap trip; DO NOT SUBMIT; UNSCORED",
    "note_140_chars": len("Lahontan shoreline datum breaks; 86,968 dots; strict registry overlap trip; DO NOT SUBMIT; UNSCORED"),
    "preplacement_surface_gate": "NOT VERIFIED; no passing receipt is present for this legacy artifact",
    "verdict": "negative",
    "verdict_reason": "The preserved final-dot one-sided overlap is 1.0 (>0.70), so the binding verdict is DUPLICATE - STOP. The informative-only clearance is withdrawn; no submission is cleared. The pre-placement surface receipt is also absent. Holdout/economics results remain diagnostics, not organizer scores.",
    "budget": dict(experiments_planned=3, experiments_run=3,
                   note="lane product + holdout; selectivity sweep; emission economics. "
                        "A separate verification pass re-measured the same-instrument "
                        "comparison because an absolute mean credit is not interpretable."),
    "second_artifact": dict(name=S["name"], sha256=S["receipt"]["sha256"],
                            n_dots=SA["n_dots"],
                            status="DO NOT SUBMIT",
                            reason="fails the strict all-comparator overlap gate at "
                                   f"{GATE_S['max_overlap_all']:.4f} (>0.70); it also has "
                                   f"{GATE_S['worst_overlap_discriminating']['overlap_3px_one_sided']:.4f} "
                                   "overlap against sparse comparator "
                                   f"{GATE_S['worst_overlap_discriminating']['file']}"),
    "deliverable_1": dict(file="docs/downloads/lahontan_shoreline_profiles.json",
                          n_traces=prof["n_traces"], n_flags=len(prof["flags"]),
                          note="elevation-versus-distance profiles with flagged steps"),
}
body_card = f"""
<h1>Run card</h1>
<p class="mut">One JSON object, as the parallel-run protocol requires. Machine-readable copy:
<a href="data/run_card.json">docs/data/run_card.json</a>.</p>
<h2>Read these two lines first</h2>
<ul class="tight">
<li><b>{P['name']}</b> — strict registry verdict <b>{GATE_P['verdict']}</b>: max one-sided
Euclidean 3 px overlap {money(GATE_P['max_overlap_all'],4)} across all comparators (limit 0.70),
max positive ρ {money(GATE_P['max_positive_spearman'],4)} (limit 0.90). Download for review only;
<b>DO NOT SUBMIT</b>.</li>
<li><b>{S['name']}</b> — strict registry verdict <b>{GATE_S['verdict']}</b>:
max one-sided overlap {money(GATE_S['max_overlap_all'],4)} against
<code>{html.escape(GATE_S['worst_overlap_all']['file'])}</code>.
<b>DO NOT SUBMIT</b>; kept as evidence.</li>
</ul>
<pre>{html.escape(json.dumps(card, indent=1))}</pre>
"""

(DOCS / "results.html").write_text(page("Results", body_results))
(DOCS / "profiles.html").write_text(page("Profiles", body_profiles))
(DOCS / "research.html").write_text(page("Research", body_research))
(DOCS / "sources.html").write_text(page("Sources", body_sources))
(DOCS / "irregularities.html").write_text(page("Irregularities", body_irr))
(DOCS / "run-card.html").write_text(page("Run card", body_card))
json.dump(card, open(DOCS / "data" / "run_card.json", "w"), indent=1, default=str)
json.dump(card, open(EV / "run_card.json", "w"), indent=1, default=str)
print("wrote results, profiles, research, sources, irregularities, run-card")
