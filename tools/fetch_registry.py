#!/usr/bin/env python3
"""Download the earlier submission rasters published by the sibling experimental repositories,
so the uniqueness check ("is this raster a re-run of something already shipped?") runs against
the real registry instead of a claim about it.

Only files that look like competition-format submissions are taken (single-band GeoTIFFs under
`docs/downloads/`), with a byte budget so the local registry stays small.  A manifest with the
sha256 of every downloaded file is written next to the rasters.

Usage: python tools/fetch_registry.py --out /tmp/registry --max-mb 250
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

REPOS = [
    "GEMSDOE", "GEMSDOE2", "GEMSDOE3", "GEMSDOE4", "5GEMSDOE", "6GEMSDOE", "7GEMSDOE",
    "8GEMSDOE", "GEMSDOE9", "GEMSDOE10", "11GEMSDOE", "12GEMSDOE", "13GEMSDOE", "14GEMSDOE",
    "15GEMSDOE", "16GEMSDOE", "17GEMSDOE", "18GEMSDOE", "19GEMSDOE", "20GEMSDOE", "GEMSDOE21",
    "GEMSDOE22", "GEMSDOE23", "GEMSDOE24", "GEMSDOE25", "GEMSDOE26", "GEMSDOE27", "GEMSDOE28",
    "GEMSDOE29", "GEMSDOE30", "GEMSDOE31", "GEMSDOE32", "GEMSDOE33", "GEMSDOE34", "GEMSDOE35",
    "GEMSDOE36", "GEMSDOE37", "GEMSDOE38", "GEMSDOE39", "GEMSDOE40", "GEMSDOE41", "GEMSDOE42",
    "GEMSDOE43", "GEMSDOE44", "GEMSDOE45", "GEMSDOE46", "GEMSDOE47", "GEMSDOE48", "GEMSDOE49",
    "GEMSDOE50", "GEMSDOE51", "GEMSDOE52", "GEMSDOE53", "GEMSDOE54", "55GEMSDOE", "56GEMSDOE",
    "57GEMSDOE", "58GEMSDOE", "59GEMSDOE", "60GEMSDOE", "61GEMSDOE",
]
ORG = "buffedlizard55-lab"
MAX_FILE_MB = 3.0
NAME_HINTS = ("zeros", "nan", "submission", "dotted", "candidate", "allfinite", "top2pct")


def gh_json(args: list[str]):
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/registry")
    ap.add_argument("--max-mb", type=float, default=250.0)
    args = ap.parse_args()
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    budget = args.max_mb * 1e6
    spent = 0
    manifest = []
    for repo in REPOS:
        info = gh_json([f"repos/{ORG}/{repo}"])
        if not info:
            continue
        br = info.get("default_branch", "main")
        tree = gh_json([f"repos/{ORG}/{repo}/git/trees/{br}?recursive=1"])
        if not tree:
            continue
        for e in tree.get("tree", []):
            if e["type"] != "blob" or not e["path"].endswith(".tif"):
                continue
            size = e.get("size", 0)
            low = e["path"].lower()
            if size > MAX_FILE_MB * 1e6:
                continue
            if "downloads" not in low and "evidence" not in low:
                continue
            if not any(h in low for h in NAME_HINTS):
                continue
            if spent + size > budget:
                continue
            # IR-62-REG-01 FIX (2026-10-12).  The destination was
            # ``f"{repo}__{pathlib.Path(e['path']).name}"``, which collapses every
            # ``docs/downloads/submission.tif`` in a repository onto one file: in the
            # 2026-10-12 run, 46 of the first 51 fetches wrote to the same handful of
            # names (GEMSDOE4 alone produced 23 distinct rasters and kept one).  The
            # uniqueness gate would then have compared a candidate against a fraction of
            # the registry while reporting the full count.  The path is now flattened
            # with its directory separators preserved, so each blob keeps its own name.
            flat = str(pathlib.PurePosixPath(e["path"]).with_suffix("")).replace("/", "_")
            dest = out / f"{repo}__{flat}.tif"
            if dest.exists() and dest.stat().st_size == size:
                spent += size
                continue
            r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                                f"repos/{ORG}/{repo}/contents/{e['path']}"],
                               stdout=open(dest, "wb"), stderr=subprocess.PIPE, timeout=180)
            if r.returncode != 0:
                dest.unlink(missing_ok=True)
                continue
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            spent += size
            manifest.append(dict(repo=repo, path=e["path"], bytes=size, sha256=h,
                                 local=dest.name))
            print(f"{repo:12s} {size/1e6:6.3f}MB {dest.name}", flush=True)
    (out / "registry_manifest.json").write_text(json.dumps(
        dict(org=ORG, n=len(manifest), bytes=int(spent), files=manifest), indent=1))
    print(f"registry: {len(manifest)} rasters, {spent/1e6:.1f} MB -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
