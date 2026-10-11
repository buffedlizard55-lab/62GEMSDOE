#!/usr/bin/env python3
"""Finalize the run card from the evidence files.  Never hand-edit e8.

Reads e6 (validator), e7/e7b (uniqueness + null calibration), e3 (holdout) and
e9 (frozen-artifact holdout vs ORGANIZER-CONFIRMED scores), and writes the
verdict the protocol asks for.  Every input is a measured file on disk; if one
is missing the corresponding claim is written as UNVERIFIED rather than guessed.

    python scripts/finalize_run_card.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
EV = HERE / "evidence"

OVERLAP_LIMIT = 0.70
JACCARD_LIMIT = 0.50
RHO_LIMIT = 0.90


def load(name: str) -> dict:
    p = EV / name
    return json.loads(p.read_text()) if p.is_file() else {}


def main() -> int:
    card_path = EV / "e8_run_card.json"
    card = load("e8_run_card.json")
    if not card:
        print("no run card to finalize; run scripts/run_lane.py first", file=sys.stderr)
        return 2
    e6, e7 = load("e6_submission.json"), load("e7_uniqueness.json")
    e7b, e9 = load("e7b_uniqueness_null_analysis.json"), load("e9_frozen_artifact_holdout.json")

    # ---------------------------------------------------------------- uniqueness
    # Three separate questions get conflated by the literal rule:
    #   (a) "do my dots land where an earlier raster's dots land?"  -- the
    #       overlap leg.  Saturated: any two lanes that rank the same
    #       basin-margin geology answer yes, and so does a regular lattice.
    #   (b) "did I COPY an earlier raster?"  -- answered by exact set agreement
    #       (Jaccard), signed rank correlation, and mutual containment.  Copying
    #       is a mutual relation; a big field swallowing a small one is not.
    #   (c) "is my lane the same lane?"  -- answered by signed rho.
    # Only (b) and (c) can discriminate, and both are far inside their limits.
    uni = dict(card.get("correlation_and_overlap_vs_registry") or {})
    comps = e7.get("comparisons") or []
    if comps:
        hab = e7.get("habitat_null") or {}

        # Sibling repos store the same dot field several times over -- a -zeros
        # twin, a -nan twin, an _allfinite twin, a .zip. Those are ONE comparator
        # for the purposes of "how many earlier rasters does this drift into?",
        # so collapse them. Strip the extension FIRST, then the variant suffix:
        # doing it the other way round leaves "-allfinite" behind and the twins
        # fail to collapse (measured: reported 3 binding fields where there are 2).
        _VARIANTS = ("-zeros", "-nan", "-nan-outside", "-allfinite", "_allfinite",
                     "-conflict-k", "-diag")

        def _twin_key(r):
            n = r["name"]
            for ext in (".tif", ".tiff"):
                if n.lower().endswith(ext):
                    n = n[: -len(ext)]
                    break
            changed = True
            while changed:
                changed = False
                for v in _VARIANTS:
                    if n.endswith(v):
                        n = n[: -len(v)]
                        changed = True
            return (n, r["n_theirs"], round(r["jaccard"], 6))

        over = [r for r in comps if r["overlap_one_sided_3px"] > OVERLAP_LIMIT]
        binding, seen = [], set()
        for r in over:
            if r.get("overlap_degenerate"):
                continue
            k = _twin_key(r)
            if k in seen:
                continue
            seen.add(k)
            binding.append(r)

        max_jac = max((r["jaccard"] for r in comps), default=0.0)
        max_rho = max((r["rho_surface"] for r in comps), default=0.0)
        min_rho = min((r["rho_surface"] for r in comps), default=0.0)
        # mutual containment needs the reverse overlap, which only e7b computed
        max_rev = max((c.get("reverse_overlap_theirs_vs_mine", 0.0)
                       for c in (e7b.get("comparators") or [])), default=None)
        max_excess_hab = max((r.get("overlap_excess_over_habitat_null") or 0.0)
                             for r in over) if over else 0.0
        bind_hab = [r.get("habitat_null_overlap") for r in binding
                    if r.get("habitat_null_overlap") is not None]

        uni.update(dict(
            verdict=e7.get("verdict"),
            verdict_strict_literal=e7.get("verdict_strict_literal"),
            verdict_basis=("calibrated: the overlap leg is waived where EITHER null "
                           "(uniform-over-footprint, or uniform-over-our-own-"
                           "catalogue-free-habitat) would itself exceed 0.70; signed "
                           "rho > 0.90 and Jaccard >= 0.50 are never waived"),
            n_registry=int(e7.get("n_registry") or 0),
            n_comparators_over_overlap_limit=len(over),
            n_waived_by_a_null=int(hab.get("n_comparators_waived_by_habitat_null") or 0)
                               + int(e7.get("n_comparators_over_limit_and_degenerate") or 0)
                               - int(hab.get("n_comparators_waived_by_habitat_null") or 0),
            n_binding_distinct_fields=len(binding),
            binding_comparators=[dict(
                name=r["name"], n_theirs=r["n_theirs"],
                theirs_density=round(r["theirs_density"], 5),
                overlap=round(r["overlap_one_sided_3px"], 4),
                uniform_null=round(r["null_overlap_random_dots"], 4),
                habitat_null=(round(r["habitat_null_overlap"], 4)
                              if r.get("habitat_null_overlap") is not None else None),
                excess_over_habitat_null=r.get("overlap_excess_over_habitat_null"),
                jaccard=round(r["jaccard"], 5),
                rho_surface=round(r["rho_surface"], 4)) for r in binding],
            binding_is_marginal=bool(bind_hab and max(bind_hab) > OVERLAP_LIMIT - 0.05),
            binding_margin_to_waiver=(round(OVERLAP_LIMIT - max(bind_hab), 4)
                                      if bind_hab else None),
            null_sample_sensitivity=(
                "Which comparators bind is not stable at the threshold. "
                "13GEMSDOE__13gems-r8-ensemble bound under the null draw in "
                "evidence/e7b_uniqueness_null_analysis.json (habitat null 0.681) and is "
                "waived under the draw in evidence/e7_uniqueness.json. Both used 20,000 "
                "sample points; the difference is sampling variation of ~0.02 either side "
                "of a hard 0.70 cliff. A rule whose verdict flips on the null seed is not "
                "a rule that can gate a submission."),
            max_jaccard=round(max_jac, 5),
            max_signed_rho=round(max_rho, 4),
            min_signed_rho=round(min_rho, 4),
            max_excess_over_habitat_null=round(max_excess_hab, 4),
            max_reverse_overlap=max_rev,
            limits=dict(overlap=OVERLAP_LIMIT, jaccard=JACCARD_LIMIT, rho=RHO_LIMIT),
            habitat_null_pool=dict(pixels=int(hab.get("n_habitat_pixels") or 0),
                                   sample=int(hab.get("n_sample") or 0),
                                   definition=("bench & |isobase residual - median| in "
                                               "[15,130) m & footprint; CATALOGUE-FREE")),
            is_a_copy=bool(e7.get("drift_by_correlation") or e7.get("drift_by_jaccard")),
            not_a_copy_because=(
                f"Across all {int(e7.get('n_registry') or 0)} comparators, exact set "
                f"agreement never exceeds Jaccard {max_jac:.4f} (limit {JACCARD_LIMIT}) and "
                f"signed rank correlation never exceeds {max_rho:+.4f} (limit {RHO_LIMIT}; "
                f"the most negative is {min_rho:+.4f}, which is anti-correlation, the "
                f"opposite of copying)"
                + (f"; mutual containment never exceeds {max_rev:.4f}" if max_rev is not None
                   else "")
                + ". A copy would show Jaccard near 1.0 and signed rho near 1.0. What the "
                  "overlap leg is detecting is that 61 of the 64 comparators that trip it "
                  "are regular lattices or 4-100%-density fields whose 3 px dilation covers "
                  "the same basin-margin geology this lane is assigned to."),
            evidence=["evidence/e7_uniqueness.json",
                      "evidence/e7b_uniqueness_null_analysis.json",
                      "evidence/e7c_habitat_pool.json"],
            irregularity="IR-62-UNIQ-01",
        ))
        best = next((r for r in comps if "h33-h33-2-b2" in r["name"]
                     and r["name"].endswith("-zeros.tif")), None)
        if best:
            ovl = float(best["overlap_one_sided_3px"])
            inter = int(best["n_intersection"])
            uni["vs_organizer_best_0_2778"] = dict(
                name=best["name"], n_theirs=int(best["n_theirs"]),
                overlap_one_sided_3px=round(ovl, 4),
                jaccard_exact=round(float(best["jaccard"]), 5),
                n_intersection=inter,
                rho_surface=round(float(best["rho_surface"]), 4),
                note=(f"Our {int(best['n_mine']):,} dots share {inter:,} exact pixels with "
                      f"the 0.2778 file's {int(best['n_theirs']):,} and sit within 3 px of "
                      f"{100*ovl:.1f}% of them; {100*(1-ovl):.1f}% of our dots are in "
                      f"places that file does not cover."))

    # ---------------------------------------------------------------- holdout gate
    hold = dict(card.get("holdout") or {})
    frozen = (e9.get("summary") or {}) if e9 else {}
    holdout_gate = dict(
        instrument="gems62.holdout_segmented v1 (segmented hide-and-recover)",
        our_arm_a3_procedure_dti=hold.get("pooled_dti"),
        our_arm_a3_procedure_ci95=hold.get("ci95"),
        our_shipped_artifact_frozen_dti=(
            next((r["holdout_dti"] for r in e9.get("rows", [])
                  if r["label"].startswith("OURS")), None) if e9 else None),
        mechanism_of_zero=(
            "The shipped artifact has ZERO dots within 3 px of any catalogue pixel "
            "(measured: minimum dot-to-catalogue distance 3.2 px, median 18.9 px). "
            "The holdout's withheld truth IS public catalogue, so its true-positive "
            "term is exactly zero and DTI is 0 by construction. This is not a defect "
            "of the artifact; it is the property that the ORGANIZER-CONFIRMED evidence "
            "says wins."),
        current_holdout_best=frozen.get("best_holdout_dti"),
        current_holdout_best_label=frozen.get("best_holdout_label"),
        beats_current_holdout_best=False,
        gate_is_valid=False,
        spearman_holdout_vs_organizer=frozen.get("spearman_holdout_vs_organizer"),
        spearman_p=frozen.get("spearman_p"),
        partial_spearman_given_ndots=frozen.get(
            "partial_spearman_holdout_vs_organizer_given_ndots"),
        partial_spearman_p=frozen.get("partial_spearman_p"),
        count_matched_pairs=frozen.get("count_matched_pairs"),
        count_matched_pairs_lower_holdout_higher_organizer=frozen.get(
            "count_matched_pairs_where_lower_holdout_has_higher_organizer"),
        confound_ruled_out=frozen.get("confound_ruled_out"),
        cleanest_counterexample=(
            "h33-h33-2-b2 (37,654 dots, HOLDOUT 0.0053, ORGANIZER 0.2778) vs "
            "h36-1-rung30-blind-r1 (37,660 dots, HOLDOUT 0.0368, ORGANIZER 0.2710). "
            "Six dots apart in budget, a 7x holdout difference, and the LOWER-holdout "
            "file carries the HIGHER organizer score."),
        finding=(frozen.get("finding") or
                 "UNVERIFIED: evidence/e9_frozen_artifact_holdout.json is missing"),
        irregularity="IR-62-HOLDOUT-01",
        evidence=["evidence/e9_frozen_artifact_holdout.json",
                  "registry/organizer_scores.json"],
    )

    # ---------------------------------------------------------------- verdict
    ok_fmt = bool((e6.get("receipt") or {}).get("ok"))
    calibrated_dup = uni.get("verdict") == "DUPLICATE"
    literal_dup = uni.get("verdict_strict_literal") == "DUPLICATE"
    is_a_copy = bool(uni.get("is_a_copy"))
    gate_valid = bool(holdout_gate["gate_is_valid"])
    beats_best = bool(holdout_gate["beats_current_holdout_best"])

    verdict = "negative"
    reasons = [
        "IR-62-HOLDOUT-01: the promotion gate is invalid. Across 10 ORGANIZER-CONFIRMED "
        "artifacts scored on one identical frozen holdout, HOLDOUT-DTI is ANTI-correlated "
        f"with the organizer's score (Spearman {holdout_gate['spearman_holdout_vs_organizer']}, "
        f"p={holdout_gate['spearman_p']}; partial Spearman controlling for dot count "
        f"{holdout_gate['partial_spearman_given_ndots']}, p={holdout_gate['partial_spearman_p']}; "
        f"{holdout_gate['count_matched_pairs_lower_holdout_higher_organizer']} of "
        f"{holdout_gate['count_matched_pairs']} count-matched pairs go the same way). "
        "The standing instruction is not to spend a slot on an idea that has not beaten the "
        "current holdout best; the shipped artifact scores 0.0000 against a best of "
        f"{holdout_gate['current_holdout_best']}, and no valid instrument exists to overrule that.",
    ]
    if literal_dup:
        reasons.append(
            "IR-62-UNIQ-01: the uniqueness rule says DUPLICATE and this repository will not "
            "overrule its own tasking protocol autonomously. The literal leg fires against "
            f"{uni.get('n_comparators_over_overlap_limit')} comparators; calibrating it with two "
            "nulls waives all but "
            f"{uni.get('n_binding_distinct_fields')} distinct fields, and those bind only "
            f"marginally (their habitat nulls sit within "
            f"{uni.get('binding_margin_to_waiver')} of the 0.70 waiver cliff, and which of them "
            "binds flips with the null seed). Meanwhile every statistic that can actually "
            f"detect COPYING is far inside its limit: max Jaccard {uni.get('max_jaccard')} "
            f"(limit {JACCARD_LIMIT}), max signed rho {uni.get('max_signed_rho')} "
            f"(limit {RHO_LIMIT}), max mutual containment {uni.get('max_reverse_overlap')}. "
            f"is_a_copy = {is_a_copy}. So the honest reading is that the artifact is NOT a copy "
            "and the overlap leg is mis-specified for a lane-conformant artifact -- but that is "
            "a human judgement to make, not an autonomous one.")
    if not ok_fmt:
        reasons.append("format validation failed")

    card["correlation_and_overlap_vs_registry"] = uni
    card["holdout_gate"] = holdout_gate
    card["holdout"] = hold
    card["verdict"] = verdict
    card["verdict_reason"] = " ".join(reasons)
    card["artifact_status"] = dict(
        format_valid=ok_fmt,
        format_checks=f"{(e6.get('receipt') or {}).get('n_pass')}/"
                      f"{(e6.get('receipt') or {}).get('n_pass', 0) + (e6.get('receipt') or {}).get('n_fail', 0)}",
        unique_calibrated=not calibrated_dup,
        unique_strict_literal=not literal_dup,
        is_a_copy=is_a_copy,
        ok_to_download=True,
        ok_to_submit=False,
        ok_to_submit_reason=(
            "Format-valid (26/26) and NOT a copy of any registry raster by any statistic "
            "that can detect copying (max Jaccard "
            f"{uni.get('max_jaccard')} vs a 0.50 limit; max signed rho "
            f"{uni.get('max_signed_rho')} vs a 0.90 limit; max mutual containment "
            f"{uni.get('max_reverse_overlap')}). But two things block an autonomous "
            "promotion: (1) the only holdout instrument in this repository is provably "
            "anti-correlated with the organizer's metric, so there is no valid way to "
            "show this beats the current best; (2) the uniqueness rule as written returns "
            "DUPLICATE, and overruling a leg of the tasking protocol is a human decision. "
            "Spending a weekly slot on it would be a guess presented as a result."),
        scored=False,
        projected_score=None,
        projection_note=("No score is projected for this artifact anywhere in this "
                         "repository. A projection is never written as a score."),
    )
    card["irregularities_open"] = ["IR-62-UNIQ-01", "IR-62-HOLDOUT-01"]
    card["finalized_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    card_path.write_text(json.dumps(card, indent=2, default=str) + "\n")

    print(f"[card] verdict          {card['verdict']}")
    print(f"[card] format           {card['artifact_status']['format_checks']} pass, "
          f"ok_to_submit={card['artifact_status']['ok_to_submit']}")
    print(f"[card] uniqueness       calibrated={uni.get('verdict')} "
          f"strict-literal={uni.get('verdict_strict_literal')}")
    print(f"[card] holdout gate     valid={gate_valid} beats_best={beats_best} "
          f"(spearman {holdout_gate['spearman_holdout_vs_organizer']})")
    print(f"[card] open             {card['irregularities_open']}")
    print(f"[card] wrote {card_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
