#!/usr/bin/env python3
"""Fetch the external rasters this lane reads, from the group's PUBLIC repositories.

Nothing here requires DrivenData credentials and nothing here logs in.  The three
competition rasters (`labels.tif`, `existing_faults.tif`, `sample_submission.tif`) are
committed in `data/`; the *external* layers are re-creatable and stay out of git, so this
script writes them into `data/external/`.

Provenance, stated honestly: these are **owner-mirrored** copies.  Hashing them proves the
bytes are consistent between mirrors; it does **not** authenticate their origin.  The 100 m
DEM's sha256 is pinned in `registry/data_pins.json` and is checked below.

Usage:  python3 scripts/fetch_external.py [--dest data/external]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

OWNER = "buffedlizard55-lab"
SOURCES = [
    # (repo, path-in-repo, expected sha256 or None)
    ("60GEMSDOE", "data/geodawn_dem_a2_100m.tif",
     "d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431"),
    ("60GEMSDOE", "data/external/derived_sgmc_faults_100m.tif", None),
    ("60GEMSDOE", "data/external/lidar_scarp_features_u8.tif", None),
    ("60GEMSDOE", "data/external/topo_10m_derived_100m_u8.tif", None),
]


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data/external")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    report = []
    ok = True
    for repo, path, want in SOURCES:
        out = dest / pathlib.Path(path).name
        if out.exists() and out.stat().st_size > 1000 and not args.force:
            digest = sha256(out)
        else:
            r = subprocess.run(
                ["gh", "api", f"repos/{OWNER}/{repo}/contents/{path}",
                 "-H", "Accept: application/vnd.github.raw"],
                capture_output=True, timeout=900)
            if r.returncode != 0 or not r.stdout:
                print(f"FAIL {path}: {r.stderr.decode()[:160]}", file=sys.stderr)
                ok = False
                report.append(dict(path=path, status="FAIL"))
                continue
            out.write_bytes(r.stdout)
            digest = sha256(out)
        match = (want is None) or (digest == want)
        ok &= match
        report.append(dict(repo=repo, path=path, dest=str(out), bytes=out.stat().st_size,
                           sha256=digest, pin_checked=want is not None, pin_match=match))
        print(f"{'OK ' if match else 'PIN-MISMATCH'} {out.stat().st_size/1e6:8.2f}MB {out}")
    json.dump(dict(sources=report, all_pins_match=ok,
                   provenance="owner-mirrored; hash consistency is NOT origin authentication"),
              open(dest / "fetch_receipt.json", "w"), indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
