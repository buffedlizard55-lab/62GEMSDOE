#!/usr/bin/env python3
"""Fetch every earlier submission raster the uniqueness tripwire must be checked against.

The earlier ``tools/fetch_registry.py`` filters candidate blobs by a name hint
(``zeros``/``nan``/``submission``/…) and returned **zero** rasters when run on 2026-10-12,
because most sibling repositories ship their artifacts as ``docs/downloads/<name>.tif`` with
none of those substrings.  This fetcher drops the name filter and takes every single-band
GeoTIFF under ``docs/downloads/`` or ``data/evidence/`` up to 3 MB, plus the artifacts that
already live in this repository.

Only api.github.com is contacted (the sandbox has no other outbound network).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

ORG = "buffedlizard55-lab"
REPOS = [
    "GEMSDOE", "GEMSDOE2", "GEMSDOE3", "GEMSDOE4", "5GEMSDOE", "6GEMSDOE", "7GEMSDOE",
    "8GEMSDOE", "GEMSDOE9", "GEMSDOE10", "11GEMSDOE", "12GEMSDOE", "13GEMSDOE", "14GEMSDOE",
    "15GEMSDOE", "16GEMSDOE", "17GEMSDOE", "18GEMSDOE", "19GEMSDOE", "20GEMSDOE",
    "GEMSDOE21", "GEMSDOE22", "GEMSDOE23", "GEMSDOE24", "GEMSDOE25", "GEMSDOE26",
    "GEMSDOE27", "GEMSDOE28", "GEMSDOE29", "GEMSDOE30", "GEMSDOE31", "GEMSDOE32",
    "GEMSDOE33", "GEMSDOE34", "GEMSDOE35", "GEMSDOE36", "GEMSDOE37", "GEMSDOE38",
    "GEMSDOE39", "GEMSDOE40", "GEMSDOE41", "GEMSDOE42", "GEMSDOE43", "GEMSDOE44",
    "GEMSDOE45", "GEMSDOE46", "GEMSDOE47", "GEMSDOE48", "GEMSDOE49", "GEMSDOE50",
    "GEMSDOE51", "GEMSDOE52", "GEMSDOE53", "GEMSDOE54", "55GEMSDOE", "56GEMSDOE",
    "57GEMSDOE", "58GEMSDOE", "59GEMSDOE", "60GEMSDOE", "61GEMSDOE", "62GEMSDOE",
]
MAX_MB = 3.0


def _get(url: str, accept: str = "application/vnd.github+json", timeout: int = 120):
    req = urllib.request.Request(url, headers={"User-Agent": "62gemsdoe-registry",
                                               "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/registry")
    ap.add_argument("--max-mb", type=float, default=260.0)
    ap.add_argument("--minutes", type=float, default=12.0)
    args = ap.parse_args()
    import time
    t0 = time.time()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    spent = 0
    for repo in REPOS:
        if time.time() - t0 > args.minutes * 60:
            print(f"time budget reached after {repo}", flush=True)
            break
        try:
            info = json.loads(_get(f"https://api.github.com/repos/{ORG}/{repo}"))
            br = info.get("default_branch", "main")
            tree = json.loads(_get(
                f"https://api.github.com/repos/{ORG}/{repo}/git/trees/{br}?recursive=1"))
        except Exception as exc:                                   # noqa: BLE001
            print(f"  skip {repo}: {exc}", flush=True)
            continue
        blobs = [e for e in tree.get("tree", [])
                 if e.get("type") == "blob"
                 and e["path"].endswith(".tif")
                 and e.get("size", 0) <= MAX_MB * 1e6
                 and ("downloads" in e["path"] or "evidence" in e["path"])]
        for e in blobs:
            if spent + e["size"] > args.max_mb * 1e6:
                continue
            dest = out / f"{repo}__{pathlib.Path(e['path']).name}"
            if dest.exists() and dest.stat().st_size == e["size"]:
                spent += e["size"]
                manifest.append(dict(repo=repo, path=e["path"], file=dest.name,
                                     bytes=e["size"], status="cached"))
                continue
            try:
                data = _get(f"https://api.github.com/repos/{ORG}/{repo}/contents/{e['path']}",
                            accept="application/vnd.github.raw", timeout=300)
            except Exception as exc:                               # noqa: BLE001
                print(f"  fail {repo}:{e['path']}: {exc}", flush=True)
                continue
            dest.write_bytes(data)
            spent += len(data)
            manifest.append(dict(repo=repo, path=e["path"], file=dest.name, bytes=len(data),
                                 sha256=hashlib.sha256(data).hexdigest(), status="fetched"))
        print(f"  {repo}: {len(blobs)} blobs, {spent/1e6:.1f} MB total", flush=True)
    (out / "manifest.json").write_text(json.dumps(dict(
        fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        total_mb=round(spent / 1e6, 2), n=len(manifest), entries=manifest), indent=1))
    print(f"registry: {len(manifest)} rasters, {spent/1e6:.1f} MB -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
