#!/usr/bin/env python3
"""Build the *registry*: every earlier competition-grid prediction raster in the
family (all sibling GEMSDOE repositories), cached outside the repository and
indexed for the uniqueness gate.

Why this is not just ``refresh_registry.py`` copied from the 61 template
------------------------------------------------------------------------
The template (``61GEMSDOE/scripts/refresh_registry.py``) sparse-clones every
sibling with the pattern ``*.tif``.  That is correct but it also transfers every
*input* raster it later throws away (DEM / lidar / feature stacks: hundreds of
MB per repo).  In this sandbox the transfer, not the logic, is the bottleneck,
so the same selection is done with the GitHub tree+blob REST API: the tree is
filtered by path and size first and only the surviving blobs are downloaded.
The classification rule (single band, 3730x3292, EPSG:32611, sample-submission
transform, input paths excluded, deduplicated by sha256) is unchanged from the
template, so results remain comparable across lanes.

Outputs (deliberately outside the repo working tree so the git artifact budget
is not spent on cache): ``$GEMS_REGISTRY/cache/<sha256[:24]>.tif`` and
``$GEMS_REGISTRY/index.json`` with ``declared_scope_complete``.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OWNER = "buffedlizard55-lab"
SELF = os.environ.get("GEMS_SELF", "62GEMSDOE")
ROOT = Path(__file__).resolve().parents[1]
REG = Path(os.environ.get("GEMS_REGISTRY", "/home/user/datacache/registry"))
SHAPE = (3730, 3292)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
MAX_BYTES = int(os.environ.get("GEMS_MAX_RASTER_BYTES", 12_000_000))

# Input / auxiliary rasters are not predictions and must never gate a candidate.
# (identical list to the 61 template, so the two registries are comparable)
INPUT_PATTERNS = (
    ".part-", "numerical-features", "training_features", "existing_faults",
    "sample_submission", "example_submission", "labels.tif", "/external/",
    "/raw/", "/bridge/", "/source_mirrors/", "/aux/", "/audit_sources/",
    "lidar_scarp", "topo_u8", "h52_scarp", "geodawn_rad", "sgmc_faults",
    "derived_sgmc", "depth_to_base", "quarantine", "features_u8", "extensions_u8",
    "dem10", "dem_a2", "_dem_", "fixture", "nodata", "template",
)


def gh(*args, binary_out: Path | None = None, tries: int = 3) -> str | bytes | None:
    cmd = ["gh", "api", *args]
    for attempt in range(tries):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=300)
        except Exception:                                   # noqa: BLE001
            time.sleep(2 + 3 * attempt)
            continue
        if p.returncode == 0:
            if binary_out is not None:
                binary_out.write_bytes(base64.b64decode(p.stdout))
                return "OK"
            return p.stdout.decode()
        time.sleep(1.5 * (attempt + 1))
    return None


def is_input(rel: str) -> bool:
    low = "/" + rel.lower()
    return any(("/" + p.strip("/")) in low or p in low for p in INPUT_PATTERNS)


def classify(path: Path) -> tuple[bool, str]:
    import rasterio
    try:
        with rasterio.open(path) as src:
            if src.count != 1:
                return False, f"band count {src.count}"
            if tuple(src.shape) != SHAPE:
                return False, f"shape {src.shape}"
            if src.crs is None or src.crs.to_epsg() != 32611:
                return False, f"crs {src.crs}"
            if tuple(float(v) for v in src.transform)[:6] != TRANSFORM:
                return False, "different transform"
            if src.dtypes[0] not in ("float32", "uint8", "float64", "int16", "uint16"):
                return False, f"dtype {src.dtypes[0]}"
    except Exception as exc:                                # noqa: BLE001
        return False, f"unreadable: {str(exc)[:120]}"
    return True, ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def repo_candidates(repo: str) -> list[dict]:
    out = gh(f"/repos/{OWNER}/{repo}/git/trees/main?recursive=1")
    if not out:
        raise RuntimeError("tree API failed")
    tree = json.loads(out)["tree"]
    cand = []
    for e in tree:
        p = e["path"]
        if e["type"] != "blob" or not p.lower().endswith((".tif", ".tiff")):
            continue
        size = int(e.get("size") or 0)
        if size < 1000 or size > MAX_BYTES:
            continue
        if is_input(p):
            continue
        cand.append(dict(repo=repo, path=p, size=size, blob_sha=e["sha"]))
    return cand


def download(item: dict, cache: Path) -> dict:
    stem = f"{item['repo']}__{Path(item['path']).stem}".replace("/", "_")
    tmp = cache / (stem + ".tif.part")
    ok = gh(f"/repos/{OWNER}/{item['repo']}/git/blobs/{item['blob_sha']}",
            "--jq", ".content", binary_out=tmp)
    if ok != "OK":
        tmp.unlink(missing_ok=True)
        return dict(item, error="blob download failed")
    digest = sha256_file(tmp)
    final = cache / f"{digest[:24]}.tif"
    if final.exists():
        tmp.unlink(missing_ok=True)
    else:
        os.replace(tmp, final)
    return dict(item, abs=str(final), sha256=digest, bytes=final.stat().st_size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cache = REG / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    repos = json.loads(gh(f"/users/{OWNER}/repos?per_page=200") or "[]")
    names = sorted(r["name"] for r in repos if "GEMSDOE" in r["name"].upper() and r["name"] != SELF)
    print(f"[registry] sibling repos: {len(names)}", flush=True)

    cands: list[dict] = []
    errors: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        fut = {pool.submit(repo_candidates, r): r for r in names}
        for f in cf.as_completed(fut):
            r = fut[f]
            try:
                cands.extend(f.result())
            except Exception as exc:                        # noqa: BLE001
                errors.append(dict(repo=r, error=str(exc)[:200]))
    print(f"[registry] candidate prediction rasters: {len(cands)}", flush=True)

    rows: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        fut = {pool.submit(download, c, cache): c for c in cands}
        for i, f in enumerate(cf.as_completed(fut), 1):
            try:
                rows.append(f.result())
            except Exception as exc:                        # noqa: BLE001
                errors.append(dict(item=fut[f], error=str(exc)[:200]))
            if i % 100 == 0:
                print(f"[registry] downloaded {i}/{len(cands)}", flush=True)

    seen: dict[str, dict] = {}
    rejected = []
    for r in rows:
        if "abs" not in r:
            errors.append(dict(item=r, error=r.get("error", "no file")))
            continue
        rec = seen.get(r["sha256"])
        if rec is None:
            ok, why = classify(Path(r["abs"]))
            rec = dict(sha256=r["sha256"], bytes=r["bytes"], cache_file=r["abs"],
                       sources=[], comparable=ok, reason=why)
            seen[r["sha256"]] = rec
            if not ok:
                rejected.append(dict(sha256=r["sha256"], sources=[f"{r['repo']}:{r['path']}"],
                                     reason=why))
                Path(r["abs"]).unlink(missing_ok=True)
                continue
        rec["sources"].append(f"{r['repo']}:{r['path']}")
    usable = sorted([v for v in seen.values() if v["comparable"]],
                    key=lambda v: v["sources"][0])
    for v in usable:
        v["sources"] = sorted(set(v["sources"]))
    out = dict(evidence_class="DATA-INVENTORY",
               generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               owner=OWNER, self_repo=SELF,
               method="GitHub tree+blob REST API; filtered by path/size before transfer; "
                      "grid-classified with rasterio; deduplicated by sha256",
               repos_scanned=names, n_repos=len(names),
               repos_unreachable_or_missing=sorted({e.get("repo", "") for e in errors if e.get("repo")}),
               errors=errors, grid=dict(shape=list(SHAPE), crs="EPSG:32611", transform=list(TRANSFORM)),
               n_candidate_paths=len(cands), n_unique_grid_rasters=len(usable),
               rejected_not_competition_grid=rejected,
               complete_accessible_scan=not errors,
               declared_scope_complete=not errors,
               organizer_registry_complete=False,
               scope="every accessible sibling GEMSDOE repository reachable from main; "
                     "single-band 3730x3292 EPSG:32611 prediction rasters only; inputs excluded by path",
               rasters=usable)
    REG.mkdir(parents=True, exist_ok=True)
    (REG / "index.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"[registry] DONE repos={len(names)} unique_grid_rasters={len(usable)} "
          f"errors={len(errors)} rejected={len(rejected)}", flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
