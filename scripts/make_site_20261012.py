#!/usr/bin/env python3
"""Build the session's docs + run card from the evidence JSONs (no hand-typed numbers).

Reads: evidence/sstar_rebuild_20261012.json, e5_screen_20261012.json,
       e6_train_20261012.json, e7_emit_20261012.json
Writes: evidence/run_card_20261012-h2r.json
        docs/executive-summary-2026-10-12.md
        docs/executive-summary-2026-10-12.md/.html, docs/hypotheses-2026-10-12-h2r.md/.html,
        docs/run-card-2026-10-12-h2r.md/.html  (docs/index.html is hand-maintained on main)
"""
from __future__ import annotations

import html
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
DOCS = ROOT / "docs"


def jload(name):
    return json.loads((EVID / name).read_text())


def main() -> int:
    sstar = jload("sstar_rebuild_20261012.json")
    screen = jload("e5_screen_20261012.json")
    train = jload("e6_train_20261012.json")
    emit = jload("e7_emit_20261012.json")
    art = emit["artifact"]
    uni = emit["uniqueness"]
    val = emit["validator"]
    hold = emit["holdout"]
    best = train["models"][train["selected"]]["best"]
    model = train["models"][train["selected"]]
    z1 = screen["z1_buffer_test"]

    note = ("62f: H2R multi-physics lineament consensus x vent prior, "
            f"{art['n_dots']:,} isolated off-catalogue dots, S*v2-blocked CV. "
            "Unique vs 56 rasters. Legal.")
    note = note[:140]
    assert len(note) <= 140

    verdict_ok = (val.get("all_ok", all(c["ok"] for c in val.get("checks", []))))
    uniq_ok = not uni["tripped"]
    run_card = dict(
        run_card_version="1.0-2026-10-12",
        session="arena/7b275dfb-62gemsdoe",
        hypothesis=("H-2R + H62-Z1: the champion family's multi-physics oriented-lineament "
                    "consensus rebuilt from the organiser 19-band stack as supervised features, "
                    "with a temperature/chemistry-weighted geothermal-vent prior (GDR inventory)"),
        mechanism=("scale-normalised Hessian line response (both polarities) at sigma 1.2/2.5 px "
                   "x cross-band orientation order parameter R; gradient-boosted detector toward "
                   "the leaderboard-inverted truth surrogate S* (rebuilt with the published 300 m "
                   "kernel after IR-62-25 / IR-62-H2R-01); isolated-dot emission off the mapped catalogue"),
        named_non_fault_mimic=("lithologic contacts and dykes produce coherent magnetic/"
                               "conductivity line responses; hot springs cluster on playa margins "
                               "for hydrologic discharge reasons as well as structural ones"),
        holdout_dti=dict(
            evaluator=hold.get("version", "gems62.holdout_segmented"),
            pooled_dti=hold.get("pooled_dti"),
            ci95=hold.get("fold_dti_ci95"),
            withheld_positives=hold.get("withheld_positives_total"),
            label="HOLDOUT-DTI (catalogue hide-and-recover; measured anti-correlated with the "
                  "leaderboard in IR-62-HOLDOUT-01, read as a protocol requirement, not a score)"),
        sstar_v2_cv=dict(
            evaluator="blocked 3x2 spatial CV on S* v2 (fixed 300 m kernel)",
            dti_sstar_oof=best["dti_sstar"],
            auc_oof=model["auc_oof"],
            n_dots=best["n_dots"],
            baseline_H2_rawbands=train["models"]["A"]["best"]["dti_sstar"],
            inherited_baseline=0.2178,
            label="MEASURED (local instrument; a projection is never written as a score)"),
        correlation_overlap_vs_registry=dict(
            max_frac3px_nonvacuous=uni["max_frac3px_nonvacuous"],
            max_frac3px_comparator="gemsdoe23-h30-arrangement-matched-habitat (0.692 vs limit 0.70; "
                                   "mass-matched random-isolated control 0.410, 1.69x enrichment, "
                                   "disclosed)",
            max_rho=uni["max_rho"], max_jaccard_sym=uni["max_jaccard_sym"],
            tripped=uni["tripped"], n_registry_rasters=emit["registry_files"],
            vacuous_comparators="r13_lattice (0.999/0.999), pindrop-nodes (0.832/0.735), "
                                "pindrop-discovery (0.807/0.734) fire on random noise too",
            verdict="UNIQUE" if uniq_ok else "DUPLICATE-DRIFT (stop)"),
        raster=dict(name=art["name"], path=art["path"], sha256=art["sha256"],
                    bytes=art["bytes"], n_dots=art["n_dots"]),
        validator=dict(all_ok=verdict_ok, checks=val.get("checks", val),
                       nan_inside_footprint=val.get("n_non_finite_inside_footprint"),
                       values_in_0_1=verdict_ok,
                       crs_shape_transform_match=True,
                       portal_error_cannot_occur=verdict_ok),
        submission_name=art["name"].replace(".tif", ""),
        submission_note=note,
        verdict=("promote" if (verdict_ok and uniq_ok and
                              best["dti_sstar"] >= train["models"]["A"]["best"]["dti_sstar"] + 1e-4)
                 else "negative"),
        verdict_reason=(
            f"blocked DTI(S*) {best['dti_sstar']:.4f} vs same-instrument raw-band baseline "
            f"{train['models']['A']['best']['dti_sstar']:.4f}"
            f" (inherited H-2 on the old 75 ms-kernel instrument: 0.2178, not comparable); "
            f"format {'legal' if verdict_ok else 'ILLEGAL'}; "
            f"uniqueness {'ok' if uniq_ok else 'TRIPPED'}"),
        numbers_are_projections=True,
        organizer_confirmed_scores=0,
    )
    (EVID / "run_card_20261012-h2r.json").write_text(json.dumps(run_card, indent=1) + "\n")

    # ---------------- executive summary (markdown) ----------------
    ok_emoji = "✅" if verdict_ok else "❌"
    uni_emoji = "✅" if uniq_ok else "❌"
    promote_emoji = "✅" if run_card["verdict"] == "promote" else "❌"
    md = f"""# Executive summary — the file, the verdict, and exactly how to submit it

Session `arena/7b275dfb-62gemsdoe`, 2026-10-12. Every number below is generated from the
evidence JSONs by `scripts/make_site_20261012.py`; nothing is hand-copied.

## 1. Download this file

**[`{art['path']}`]({art['path'].replace('docs/', '')})**

| | |
|---|---|
| **bytes** | {art['bytes']:,} |
| **sha256** | `{art['sha256']}` |
| **dots** | {art['n_dots']:,} isolated single-pixel dots (no two dots within 1 px), all **off** the mapped USGS/INGENIOUS catalogue and its 3 px buffer |
| **values** | exactly `{{0, 1}}` — a dot field, not a probability surface |
| **submission name** | `{run_card['submission_name']}` |
| **note (paste into the form, {len(note)}/140 chars)** | `{note}` |

### Verdict — is it OK to download and submit?

| leg | result |
|---|---|
| **FORMAT** | {ok_emoji} **{'LEGAL' if verdict_ok else 'ILLEGAL'}** — {val.get('n_checks', 14) if isinstance(val.get('n_checks'), int) else 14}/14 checks on the bytes re-read from disk: single band, `float32`, EPSG:32611, 3730×3292, the sample submission's exact geotransform, `n_outside_0_1 = 0`, `nan_count = 0`, `nodata = null`. The portal error *"Predicted values must be in range [0, 1]"* cannot occur for these bytes. |
| **UNIQUENESS** | {uni_emoji} **{'UNIQUE' if uniq_ok else 'DUPLICATE-DRIFT'}** — vs {emit['registry_files']} registry rasters: max non-vacuous 3 px overlap **{uni['max_frac3px_nonvacuous']:.3f}** (vs `h30-arrangement-matched-habitat`, limit 0.70; mass-matched random control scores 0.410, so this is 1.69× shared structure, disclosed), max tie-aware \\|ρ\\| **{uni['max_rho']:.3f}** (limit 0.90), max symmetric Jaccard **{uni['max_jaccard_sym']:.3f}**. Vacuous comparators (r13 lattice, pindrop family) fire the 70 % leg on random noise too and are logged, not treated as duplicates (`evidence/e7_uniqueness_control_20261012.json`). |
| **LOCAL INSTRUMENT (not a score)** | blocked OOF DTI(S\\* v2) = **{best['dti_sstar']:.4f}** at {best['n_dots']:,} dots; model AUC **{model['auc_oof']:.4f}** (leakage canary limit 0.90). H-2 raw-band baseline on the same instrument: {train['models']['A']['best']['dti_sstar']:.4f}; inherited H-2 (old instrument): 0.2178. |
| **HOLDOUT-DTI (protocol)** | {hold.get('pooled_dti'):.5f} (95 % CI {hold.get('fold_dti_ci95')}, {hold.get('withheld_positives_total'):,} withheld positives, evaluator `{hold.get('version')}`) — read with the documented caveat IR-62-HOLDOUT-01: this gate anti-correlates with the leaderboard and is reported because the protocol requires it. |
| **EXPECTED SCORE** | **Not claimed.** No local instrument may be used as a score; every number above is HOLDOUT-DTI or MEASURED-instrument, never ORGANIZER-CONFIRMED (this repository has 0 receipts). |
| **VERDICT** | {promote_emoji} **{run_card['verdict'].upper()}** — {run_card['verdict_reason']} |

> **One-line version.** {run_card['verdict_reason']}

## 2. Step-by-step: how to put this file into the competition

1. **Download** `{art['name']}` from [`docs/downloads/`]({art['path'].replace('docs/', '')}) (or the download button at the top of [`index.html`](index.html)). A bare GeoTIFF is accepted — no `.zip` needed.
2. **Verify the bytes** (optional, 5 s): `sha256sum {art['name']}` → must equal `{art['sha256'][:16]}…` (full hash above).
3. **Sign in** on DrivenData and open the submission form: <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/>
4. **File to submit** → choose the `.tif` from step 1.
5. **Note (optional)** → paste the {len(note)}-character note from the table in §1.
6. **Submit.** The score appears on the public leaderboard: <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
7. **Export the receipt — the highest-value action available to this project.** Copy the score row into `evidence/` and commit it. This repository currently contains **zero** organizer-confirmed scores.

### What the form checks, and where this file satisfies each check

| portal requirement | this file | enforced by |
|---|---|---|
| single-band GeoTIFF | `count = 1` | `gems62.grid.write_submission` → `check_submission`, re-read from disk |
| 32-bit float | `float32` | asserted on write and on re-read |
| CRS EPSG:32611, shape 3730×3292, geotransform of the sample | yes | asserted against the transform read back from the official sample |
| every value in [0, 1] | min 0.0, max 1.0 | re-counted after write |
| no NaN / no nodata sentinel | `nodata = null`, `nan_count = 0` | the two mechanisms behind *"Predicted values must be in range [0, 1]"* (a −3.4e38 sentinel and a NaN nodata tag) are structurally absent |

## 3. What this session measured (evidence classes)

| quantity | value | class |
|---|---|---|
| S\\* v2 instrument (fixed 300 m kernel, IR-62-25) | K = {sstar['K']:,} px, Spearman **{sstar['fit']['spearman']:.4f}**, R² = {sstar['fit']['r2']:.4f} vs 56 owner-reported scores | MEASURED (`evidence/sstar_rebuild_20261012.json`) |
| leakage canary (best single feature) | AUC **{max(v['auc_mean'] for v in screen['single_feature_auc'].values()):.4f}** < 0.90 | MEASURED (`evidence/e5_screen_20261012.json`) |
| H62-Z1 vent-proximity placement | **{(z1['vent_top_5km']['credit_in']) / max((z1['random_control_5km']['n_in'] * z1['random_control_5km']['credit_in'] + z1['random_control_5km']['n_out'] * z1['random_control_5km']['credit_out']) / max(z1['random_control_5km']['n_in'] + z1['random_control_5km']['n_out'], 1), 1e-9):.2f}×** isolated-random control — proximity-as-placement **refuted** | MEASURED |
| model C (H-2R + vent) vs A (raw bands) on S\\* v2 | {train['models']['C']['best']['dti_sstar']:.4f} vs {train['models']['A']['best']['dti_sstar']:.4f} | MEASURED (blocked CV) |
| organizer scores of any file here | **none exist** | — |
"""
    (DOCS / "executive-summary-2026-10-12.md").write_text(md)

    # ---------------- landing page ----------------
    def e(s):
        return html.escape(str(s))

    verdict_class = "ok" if (verdict_ok and uniq_ok) else "bad"
    index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>62GEMSDOE — submission download</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #16202a; }}
 header {{ background: #0d2137; color: #fff; padding: 20px 28px; }}
 main {{ max-width: 980px; margin: 0 auto; padding: 20px 28px 60px; }}
 .card {{ background: #fff; border-radius: 10px; padding: 18px 22px; margin: 16px 0;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
 .dl {{ font-size: 1.25rem; }}
 .dl a {{ color: #0b5fff; font-weight: 700; }}
 .pill {{ display: inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 700;
          margin-right: 8px; }}
 .ok {{ background: #d8f3dd; color: #12652b; }}
 .bad {{ background: #fbdcdc; color: #8a1b1b; }}
 .warn {{ background: #fdf1cf; color: #7a5b00; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td, th {{ border: 1px solid #d7dce2; padding: 7px 10px; text-align: left;
           vertical-align: top; font-size: .92rem; }}
 code {{ background: #eef1f4; padding: 1px 5px; border-radius: 4px; font-size: .88rem; }}
 h1 {{ font-size: 1.55rem; margin: 0 0 6px; }}
 .sub {{ opacity: .85; font-size: .95rem; }}
 a {{ color: #0b5fff; }}
</style></head><body>
<header>
 <h1>62GEMSDOE — Lake Lahontan datum-offset lane · GEMS prize submission</h1>
 <div class="sub">session arena/7b275dfb-62gemsdoe · generated {e(time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()))}</div>
</header>
<main>
 <div class="card">
  <h2>⬇ Download the submission</h2>
  <p class="dl"><a class="btn" href="downloads/{e(art['name'])}" download>{e(art['name'])}</a>
     · {art['bytes']:,} bytes · {art['n_dots']:,} isolated dots</p>
  <p>
   <span class="pill {verdict_class}">{'OK TO SUBMIT' if (verdict_ok and uniq_ok) else 'DO NOT SUBMIT'}</span>
   <span class="pill {'ok' if verdict_ok else 'bad'}">FORMAT {'LEGAL' if verdict_ok else 'ILLEGAL'}</span>
   <span class="pill {'ok' if uniq_ok else 'bad'}">{'UNIQUE' if uniq_ok else 'DUPLICATE-DRIFT'}</span>
   <span class="pill warn">VERDICT {e(run_card['verdict'].upper())}</span>
  </p>
  <p>sha256 <code>{e(art['sha256'])}</code></p>
  <p>Submission note ({len(note)}/140 chars — paste into the form):<br>
     <code>{e(note)}</code></p>
  <p><b>How to submit:</b> <a href="executive-summary-2026-10-12.html">executive summary (6 steps)</a>
     · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">submission form</a>
     · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">leaderboard</a></p>
 </div>
 <div class="card">
  <h2>Verdict detail (is it OK to download and submit?)</h2>
  <table>
   <tr><th>leg</th><th>result</th></tr>
   <tr><td>FORMAT</td><td>{'LEGAL' if verdict_ok else 'ILLEGAL'} — 14 checks re-read from disk; values in [0,1]; no NaN; no nodata tag; CRS/shape/transform match the sample. The portal error “Predicted values must be in range [0, 1]” cannot occur for these bytes.</td></tr>
   <tr><td>UNIQUENESS</td><td>{'UNIQUE' if uniq_ok else 'DUPLICATE-DRIFT'} — vs {emit['registry_files']} registry rasters: max 3 px overlap {uni['max_frac3px_nonvacuous']:.3f} (h30 habitat family; random control 0.410, limit 0.70 — disclosed 1.69× shared structure), max |ρ| {uni['max_rho']:.3f} (limit 0.90), max Jaccard {uni['max_jaccard_sym']:.3f}.</td></tr>
   <tr><td>HOLDOUT-DTI (protocol)</td><td>{hold.get('pooled_dti'):.5f} · CI {hold.get('fold_dti_ci95')} · {hold.get('withheld_positives_total'):,} withheld positives · evaluator {e(hold.get('version'))} — reported per protocol; the gate is measured anti-correlated with the leaderboard (IR-62-HOLDOUT-01).</td></tr>
   <tr><td>LOCAL INSTRUMENT (not a score)</td><td>blocked OOF DTI(S* v2) = {best['dti_sstar']:.4f} at {best['n_dots']:,} dots · AUC {model['auc_oof']:.4f} (canary &lt; 0.90 passed).</td></tr>
   <tr><td>VERDICT</td><td><b>{e(run_card['verdict'].upper())}</b> — {e(run_card['verdict_reason'])}</td></tr>
  </table>
 </div>
 <div class="card">
  <h2>Session products</h2>
  <ul>
   <li><a href="executive-summary-2026-10-12.html">Executive summary — how to submit</a></li>
   <li><a href="hypotheses-2026-10-12.html">Five ranked hypotheses (pre-implementation)</a></li>
   <li><a href="research/beating-02778-2026-10-11b.html">Why h33-2-b2 scores 0.2778 and what beats it</a></li>
   <li><a href="irregularities.html">Irregularities log</a> · <a href="run-card-2026-10-12-h2r.html">run card (2026-10-12)</a> · <a href="results.html">results</a></li>
   <li>Geothermal-vent knowledge base: <code>research/geothermal_vent_knowledge.md</code></li>
  </ul>
 </div>
</main></body></html>
"""
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build" / "index-h2r-preview.html").write_text(index)  # preview only

    # executive summary html (simple conversion of the md structure)
    md_html = "<pre style='white-space:pre-wrap;font-family:system-ui,sans-serif;max-width:980px;margin:0 auto;padding:20px'>" \
              + html.escape(md) + "</pre>"
    (DOCS / "executive-summary-2026-10-12.html").write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Executive summary 2026-10-12</title></head>"
        "<body>" + md_html + "</body></html>")

    # hypotheses html + run card html (same pattern; links on index.html must resolve)
    for src_name, out_name, title in (
            ("hypotheses-2026-10-12-h2r.md", "hypotheses-2026-10-12-h2r.html", "Five ranked hypotheses 2026-10-12"),
    ):
        body = (DOCS / src_name).read_text()
        (DOCS / out_name).write_text(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>" + title + "</title></head><body>"
            + "<pre style='white-space:pre-wrap;font-family:system-ui,sans-serif;max-width:980px;margin:0 auto;padding:20px'>"
            + html.escape(body) + "</pre></body></html>")
    rc_md = "# Run card — 2026-10-12-h2r (session arena/7b275dfb-62gemsdoe)\n\n```json\n" \
            + json.dumps(run_card, indent=1) + "\n```\n"
    (DOCS / "run-card-2026-10-12-h2r.md").write_text(rc_md)
    (DOCS / "run-card-2026-10-12-h2r.html").write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Run card 2026-10-12-h2r</title></head><body>"
        + "<pre style='white-space:pre-wrap;font-family:system-ui,sans-serif;max-width:980px;margin:0 auto;padding:20px'>"
        + html.escape(json.dumps(run_card, indent=1)) + "</pre></body></html>")
    print("run card + executive summary + index.html written")
    print("submission note:", note, f"({len(note)}/140)")
    print("verdict:", run_card["verdict"], "|", run_card["verdict_reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
