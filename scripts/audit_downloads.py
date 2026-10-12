#!/usr/bin/env python3
"""Audit every downloadable raster in this repository and emit the manifest the site renders.

Why this exists
---------------
The standing brief requires that it be *obvious* whether a file on the site is OK to download and
submit, and that the download be one click away.  A promise like that cannot be hand-maintained:
a page that says "no NaN, values in [0, 1]" about bytes regenerated an hour later is worse than no
page at all.  So every claim about a shipped raster is recomputed **from the bytes on disk** here,
and `tests/test_download_manifest.py` fails when the committed manifest disagrees with reality or
when a page links a file that has no verdict.

Two validators run on every file, because they check different things:

* ``gems62.grid.check_submission`` -- the portal-contract fields whose violation produced the
  error "Predicted values must be in range [0, 1]": float32 nodata sentinels and NaN nodata tags;
* ``gems62.validate.validate_submission`` -- the published submission contract: single band,
  CRS/shape/geotransform, no NaN inside the footprint, values in [0, 1], consistent outside
  encoding.

Plus two facts the portal will not tell you but the metric will: how many dots land on the public
catalogue (dead mass -- those pixels are masked out of the organiser's truth) and whether any dot
sits outside the survey footprint.

Usage
    python3 scripts/audit_downloads.py [--write] [--root .]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid as G  # noqa: E402
from gems62 import validate as V  # noqa: E402

# Checks that are THIS LANE'S convention, stricter than anything the portal has stated.
# The reference block below proves it: the organiser's own `sample_submission.tif` carries
# nodata=NaN and 7,111,787 NaN pixels outside the footprint and passes the published contract.
# A file that fails only a STRICT check is legal for submission; it is our own rule that it broke.
STRICT_CHECKS = ("no_nodata_tag", "no_nan_anywhere")

PAGES = ("docs/index.html", "docs/executive-summary.html", "docs/executive-summary-v2.html",
         "docs/results.html", "docs/run-card.html")
CHECK_NAMES = ("single_band", "dtype_float32", "crs", "shape", "transform", "pixel_100m",
               "no_nodata_tag", "no_nan_inside_footprint", "no_nan_anywhere", "values_in_0_1",
               "no_mass_outside_footprint", "nonempty", "contract_validator_passes",
               "no_dead_mass_on_catalogue")


def jsonable(o):
    """NaN/Infinity are not JSON; a manifest a browser cannot parse is not evidence."""
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


def find_rasters(root: pathlib.Path) -> list[pathlib.Path]:
    out: set[pathlib.Path] = set()
    for pat in ("docs/downloads/*.tif", "*/docs/downloads/*.tif"):
        out |= {p for p in root.glob(pat) if p.is_file()}
    return sorted(out, key=lambda p: str(p.relative_to(root)))


def linked_rasters(root: pathlib.Path) -> dict[str, list[str]]:
    """Every `downloads/*.tif` href mentioned on the public pages -> the pages that link it."""
    hits: dict[str, list[str]] = {}
    for page in PAGES:
        f = root / page
        if not f.exists():
            continue
        for m in re.finditer(r'href="([^"]*downloads/[^"]+\.tif)"', f.read_text(errors="ignore")):
            hits.setdefault(m.group(1).split("/")[-1], []).append(page)
    return hits


CLAIM_KEYS = ("verdict", "ok_to_submit", "note", "submission_name", "submission_note",
              "organizer_score", "organizer_score_note", "expected_value_label", "artifact_of",
              "evidence")


def audit_file(path: pathlib.Path, root: pathlib.Path, footprint: np.ndarray,
               catalogue: np.ndarray, claim: dict | None = None,
               write_sidecar: bool = False) -> dict:
    rel = path.relative_to(root).as_posix()
    row: dict = {"path": rel, "bytes": path.stat().st_size}
    try:
        rec = G.check_submission(path)
        rep = V.validate_submission(path, footprint)
    except Exception as exc:                                    # noqa: BLE001
        row.update(status="UNREADABLE", error=f"{type(exc).__name__}: {exc}")
        return row
    with rasterio.open(path) as d:
        a = d.read(1)
    fin = np.isfinite(a)
    pos = (np.nan_to_num(a, nan=0.0) > 0)
    n_dots = int(pos.sum())
    # `values_in_0_1` is measured on FINITE pixels, because that is what a masked reader sees.
    # A file with NaN and no nodata tag therefore passes it and is still rejected by a portal
    # that takes min/max over the whole array -- which is why `portal_range_risk` exists: it
    # names the mechanism behind the "[0, 1]" message instead of hiding behind one boolean.
    finite_min = float(a[fin].min()) if fin.any() else None
    finite_max = float(a[fin].max()) if fin.any() else None
    n_nonfinite = int((~fin).sum())
    checks = {
        "single_band": rec["count"] == 1,
        "dtype_float32": rec["dtype"] == "float32",
        "crs": rec["crs_match"],
        "shape": rec["width_height_match"],
        "transform": rec["transform_match"],
        "pixel_100m": list(rec["res"]) == [100.0, -100.0] or all(abs(abs(v) - 100.0) < 1e-6
                                                                  for v in rec["res"]),
        "no_nodata_tag": rec["nodata"] is None,
        "no_nan_inside_footprint": rep.nan_inside_footprint == 0,
        "no_nan_anywhere": rec["nan_count"] == 0,
        "values_in_0_1": (rec["n_outside_0_1"] == 0 and finite_min is not None
                          and 0.0 <= finite_min and finite_max <= 1.0),
        "no_mass_outside_footprint": int((pos & ~footprint).sum()) == 0,
        "nonempty": n_dots > 0,
        "contract_validator_passes": bool(rep.passed),
        "no_dead_mass_on_catalogue": int((pos & catalogue).sum()) == 0,
    }
    fails = [k for k, v in checks.items() if not v]
    row_update_legal = all(checks.values())
    row["fails"] = fails
    row["fails_only_strict_conventions"] = bool(fails) and all(f in STRICT_CHECKS for f in fails)
    row.update(sha256=rec["sha256"], dots=n_dots, total_mass=rec["total_mass"],
               min=(rec["min"] if math.isfinite(rec["min"]) else "NaN"),
               max=(rec["max"] if math.isfinite(rec["max"]) else "NaN"),
               nodata=("NaN" if (rec["nodata"] is not None and not math.isfinite(rec["nodata"]))
                       else rec["nodata"]),
               finite_min=finite_min, finite_max=finite_max,
               nonfinite_pixels=n_nonfinite,
               nonfinite_inside_footprint=int((~fin & footprint).sum()),
               nan_count=rec["nan_count"], n_outside_0_1=rec["n_outside_0_1"],
               dots_inside_footprint=int((pos & footprint).sum()),
               dots_on_catalogue=int((pos & catalogue).sum()),
               unique_positive_values=rep.unique_positive_values[:6],
               checks=[dict(check=k, ok=bool(v)) for k, v in checks.items()],
               checks_passed=int(sum(bool(v) for v in checks.values())),
               checks_total=len(CHECK_NAMES),
               format_legal=row_update_legal)
    row["portal_range_risk"] = (
        "none" if n_nonfinite == 0 else
        ("high" if rec["nodata"] is None else "low"))
    if row["portal_range_risk"] == "high":
        row["portal_range_risk_note"] = (
            f"{n_nonfinite:,} non-finite pixels with no nodata tag: a reader that does not mask "
            "sees them as values, and NaN is not in [0, 1] - this is the mechanism behind the "
            "portal's 'Predicted values must be in range [0, 1]' rejection")
    if n_dots:
        row["dots_on_catalogue_frac"] = round(float((pos & catalogue).sum() / n_dots), 6)
    sidecar = path.parent / (re.sub(r"\.tif$", "", path.name) + ".verdict.json")
    if claim is not None and write_sidecar:
        # The sidecar is *generated*: the hand-authored claim (docs/downloads/verdicts.json)
        # joined with the facts measured from these bytes.  Nobody can therefore edit a
        # verdict without re-running the audit, and a verdict cannot outlive its bytes.
        gen = {k: claim[k] for k in CLAIM_KEYS if k in claim}
        gen.update(name=path.name, format_legal=bool(row["format_legal"]),
                   fails=row["fails"], portal_range_risk=row["portal_range_risk"],
                   nonfinite_pixels=row["nonfinite_pixels"],
                   sha256=row["sha256"], bytes=row["bytes"], dots=row["dots"],
                   checks_passed=row["checks_passed"], checks_total=row["checks_total"],
                   generated_by="scripts/audit_downloads.py --write")
        sidecar.write_text(json.dumps(gen, indent=1) + "\n")
    if sidecar.exists():
        v = json.loads(sidecar.read_text())
        for k in ("verdict", "ok_to_submit", "note", "submission_name", "submission_note",
                  "organizer_score", "expected_value_label", "artifact_of"):
            row[k] = v.get(k)
        row["sidecar"] = sidecar.relative_to(root).as_posix()
        pinned = bool(v.get("sha256") or v.get("bytes"))
        row["sidecar_matches_bytes"] = (None if not pinned else
                                       bool(v.get("sha256") == rec["sha256"]
                                            and v.get("bytes") == row["bytes"]))
        if row["sidecar_matches_bytes"] is False:
            row["sidecar_error"] = ("the verdict sidecar describes different bytes (sidecar "
                                    f"sha {str(v.get('sha256'))[:16]}, file sha {rec['sha256'][:16]})")
        note = v.get("submission_note")
        if isinstance(note, str) and len(note) > 140:
            row["sidecar_error"] = (row.get("sidecar_error") or "") + \
                f" submission note is {len(note)} chars (limit 140)"
    else:
        row["verdict"] = None
        row["sidecar"] = None
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", action="store_true", help="write docs/downloads/manifest.json")
    ap.add_argument("--manifest", default="docs/downloads/manifest.json")
    ap.add_argument("--verdicts", default="docs/downloads/verdicts.json",
                    help="hand-authored claims, keyed by file name; --write turns them into "
                         "the per-file .verdict.json sidecars the site table renders")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()

    cat_path, samp_path = root / "data/labels.tif", root / "data/sample_submission.tif"
    if not cat_path.exists() or not samp_path.exists():
        print("data/labels.tif and data/sample_submission.tif are required", file=sys.stderr)
        return 2
    catalogue, _ = G.load_catalogue(cat_path)
    with rasterio.open(samp_path) as d:
        footprint = np.isfinite(d.read(1))

    claims: dict[str, dict] = {}
    vfile = root / args.verdicts
    if vfile.exists():
        claims = json.loads(vfile.read_text())
        unknown = sorted(set(claims) - {p.name for p in find_rasters(root)})
        for name in unknown:
            print(f"note: {args.verdicts} claims about {name}, which is not a downloadable raster")
    rows = [audit_file(p, root, footprint, catalogue, claim=claims.get(p.name),
                       write_sidecar=bool(args.write))
            for p in find_rasters(root)]
    links = linked_rasters(root)
    problems: list[str] = []
    notes: list[str] = []
    by_name = {pathlib.Path(r["path"]).name: r for r in rows}
    for r in rows:
        if r.get("status") == "UNREADABLE":
            problems.append(f"{r['path']}: unreadable ({r.get('error')})")
            continue
        if not r["format_legal"]:
            bad = [c["check"] for c in r["checks"] if not c["ok"]]
            vv = (r.get("verdict") or "").lower()
            if r.get("verdict") and ("illegal" in vv or "probe" in vv) and not r.get("ok_to_submit"):
                notes.append(f"{r['path']}: deliberately NOT format-legal {bad}, labelled as a "
                             f"probe - {r['verdict']}")
            elif r["path"].startswith("docs/downloads/"):
                problems.append(f"{r['path']}: NOT format-legal -> {bad}, and the claim does not "
                                f"say so")
            else:
                notes.append(f"{r['path']}: NOT format-legal {bad}; it sits in a lane directory, "
                             f"is not linked from the site, and its owning lane has not labelled "
                             f"it - fix it there")
        if r.get("sidecar_error"):
            problems.append(f"{r['path']}: {r['sidecar_error']}")
        if r["path"].startswith("docs/downloads/") and r["verdict"] is None:
            problems.append(f"{r['path']}: shipped at the site root with no claim in "
                            f"{args.verdicts} (and so no verdict sidecar)")
        if r.get("ok_to_submit") and not r.get("format_legal"):
            problems.append(f"{r['path']}: claimed OK to submit while NOT format-legal")
        for ev in (r.get("evidence") or []):
            if not (root / ev).exists():
                problems.append(f"{r['path']}: its verdict cites {ev}, which does not exist")
    for name, pages in links.items():
        if name not in by_name:
            problems.append(f"{', '.join(sorted(set(pages)))}: links {name}, which does not exist")
        elif by_name[name].get("verdict") is None:
            problems.append(f"{name}: linked from the site but has no verdict sidecar")
        else:
            problems += cross_check_page(root, name, by_name[name], links[name])


    # The organiser's own example, measured the same way, so that our stricter rules are
    # visibly OURS: sample_submission.tif carries nodata=NaN and fails `no_nodata_tag`.
    ref_path = root / "data/sample_submission.tif"
    ref = None
    if ref_path.exists():
        r = audit_file(ref_path, root, footprint, catalogue)
        if r.get("status") != "UNREADABLE":
            ref = {k: r.get(k) for k in ("path", "bytes", "sha256", "dots", "total_mass",
                                         "min", "max", "finite_min", "finite_max", "nodata",
                                         "nan_count", "nonfinite_pixels", "dots_on_catalogue",
                                         "format_legal", "fails", "portal_range_risk",
                                         "fails_only_strict_conventions")}
            ref["checks"] = r["checks"]
            ref["interpretation"] = (
                "the file the organiser ships as the format example. It carries nodata=NaN, "
                "7.1M non-finite pixels outside the footprint, and its positive cells are exactly "
                "the public catalogue (60,988) - so `check_submission`'s all_finite/no_nodata_tag "
                "rules, which this lane's own files satisfy, are STRICTER than the example. A "
                "failure here is a failure of our convention, not of the published contract.")
    man = dict(
        generated_by="scripts/audit_downloads.py --write",
        rule=("this manifest is the source of truth for the site's download table; a page may not "
              "state a verdict, hash or byte count that disagrees with it"),
        grid=dict(shape=[int(footprint.shape[0]), int(footprint.shape[1])], crs=G.CRS,
                  pixel_m=G.PIXEL_M, footprint_cells=int(footprint.sum()),
                  catalogue_cells=int(catalogue.sum())),
        n_files=len(rows), files=rows, problems=problems, notes=notes,
        strict_checks=list(STRICT_CHECKS),
        strict_checks_meaning=("this lane's own convention; the reference example below shows the "
                              "organiser's shipped file does not satisfy them"),
        reference_example=ref)
    for r in rows:
        print(f"{'OK ' if r.get('format_legal') else 'BAD'} {r['path']:66s} "
              f"{r.get('bytes', 0):>9,} B dots={str(r.get('dots')):>7} "
              f"checks={r.get('checks_passed', '-')}/{r.get('checks_total', 14)} "
              f"verdict={r.get('verdict')}")
    if notes:
        print("\nNOTES (expected, labelled):")
        for n in notes:
            print("  -", n)
    if problems:
        print("\nPROBLEMS:")
        for one in problems:
            print("  -", one)
    else:
        print(f"\nall {len(rows)} downloadable rasters verified from their bytes; "
              f"every site link has a matching verdict.")
    if args.write:
        out = root / args.manifest
        out.parent.mkdir(parents=True, exist_ok=True)
        before = json.dumps(man)
        out.write_text(json.dumps(jsonable(man), indent=1) + "\n")
        if "NaN" in before:
            print("note: non-finite numbers in the audit were written as null "
                  "(NaN is not valid JSON)")
        print("wrote", out)
    return 1 if problems else 0


def cross_check_page(root: pathlib.Path, name: str, row: dict, pages: list[str]) -> list[str]:
    """The page may not print a hash or a byte count that disagrees with the bytes.

    Only what a page can plausibly state is checked, in the table row that **links** the file:
    any hex token of length >= 8 must be a prefix of the file's sha256, and any integer of at
    least four digits written next to a B/byte unit must equal the file's size.  A stale hash on
    the site is the exact failure this repo has been built to make impossible.

    IR-62-B-13: "mentions" used to be the test, and it is wrong. Prose in one file's verdict
    column legitimately names a *different* file -- on 2026-10-12 the H63M row says "NOT the same
    artifact as gems62-h63-diffuse-isolated-offcat-40k-zeros.tif" while printing H63M's own hash
    and byte count, so the gate read H63M's numbers as a claim about the H63 file and failed the
    audit on a page that was correct. The claim a row can make about a file is the one it links
    to, so that is what is checked now.
    """
    out = []
    sha, size = row.get("sha256") or "", row.get("bytes")
    for page in sorted(set(pages)):
        f = root / page
        if not f.exists():
            continue
        html = f.read_text(errors="ignore")
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            tr = m.group(1)
            # IR-62-B-13: a row may only be held to a claim about a file it LINKS to. A row that
            # merely names another file in its verdict prose is not claiming that file's bytes.
            # The href may carry any prefix (downloads/, a sibling lane's directory), so match
            # on the file name at the end of the target.
            if not re.search(r'href="[^"]*' + re.escape(name) + r'"', tr):
                continue
            for hexm in re.finditer(r"(?<![0-9a-f/])([0-9a-f]{16,64})(?![0-9a-f])", tr):
                tok = hexm.group(1)
                # a 16+ char hex token is a hash claim; shorter ones are session ids, and anything
                # after a slash (arena/d0303476) is a branch name, not a digest
                if sha and not sha.startswith(tok):
                    out.append(f"{page}: prints hash {tok} for {name}, whose sha256 starts "
                               f"{sha[:16]} - stale claim, re-run scripts/audit_downloads.py --write")
            for numm in re.finditer(r"([\d][\d,]{3,})\s*(?:B|\bbytes?\b)", tr):
                got = int(numm.group(1).replace(",", ""))
                if size and got != size and got > 999:
                    out.append(f"{page}: prints {got:,} B for {name}, the file on disk is {size:,} B")
    return out
if __name__ == "__main__":
    sys.exit(main())
