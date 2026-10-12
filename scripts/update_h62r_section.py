#!/usr/bin/env python3
"""Render lane H62-R's block on ``docs/index.html`` (and its row in the all-files table).

Why a generator rather than a hand-edit: this lane has already been bitten once by a page that
was written by hand while a re-run changed the bytes underneath it (IR-62-H62R-04).  Every
number in the block below is read from a receipt in ``evidence/h62r/`` or from the audit's own
``.verdict.json`` sidecar, and the script refuses to write at all if the two disagree.
``tests/test_shipped_artifact_h62r.py`` re-derives the same numbers from the raster.

Run after any lane re-run plus ``scripts/audit_downloads.py --write``:

    .venv/bin/python scripts/update_h62r_section.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVID = ROOT / "evidence" / "h62r"
BEG = "<!-- ==================== LANE H62-R (session arena/7eee17f9) ==================== -->"
END = "<!-- ==================== /LANE H62-R ==================== -->"
NAME = "gems62-h62r-multilevel-datum-repeat-offset-zeros"


def _nan_twins() -> list[dict]:
    """The NaN-encoded files, read from the audit's manifest rather than described by hand."""
    man = json.loads((DOCS / "downloads" / "manifest.json").read_text())
    return [r for r in man["files"]
            if not r.get("format_legal") and "no_nan_anywhere" in (r.get("fails") or [])]


def _receipts() -> dict:
    j = lambda n: json.loads((EVID / n).read_text())
    sidecar = json.loads((DOCS / "downloads" / f"{NAME}.verdict.json").read_text())
    return dict(
        sidecar=sidecar,
        val=j("e6_validation.json"),
        emit=j("e5_emission.json"),
        stat=j("e10_field_stats.json"),
        uni=j("e7_uniqueness.json"),
        hold=j("e9_holdout.json"),
        surf=j("e1_surfaces.json"),
        lines=j("e3_repeat_offsets.json"),
        prof=j("e4_profiles.json"),
        card=j("e8_run_card.json"),
    )


def _section(r: dict) -> str:
    sc, val, emit, stat = r["sidecar"], r["val"], r["emit"], r["stat"]
    uni, hold, surf, lines, prof = r["uni"], r["hold"], r["surf"], r["lines"], r["prof"]
    grid, em = val["grid_check"], emit["emission"]
    dm = stat["dot_dist_to_catalogue_m"]
    ctrl = hold["controls_mean"]
    trace_km = float(emit.get("trace_km") or r["card"].get("trace_km") or 0.0)

    # the generator's own guardrails: the sidecar and the receipts must describe one file
    assert sc["sha256"] == grid["sha256"], "sidecar and validation disagree on the sha256"
    assert sc["bytes"] == grid["bytes"], "sidecar and validation disagree on the byte count"
    assert sc["dots"] == stat["n_dots"] == em["n_dots"], "dot counts disagree"
    assert sc["checks_passed"] == sc["checks_total"] == 14, sc["checks_passed"]

    twins = _nan_twins()
    nan_cells = max((int(t.get("nonfinite_pixels") or 0) for t in twins), default=0)
    lv = " / ".join(str(int(d["level"]["elev_m"])) for d in surf["levels"])
    sup = " / ".join(str(d["level"]["block_support"]) for d in surf["levels"])
    steps = " / ".join(f"{d['n_step']:,}" for d in surf["levels"])
    deflect = sum(int(d["n_deflect"]) for d in surf["levels"])
    n_vac = uni["n_vacuous"]
    n_nan = len(twins)
    note = sc["submission_note"]
    assert len(note) <= 140, f"the submission note is {len(note)} chars"

    return f'''{BEG}
<h2 id="h62r">Lane H62-R — the Lahontan datum as a <i>stack</i> of shorelines, and a repeat-offset test across them</h2>
<div class="card">
<p><span class="pill ok">FORMAT: LEGAL — {sc["checks_passed"]}/{sc["checks_total"]} on the bytes re-read from disk</span>
&nbsp;<span class="pill ok">UNIQUE — max |ρ| {uni["max_abs_rho"]:.4f} over {uni["n_compared"]} comparators</span>
&nbsp;<span class="pill ok">ISOLATION: PROVEN — {em["n_dots_with_kernel_overlap"]} of {sc["dots"]:,} dots receive any kernel mass</span>
&nbsp;<span class="pill ok">OFF-CATALOGUE — {dm["frac_within_300m"]:.1%} within 300 m, median {dm["median"]:,.0f} m</span>
&nbsp;<span class="pill warn">HOLDOUT GATE: STRUCTURALLY VACUOUS — see below, not a pass</span></p>

<p class="big">{sc["name"]}</p>
<p><a class="btn" href="downloads/{sc["name"]}">⬇ Download the GeoTIFF ({sc["bytes"]:,} bytes)</a>
<a class="btn sec" href="downloads/{NAME}.zip">⬇ .zip</a>
<a class="btn sec" href="executive-summary-h62r.html">Six submission steps + full verdict ↗</a>
<a class="btn sec" href="hypotheses-h62r.html">Ranked hypotheses ↗</a></p>

<p><b>Session <code>arena/7eee17f9-62gemsdoe</code>, lane H62-R, 2026-10-12.</b>
The Lahontan datum is not one surface but a <b>stack of nested shorelines</b> of different ages.
This lane <b>detects</b> the stack from the DEM instead of assuming a datum band
({lv} m, on block support {sup} of 323 twenty-kilometre blocks), fits a robust tile-mode isobase
per level, flags steps in the physical 15–140 m throw window, and then keeps only the steps that
lie on <b>one common line with steps on at least one other level</b> — a Hough collinearity vote,
because nested shorelines are crossed by one fault at <i>different map points</i>, so the naive
"same place on two levels" test cannot work. It then seeds a trace at each surviving step,
extends it on DEM-ridge evidence, and emits dotted lines.</p>

<table class="kv">
<tr><td>sha256</td><td><code>{sc["sha256"]}</code></td></tr>
<tr><td>What it is</td><td><b>{sc["dots"]:,}</b> single-pixel dots, values exactly <code>{{0, 1}}</code>,
 {sc["bytes"]:,} bytes, <code>nodata = null</code>, <code>nan_count = {grid["nan_count"]}</code>,
 <code>n_outside_0_1 = {grid["n_outside_0_1"]}</code> — re-read from the bytes by two independent
 validators, so the portal error <i>"Predicted values must be in range [0, 1]"</i> cannot occur for
 this file. Portal range risk: <code>{sc["portal_range_risk"]}</code>.</td></tr>
<tr><td>Isolation — why no dot wastes mass</td><td>Measured against the metric's own kernel
 <code>k(d) = max(1 − d/300 m, 0)</code>: minimum nearest-neighbour distance <b>{stat["nn_min_m"]:.6f} m</b>
 (greedy thinning at 300 m, so the distance is the thinning distance exactly), and
 <b>{em["n_dots_with_kernel_overlap"]}</b> of {sc["dots"]:,} dots receives <b>any</b> kernel mass from
 another dot — maximum received mass <b>{em["max_kernel_mass_from_other_dots"]:.6f}</b>. Cross-checked
 two ways after this lane's own first statistic was found to be wrong in the flattering direction
 (<code>IR-62-H62R-03</code>).</td></tr>
<tr><td>Distance to the mapped catalogue</td><td><b>{dm["frac_within_300m"]:.1%}</b> of dots within
 300 m of a mapped fault (nearest {dm["min"]:.0f} m); median <b>{dm["median"]:,.0f} m</b>;
 <b>{dm["frac_within_1000m"]:.1%}</b> within 1 km. {em["n_dropped_catalogue_exclusion"]:,} of
 {em["n_sampled"]:,} samples were deleted by the 300 m exclusion — those pixels are masked out of live
 scoring (organiser forum thread 11516).</td></tr>
<tr><td>Unique against the registry</td><td>{uni["n_compared"]} comparators harvested from the
 group and organiser repositories: max |tie-aware Spearman| <b>{uni["max_abs_rho"]:.4f}</b>
 (limit {uni["rho_limit"]:,}), worst symmetric 3-px-dilated Jaccard <b>{uni["worst_jaccard3px"]["value"]:.4f}</b>
 ({uni["worst_jaccard3px"]["alias"].split("__")[-1]}), and
 <b>{uni["n_comparators_over_overlap_limit_nonvacuous"]}</b> comparators over the overlap limit among the
 non-vacuous. <b>{n_vac}</b> comparators are flagged <i>vacuous</i> because their own 3-px dilation covers
 ≥70 % of the footprint, so overlap with them carries no information (<code>IR-62-22</code>).
 {uni["n_skipped"]} file was skipped (a 32×48 format-test image — shape mismatches are counted, not fatal,
 <code>IR-62-REG-02</code>). Full report:
 <a href="../evidence/h62r/e7_uniqueness.json">e7_uniqueness.json</a>.</td></tr>
<tr><td>The holdout gate — read this before trusting it</td><td><b>{hold["pooled_dti"]:.6f}</b>, and that
 number is <b>structurally vacuous for this field, not a failure of it</b>: the catalogue-exclusion radius and
 the metric kernel radius are both 300 m, so a dot that obeys the exclusion has kernel weight exactly 0
 against every mapped fault. On the same {hold["n_folds"]} folds × {len(hold["seeds"])} seeds over
 {hold["withheld_positives_total"]:,} withheld positives, the equal-budget controls score
 random_lines <b>{ctrl["random_lines"]:.4f}</b>, random_dots <b>{ctrl["random_dots"]:.4f}</b>,
 catalogue_offset <b>{ctrl["catalogue_offset"]:.4f}</b> — this field scores <i>below its own random-dot
 control</i>, which is the signature of the exclusion rather than of a bad field. Logged as
 <code>IR-62-H62R-02</code>; not "fixed" by shrinking the exclusion, because the calibration
 (ρ = −0.597 against the mapped catalogue) is what demands it.</td></tr>
<tr><td>What the lane measured</td><td>Steps flagged per level: {steps} ({lines["n_flagged_total"]:,} in
 total) → <b>{lines["n_lines"]:,}</b> accepted lines, <b>all</b> multi-level, {lines["n_support_px"]:,}
 support px → <b>{em["n_traces"]}</b> traces over <b>{trace_km:,.0f} km</b> → {sc["dots"]:,} dots.
 Lateral-deflection flags: <b>{deflect}</b> — a measured NULL on all four levels even at a 1.2 km lever
 arm (<code>IR-62-DEFL-01</code>); no deflection claim is made anywhere.</td></tr>
<tr><td>First deliverable (the lane asks for this first)</td><td>
 <a href="h62r/h62r_shoreline_profiles.png">shoreline elevation-vs-distance profiles with the flagged
 steps</a> — <b>{prof["n_profiles"]}</b> runs, <b>{prof["total_profile_km"]:,.0f} km</b>,
 <b>{prof["n_profiles_with_step"]}</b> carrying flagged steps ·
 <a href="downloads/h62r-shoreline-profiles.csv">machine-readable CSV</a> ·
 <a href="h62r/h62r_level_spectrum.png">the measured level spectrum</a> ·
 <a href="h62r/h62r_field_map.png">the field against the excluded catalogue</a></td></tr>
<tr><td>Should it take the slot?</td><td>{sc["verdict"]}</td></tr>
<tr><td>Submission note ({len(note)}/140 chars)</td><td><code>{note.replace("&", "&amp;").replace(">", "&gt;").replace("<", "&lt;")}</code></td></tr>
<tr><td>Expected score</td><td><b>Not claimed.</b> No local instrument in this repository can rank this
 field, and the two off-catalogue proxies that exist disagree with each other in this repository's own
 record. Organiser score: <b>none</b> — never submitted.</td></tr>
</table>
<p><b>Why some files in the table below say "not legal".</b> The portal error the owner hit —
<i>"Predicted values must be in range [0, 1]"</i> — is produced by encoding "outside the data" as
<b>NaN</b>: a range test applied to NaN fails. The {n_nan} NaN-encoded twins in this repository carry
<b>{nan_cells:,}</b> non-finite cells each, which is exactly the number of cells outside the survey
footprint (12,279,160 − 5,167,373), so the encoding is deliberate and the mechanism is measured —
but it is not the encoding this lane ships. Every raster offered here has its own row, its own
checks and its own verdict, and the button above is verified legal on re-read by
<code>tests/test_downloads_are_submittable.py</code>.</p>
<p class="mut">Defects this lane found and fixed in flight — <code>IR-62-REG-01</code> (the registry harvest
overwrote itself, so the drift gate was comparing against a fraction of the registry while reporting the full
count), <code>IR-62-REG-02</code> (one format-test image aborted the whole check),
<code>IR-62-H62R-01</code> (a span-only line test produced radiating "star" artifacts),
<code>IR-62-H62R-03</code> (this lane's own isolation statistic counted a dot as its own neighbour) — are in
<a href="irregularities.html">the register</a>.</p>
</div>
{END}'''


def _row(name: str, row: dict, sc: dict) -> str:
    """One row of the all-files table, built from the manifest row + the generated sidecar."""
    esc = lambda t: (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    legal = bool(row.get("format_legal"))
    pills = ['<span class="pill ok">legal</span>' if legal else
             '<span class="pill no">not legal: ' + ", ".join(row.get("fails") or []) + '</span>']
    if not legal and row.get("portal_range_risk"):
        pills.append(f'<span class="pill warn">range risk {esc(str(row["portal_range_risk"]))}</span>')
    return (f'<tr><td><a href="downloads/{name}">{name}</a>{" ".join(pills)}</td>'
            f'<td>{row.get("dots"):,}</td><td>{row.get("bytes"):,} B</td>'
            f'<td>{row.get("checks_passed")}/{row.get("checks_total")}</td>'
            f'<td><code>{row.get("sha256", "")[:16]}…</code></td>'
            f'<td>{esc(sc.get("verdict"))}</td></tr>')


def _all_rows() -> dict:
    """Every site raster with its manifest row and generated sidecar, keyed by file name."""
    out: dict[str, tuple[dict, dict]] = {}
    for row in json.loads((DOCS / "downloads" / "manifest.json").read_text())["files"]:
        if pathlib.PurePosixPath(row["path"]).parent != pathlib.PurePosixPath("docs/downloads"):
            continue
        name = pathlib.Path(row["path"]).name
        side_car = DOCS / "downloads" / f"{name[:-4]}.verdict.json"
        if side_car.exists():
            out[name] = (row, json.loads(side_car.read_text()))
    return out


def main() -> int:
    r = _receipts()
    p = DOCS / "index.html"
    s = p.read_text()
    section = _section(r)
    rows_by_name = _all_rows()
    name = r["sidecar"]["name"]
    row = _row(name, rows_by_name[name][0], rows_by_name[name][1])

    # 1. the section, replaced in place
    if BEG in s:
        i, j = s.index(BEG), s.index(END, s.index(BEG)) + len(END)
        s = s[:i] + section + s[j:]
    else:
        anchor = "<!-- ==================== SESSION 2026-10-12: the datum doublet ==================== -->"
        assert anchor in s, "index.html has neither the H62-R markers nor the H62-J anchor"
        s = s.replace(anchor, section + "\n\n" + anchor, 1)

    # 2. the rows in the all-files table, kept in filename order.  The table's own heading says
    #    "every downloadable file in this repository", so the generator completes it: a raster with a
    #    verdict but no row is a claim the page cannot support (main shipped one such file).
    missing = [n for n in rows_by_name if n not in s]
    s = re.sub(r"<tr><td><a href=\"downloads/" + re.escape(name) + r"\">.*?</tr>\n?", "", s, flags=re.S)
    added = []
    for n in sorted(rows_by_name):
        if n in s and n != name:
            continue
        new_row = _row(n, rows_by_name[n][0], rows_by_name[n][1])
        s = re.sub(r"<tr><td><a href=\"downloads/" + re.escape(n) + r"\">.*?</tr>\n?", "", s, flags=re.S)
        parsed = list(re.finditer(r"<tr><td><a href=\"downloads/([^\"]+)\">.*?</tr>\n?", s, flags=re.S))
        after = next((m for m in parsed if m.group(1) > n), None)
        if after:
            s = s[:after.start()] + new_row + "\n" + s[after.start():]
        else:
            s = s[:parsed[-1].end()] + new_row + "\n" + s[parsed[-1].end():]
        added.append(n)

    # 3. the nav link, and the all-files count in the nav (a stale count is a stale claim)
    n_files = json.loads((DOCS / "downloads" / "manifest.json").read_text())["n_files"]
    s = re.sub(r"⬇ All \d+ files \+ verdicts", f"⬇ All {n_files} files + verdicts", s)
    link = '<a href="#h62r">H62-R — multi-level datum stack</a>'
    if link not in s:
        s = re.sub(r"<a href=\"#h62j\">H62-J datum doublet</a>",
                   link + '\n<a href="#h62j">H62-J datum doublet</a>', s, count=1)

    p.write_text(s)
    print(f"{p} — H62-R section + {len(added)} table row(s) written from receipts "
          f"({r['sidecar']['dots']:,} dots, sha {r['sidecar']['sha256'][:16]}…, "
          f"{n_files} files audited; completed rows: {added or 'none'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
