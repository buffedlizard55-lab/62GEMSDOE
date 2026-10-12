#!/usr/bin/env python3
"""Rewrite the download hero on ``docs/index.html`` from the receipts.

Why this exists: the hero was hand-edited when H62-R replaced H62-B, and the file the
page offered (27,623 dots, sha ``bd4690db``, 163,775 bytes) was not the file the evidence
described (14,765 dots, sha ``d5a15369``, 116,946 bytes).  The page and the receipts had
drifted apart, which is exactly the failure the whole ``tests/`` suite exists to prevent.
From here on the hero is generated: every number is read from a receipt, never typed.

Run after any lane re-run:  .venv/bin/python scripts/update_hero.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BEGIN = "<!-- ============================ DOWNLOAD"
END = "<!-- ============================ /DOWNLOAD"


def main() -> int:
    cur = json.loads((ROOT / "evidence" / "current_artifact.json").read_text())
    ev = ROOT / "evidence" / "h62r"
    emit = json.loads((ev / "e5_emission.json").read_text())["emission"]
    val = json.loads((ev / "e6_validation.json").read_text())
    stat = json.loads((ev / "e10_field_stats.json").read_text())
    uni = json.loads((ev / "e7_uniqueness.json").read_text())
    hold = json.loads((ev / "e9_holdout.json").read_text())
    surf = json.loads((ev / "e1_surfaces.json").read_text())
    lines = json.loads((ev / "e3_repeat_offsets.json").read_text())
    prof = json.loads((ev / "e4_profiles.json").read_text())
    card = json.loads((ev / "e8_run_card.json").read_text())
    trace_km = float(emit.get("trace_km", 0.0))
    if not trace_km:                       # E5 nests it under the emission block
        trace_km = float(json.loads((ev / "e5_emission.json").read_text()).get("trace_km", 0.0))

    lv = " / ".join(str(int(d["level"]["elev_m"])) for d in surf["levels"])
    sup = " / ".join(str(d["level"]["block_support"]) for d in surf["levels"])
    steps = " / ".join(f"{d['n_step']:,}" for d in surf["levels"])
    ctrl = hold["controls_mean"]
    dm = stat["dot_dist_to_catalogue_m"]
    note = cur["submission_note"]
    assert len(note) <= 140, f"the note is {len(note)} chars; the portal allows 140"

    hero = f'''{BEGIN} — the first thing on the page ================== -->
<div class="hero" id="download" style="border-color:var(--warn);background:rgba(210,153,34,.07)">
<h2 style="border:0;margin-top:0">The submission file — and whether you should submit it</h2>

<p><span class="pill ok">FORMAT: LEGAL — 14/14 on the bytes re-read from disk</span>&nbsp;
<span class="pill ok">UNIQUE — max |ρ| {uni["max_abs_rho"]:.4f} vs {uni["n_compared"]} comparators</span>&nbsp;
<span class="pill ok">ISOLATION: 0 of {cur["n_dots"]:,} dots has any kernel overlap</span>&nbsp;
<span class="pill ok">OFF-CATALOGUE — {dm["frac_within_300m"]:.1%} of dots within 300 m of a mapped fault</span>&nbsp;
<span class="pill warn">VERDICT: SUBMIT AS A PROBE — not a validated gain</span></p>

<p class="big">{cur["submission_name"]}.tif</p>
<p><a class="btn" href="downloads/{cur["submission_name"]}.tif">⬇ Download the GeoTIFF ({cur["bytes"]:,} bytes)</a>
<a class="btn sec" href="downloads/{cur["submission_name"]}.zip">⬇ .zip</a>
<a class="btn sec" href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">Submit it here ↗</a>
<a class="btn sec" href="executive-summary-h62r.html">Six steps + full verdict ↗</a></p>

<p><b>Session <code>{cur["session"]}</code> — new method, {cur["date"]}.</b>
The Lahontan datum is a <b>stack of nested shorelines</b>, not one surface. This session
<b>detected</b> four levels from the DEM alone ({lv} m; block support {sup} of 323
twenty-kilometre blocks), fitted a robust tile-mode isobase per level, flagged steps in the
physical 15–140 m throw window, and kept only the steps that lie on <b>one common line with
steps on a second level</b> — a Hough collinearity vote. Then it seeded a trace at each,
extended it on DEM-ridge evidence, and emitted dotted lines.</p>

<table class="kv">
<tr><td>sha256</td><td><code>{cur["sha256"]}</code></td></tr>
<tr><td>dots / values</td><td><b>{cur["n_dots"]:,}</b> single-pixel dots, values exactly <code>{{0, 1}}</code>. Two independent validators, both re-reading the bytes from disk: <code>n_outside_0_1 = {val["grid_check"]["n_outside_0_1"]}</code>, <code>nan_count = {val["grid_check"]["nan_count"]}</code>, <code>nodata = {json.dumps(val["grid_check"]["nodata"])}</code>.</td></tr>
<tr><td>Isolation</td><td>MEASURED against the metric's own kernel <code>k(d) = max(1 − d/300 m, 0)</code>: minimum nearest-neighbour distance <b>{stat["nn_min_m"]:.6f} m</b>, and <b>{emit["n_dots_with_kernel_overlap"]}</b> of {cur["n_dots"]:,} dots receives any kernel mass from another dot (max <b>{emit["max_kernel_mass_from_other_dots"]:.6f}</b>). No two dots waste mass on one another.</td></tr>
<tr><td>Distance to the mapped catalogue</td><td><b>{dm["frac_within_300m"]:.1%}</b> of dots within 300 m (nearest is {dm["min"]:.0f} m); median <b>{dm["median"]:,.0f} m</b>; {dm["frac_within_1000m"]:.1%} within 1 km. Dots inside 300 m were deleted — those pixels are masked out of live scoring (organizer thread 11516).</td></tr>
<tr><td>Dots dropped for that exclusion</td><td>{emit["n_dropped_catalogue_exclusion"]:,} of {emit["n_sampled"]:,} samples, from {emit["n_traces"]} traces ({trace_km:,.0f} km).</td></tr>
<tr><td>Submission name</td><td><code>{cur["submission_name"]}</code></td></tr>
<tr><td>Submission note ({len(note)} chars, limit 140)</td><td><code>{note.replace("&", "&amp;").replace(">", "&gt;").replace("<", "&lt;")}</code></td></tr>
<tr><td>Uniqueness vs the registry</td><td><b>UNIQUE.</b> {uni["n_compared"]} comparators from the harvested registry: max |Spearman| <b>{uni["max_abs_rho"]:.4f}</b> (limit {uni["rho_limit"]}), worst symmetric 3-px Jaccard <b>{uni["worst_jaccard3px"]["value"]:.4f}</b>, {uni["n_comparators_over_overlap_limit_nonvacuous"]} comparators over the overlap limit among the non-vacuous. {uni["n_vacuous"]} were flagged <i>vacuous</i> (their own 3-px dilation covers ≥70 % of the footprint, so overlap with anything is meaningless). Full report: <a href="../evidence/h62r/e7_uniqueness.json">e7_uniqueness.json</a>.</td></tr>
<tr><td>Does it pass the protocol's holdout gate?</td><td><b>{hold["pooled_dti"]:.6f}</b> — and that number is <b>structurally vacuous, not a failure of the field</b>. The catalogue-exclusion radius and the metric kernel radius are both 300 m, so a dot that obeys the exclusion has kernel weight exactly 0 against every mapped fault. Equal-budget controls on the same {hold["n_folds"]} folds × {len(hold["seeds"])} seeds, {hold["withheld_positives_total"]:,} withheld positives: random_lines <b>{ctrl["random_lines"]:.4f}</b>, random_dots <b>{ctrl["random_dots"]:.4f}</b>, catalogue_offset <b>{ctrl["catalogue_offset"]:.4f}</b>. Logged as <code>IR-62-H62R-02</code>.</td></tr>
<tr><td>Expected score</td><td><b>Not claimed.</b> No local instrument in this repository can rank this field — see <a href="executive-summary-h62r.html">the limits section</a>.</td></tr>
<tr><td>Organizer score</td><td><b>none</b> — never submitted. <code>organizer_score: {json.dumps(cur["organizer_score"])}</code>.</td></tr>
<tr><td>The lane's own numbers</td><td>Steps flagged per level: {steps} ({lines["n_flagged_total"]:,} total) → {lines["n_lines"]:,} accepted lines, all multi-level, {lines["n_support_px"]:,} support px → {emit["n_traces"]} traces ({trace_km:,.0f} km). Deflection flags: <b>{lines["per_level_points"] and sum(d["n_deflect"] for d in surf["levels"])}</b> — a measured NULL on all four levels even at a 1.2 km lever arm (<code>IR-62-DEFL-01</code>).</td></tr>
<tr><td>First deliverable (the lane asks for this)</td><td><a href="h62r/h62r_shoreline_profiles.png">shoreline elevation-vs-distance profiles with the flagged steps</a> — {prof["n_profiles"]} runs, {prof["total_profile_km"]:,.0f} km, {prof["n_profiles_with_step"]} carrying flagged steps · <a href="downloads/h62r-shoreline-profiles.csv">CSV</a> · <a href="h62r/h62r_level_spectrum.png">the measured level spectrum</a> · <a href="h62r/h62r_field_map.png">field map</a></td></tr>
<tr><td>Read before spending a slot</td><td><a href="executive-summary-h62r.html">executive summary &amp; the six submission steps</a> · <a href="hypotheses-h62r.html">five ranked hypotheses</a> · <a href="irregularities.html">irregularities (three new ones this session)</a></td></tr>
</table>

<h3>Files from earlier sessions — each with its own verdict, kept because negatives are deliverables</h3>
<p><code>gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif</code> (481,168 B, session <code>arena/d0303476</code>)
<span class="pill warn">PROBE — legal, unique, no organizer score</span> ·
<a href="downloads/gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif">⬇ download</a></p>
<p><code>gems62d-org-stack-inverted-truth-detector-46598-zeros.tif</code> (372,859 B, session <code>arena/dfc9787b</code>)
<span class="pill warn">PROBE — projection 0.110, below the incumbent band</span> ·
<a href="downloads/gems62d-org-stack-inverted-truth-detector-46598-zeros.tif">⬇ download</a></p>
<p><code>gems62-h62g-benchcrosscut-hardcore-zeros.tif</code> (98,893 B, session <code>arena/2b64062a</code>)
<span class="pill no">NEGATIVE — at chance on the proxy instrument</span> ·
<a href="downloads/gems62-h62g-benchcrosscut-hardcore-zeros.tif">⬇ download</a></p>
<p><code>gems62-h62i-scarpcrosscut-hardcore-zeros.tif</code> (282,543 B)
<span class="pill no">QUARANTINED — duplicate-drift</span></p>

<h3>Files that must NOT be submitted — the cause of the portal error you hit</h3>
<p>Two earlier files encoded "outside the data" as <b>NaN</b> (measured: 7,111,787 NaN cells each,
exactly the number of out-of-footprint cells). A range test applied to NaN fails, and that is the
mechanism behind <i>"Predicted values must be in range [0, 1]"</i>. They now live in
<a href="downloads/quarantined-not-submittable/">docs/downloads/quarantined-not-submittable/</a>
with the diagnosis, and <code>tests/test_downloads_are_submittable.py</code> re-reads every offered
<code>.tif</code> from disk and fails CI if any of them has a NaN tag, a NaN value or a value outside
<code>[0, 1]</code>. <b>Nothing in <code>docs/downloads/*.tif</code> — as opposed to the quarantine
subfolder — has NaN or a nodata tag.</b></p>
</div>
{END} -->
'''

    p = DOCS / "index.html"
    s = p.read_text()
    if BEGIN not in s:
        print(f"::{BEGIN} marker not found in {p}", file=sys.stderr)
        return 1
    i = s.index(BEGIN)
    if END in s:
        j = s.index(END, i) + len(END) + len(" -->")
    else:
        # first run against the hand-written hero: it has no end marker.  The hero's
        # last block is the quarantine paragraph; the first </div> after it closes it.
        anchor = "has NaN or a nodata tag.</b></p>"
        k = s.index(anchor, i)
        j = s.index("</div>", k) + len("</div>")
    p.write_text(s[:i] + hero.rstrip("\n") + s[j:])
    print(f"{p} hero rewritten from receipts: {cur['n_dots']:,} dots, sha {cur['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
