#!/usr/bin/env python3
"""Fetch every layer this session reads, from the group's PUBLIC repositories.

No credentials beyond the already-configured `gh` token; no DrivenData login.
Everything lands in `build/ext/` (gitignored) with a sha256 + byte-count receipt so that
every downstream number can be tied to exact bytes.

Usage:  python3 scripts/fetch_ext_20261011b.py [--dest build/ext] [--only SUBSTR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

OWNER = "buffedlizard55-lab"

# (repo, path, expected sha256 or None)
SOURCES: list[tuple[str, str, str | None]] = [
    # --- official competition feature stack, transported as 5 parts by GEMSDOE -------
    ("GEMSDOE", "data/bridge/gems-geodawn-numerical-features.tif.part-000", None),
    ("GEMSDOE", "data/bridge/gems-geodawn-numerical-features.tif.part-001", None),
    ("GEMSDOE", "data/bridge/gems-geodawn-numerical-features.tif.part-002", None),
    ("GEMSDOE", "data/bridge/gems-geodawn-numerical-features.tif.part-003", None),
    ("GEMSDOE", "data/bridge/gems-geodawn-numerical-features.tif.part-004", None),
    # --- 100 m DEM on the competition grid (hash pinned in registry/data_pins.json) ---
    ("60GEMSDOE", "data/geodawn_dem_a2_100m.tif",
     "d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431"),
    # --- derived layers ---------------------------------------------------------------
    ("60GEMSDOE", "data/external/topo_10m_derived_100m_u8.tif", None),
    ("60GEMSDOE", "data/external/lidar_scarp_features_u8.tif", None),
    ("60GEMSDOE", "data/external/geodawn_rad_u8.tif", None),
    ("60GEMSDOE", "data/external/geodawn_extensions_u8.tif", None),
    ("60GEMSDOE", "data/external/dem10_chi_100m_i16.tif", None),
    # --- catalogue geometry / attributes (small CSVs) --------------------------------
    ("60GEMSDOE", "data/external/trace_segments_utm11.csv", None),
    ("60GEMSDOE", "data/external/qfault_attributes.csv", None),
]


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="build/ext")
    ap.add_argument("--only", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    report, ok = [], True
    for repo, path, want in SOURCES:
        name = pathlib.Path(path).name
        if args.only and args.only not in name:
            continue
        out = dest / name
        t0 = time.time()
        if out.exists() and not args.force and out.stat().st_size > 1000:
            digest = sha256(out)
            status = "cached"
        else:
            status = "fetched"
            with open(out, "wb") as fh:
                proc = subprocess.run(
                    ["gh", "api", f"repos/{OWNER}/{repo}/contents/{path}",
                     "-H", "Accept: application/vnd.github.raw"],
                    stdout=fh, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                print(f"FAIL {repo}/{path}: {proc.stderr.decode()[:200]}", file=sys.stderr)
                out.unlink(missing_ok=True)
                ok = False
                continue
            digest = sha256(out)
        nbytes = out.stat().st_size
        match = (want is None) or (digest == want)
        ok = ok and match
        report.append(dict(repo=repo, path=path, local=str(out), bytes=nbytes,
                           sha256=digest, expected=want, hash_match=match,
                           status=status, seconds=round(time.time() - t0, 1)))
        print(f"{'ok ' if match else 'HASH-MISMATCH '}{name:<48} {nbytes:>12,} B  "
              f"{digest[:16]}  ({status}, {time.time() - t0:.0f}s)")
    receipt = dest / "fetch_receipt.json"
    prev = json.loads(receipt.read_text()) if receipt.exists() else {"records": []}
    # only keep newest record per (repo,path)
    merged = {(r["repo"], r["path"]): r for r in prev.get("records", [])}
    for r in report:
        merged[(r["repo"], r["path"])] = r
    receipt.write_text(json.dumps(
        dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             source=f"https://api.github.com/repos/{OWNER}/<repo>/contents/<path> "
                    "(Accept: application/vnd.github.raw)",
             note="owner-mirrored bytes; hashing proves mirror consistency only, not "
                  "organizer authentication",
             records=sorted(merged.values(), key=lambda r: (r["repo"], r["path"]))),
        indent=1) + "\n")
    print(f"\nreceipt -> {receipt}   all_hashes_match={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
