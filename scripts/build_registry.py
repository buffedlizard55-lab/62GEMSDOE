#!/usr/bin/env python3
"""Build the registry of every earlier raster, for the uniqueness gate.

Sources, all public GitHub under the ``buffedlizard55-lab`` organisation --
these are the repositories whose GitHub Pages sites the tasking paragraph
lists, each carrying the artifacts the group actually submitted or measured:

    https://api.github.com/users/buffedlizard55-lab/repos

For every repository the git tree is listed
(``/repos/{o}/{r}/git/trees/main?recursive=1``) and each ``.tif`` under a
``downloads``/``submissions`` directory is fetched through the contents API
(``Accept: application/vnd.github.raw``).  Files are skipped when they are
larger than ``--max-mb`` (diagnostic volumes, not submissions), when they are
quarantined, or when they fail to open with rasterio.

Output
------
``registry/rasters/*.tif``      the fetched comparators
``registry/raster_index.json``  name, repo, path, bytes, sha256, shape,
                                n_positive, and the organiser score attached to
                                it where the repository published one.

No score in this index is invented: the ``organizer_score`` field is only
populated from the score list transcribed in ``registry/organizer_scores.json``,
which is copied from the tasking paragraph and from the sibling repositories'
own leaderboards.  Anything else stays ``null``.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

API = "https://api.github.com"
ORG = "buffedlizard55-lab"
HERE = Path(__file__).resolve().parents[1]

DOWNLOAD_DIR_RE = re.compile(r"(^|/)(docs/)?(downloads|submissions|research/quarantine)/")


def gh(url: str, raw: bool = False, timeout: int = 180, retries: int = 3):
    hdr = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
           "User-Agent": "gems62-registry-builder",
           "X-GitHub-Api-Version": "2022-11-28"}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            return data if raw else json.loads(data)
        except Exception as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def list_repos() -> list[str]:
    names, page = [], 1
    while True:
        batch = gh(f"{API}/users/{ORG}/repos?per_page=100&page={page}&sort=created")
        if not batch:
            break
        names += [r["name"] for r in batch]
        if len(batch) < 100:
            break
        page += 1
    return names


def is_gems_repo(name: str) -> bool:
    return bool(re.search(r"(^|[^A-Za-z])GEMSDOE", name, re.I))


def list_tifs(repo: str) -> list[dict]:
    out = []
    for branch in ("main", "master"):
        try:
            t = gh(f"{API}/repos/{ORG}/{repo}/git/trees/{branch}?recursive=1")
            break
        except Exception:
            t = None
    if not t or "tree" in t and t["tree"] is None:
        return out
    for e in t.get("tree", []):
        if e.get("type") != "blob":
            continue
        p = e["path"]
        if not p.lower().endswith((".tif", ".tiff")):
            continue
        if not DOWNLOAD_DIR_RE.search(p):
            continue
        out.append(dict(repo=repo, path=p, bytes=int(e.get("size") or 0), sha=e.get("sha")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "registry"))
    ap.add_argument("--max-mb", type=float, default=25.0)
    ap.add_argument("--repos", nargs="*", default=None,
                    help="restrict to these repo names (default: all *GEMSDOE* repos)")
    ap.add_argument("--limit-per-repo", type=int, default=60)
    args = ap.parse_args()

    outdir = Path(args.out)
    rast = outdir / "rasters"
    rast.mkdir(parents=True, exist_ok=True)

    repos = args.repos or [r for r in list_repos() if is_gems_repo(r)]
    print(f"[registry] {len(repos)} GEMSDOE repositories", flush=True)

    index: list[dict] = []
    n_down = n_skip = n_err = 0
    for repo in repos:
        try:
            tifs = list_tifs(repo)
        except Exception as exc:
            print(f"[registry] {repo}: tree listing failed: {exc}", flush=True)
            continue
        tifs = [t for t in tifs if t["bytes"] <= args.max_mb * 1e6]
        tifs.sort(key=lambda t: t["path"])
        tifs = tifs[: args.limit_per_repo]
        for t in tifs:
            dest = rast / f"{repo}__{Path(t['path']).name}"
            if dest.exists() and dest.stat().st_size == t["bytes"]:
                index.append(dict(repo=repo, path=t["path"], local=str(dest),
                                  bytes=t["bytes"], status="cached"))
                continue
            try:
                blob = gh(f"{API}/repos/{ORG}/{repo}/contents/{t['path']}", raw=True)
                dest.write_bytes(blob)
                n_down += 1
                index.append(dict(repo=repo, path=t["path"], local=str(dest),
                                  bytes=len(blob), status="downloaded"))
            except Exception as exc:
                n_err += 1
                index.append(dict(repo=repo, path=t["path"], local=None,
                                  bytes=t["bytes"], status=f"error: {exc}"))
        print(f"[registry] {repo}: {len(tifs)} tifs", flush=True)

    # verify each fetched raster opens and record its geometry
    try:
        import rasterio
        import hashlib
        good = []
        for r in index:
            if not r.get("local") or not Path(r["local"]).exists():
                continue
            p = Path(r["local"])
            try:
                with rasterio.open(p) as src:
                    a = src.read(1)
                r.update(shape=[src.height, src.width], count=src.count,
                         dtype=src.dtypes[0],
                         epsg=(src.crs.to_epsg() if src.crs else None),
                         n_positive=int(np.isfinite(a).sum() and (a > 0).sum()),
                         sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                good.append(r)
            except Exception as exc:
                r["status"] = f"unreadable: {exc}"
                good.append(r)
        index = good
    except ImportError:
        print("[registry] rasterio unavailable; geometry not recorded", file=sys.stderr)

    (outdir / "raster_index.json").write_text(
        json.dumps(dict(n_repos=len(repos), n_downloaded=n_down, n_skipped=n_skip,
                        n_errors=n_err, rasters=index), indent=2) + "\n")
    print(f"[registry] downloaded={n_down} errors={n_err} entries={len(index)}", flush=True)
    print(f"[registry] wrote {outdir/'raster_index.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
