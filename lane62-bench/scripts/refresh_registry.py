#!/usr/bin/env python3
"""Scan every sibling GEMSDOE repository and cache every accessible prior
competition-grid prediction raster.

Used only for the pre-placement surface gate and the final-dot drift gate: a
new candidate must not be a copy of an earlier raster.

Method
------
The GitHub REST API enforces an undocumented secondary (burst) limit that a
60-repository scan trips immediately, but the **git** protocol to
``github.com`` does not.  Each sibling is therefore cloned
``--depth 1 --filter=blob:none --sparse`` and sparsely checked out with the
pattern ``*.tif``/``*.tiff``, so only the GeoTIFF blobs are transferred.  The
commit of each clone is recorded so the inventory is reproducible.

Inputs (bridge files, feature stacks, DEM tiles, LIDAR products) are excluded
by path: an input cannot be a previous prediction.  A single-band 3730x3292
EPSG:32611 raster that is not an input is kept, including dense soft fields --
a dense prior is exactly what can block a candidate.

Outputs ``evidence/registry_refreshed.json`` and a ``registry/cache`` of
immutable copies (never committed).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OWNER = "buffedlizard55-lab"
SELF = "61GEMSDOE"
SCRATCH = Path("/tmp/gems61-registry-clones")

# Input/auxiliary rasters are not predictions and must never gate a candidate.
INPUT_PATTERNS = (
    ".part-", "numerical-features", "training_features", "existing_faults",
    "sample_submission", "example_submission", "labels.tif", "/external/",
    "/raw/", "/bridge/", "/source_mirrors/", "/aux/", "/audit_sources/",
    "lidar_scarp", "topo_u8", "h52_scarp", "geodawn_rad", "sgmc_faults",
    "derived_sgmc", "depth_to_base", "quarantine",
)

SHAPE = (3730, 3292)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as s:
        for c in iter(lambda: s.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def list_repos() -> list[str]:
    p = subprocess.run(["gh", "repo", "list", OWNER, "--limit", "200", "--json", "name"],
                       capture_output=True, timeout=180)
    if p.returncode:
        raise RuntimeError(f"repo list failed: {p.stderr.decode()[:200]}")
    names = [r["name"] for r in json.loads(p.stdout)]
    return sorted(n for n in names if "GEMSDOE" in n.upper() and n != SELF)


def clone_repo(repo: str, scratch: Path) -> tuple[str, str]:
    dest = scratch / repo
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", "-q",
                    f"https://github.com/{OWNER}/{repo}.git", str(dest)],
                   check=True, capture_output=True, timeout=1800)
    subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", "--no-cone",
                    "*.tif", "*.tiff"], check=True, capture_output=True, timeout=1800)
    commit = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                            capture_output=True, check=True, timeout=120).stdout.decode().strip()
    return repo, commit


def is_input(rel: str) -> bool:
    low = rel.lower()
    return any(p.lower() in low for p in INPUT_PATTERNS)


def classify(path: Path) -> tuple[bool, str]:
    import rasterio
    with rasterio.open(path) as src:
        if src.count != 1:
            return False, f"band count {src.count}"
        if tuple(src.shape) != SHAPE:
            return False, f"shape {src.shape}"
        if src.crs is None or src.crs.to_epsg() != 32611:
            return False, f"crs {src.crs}"
        if tuple(float(v) for v in src.transform)[:6] != TRANSFORM:
            return False, "different transform"
    return True, ""


def refresh(root: Path = ROOT, workers: int = 6, scratch: Path = SCRATCH) -> dict:
    cache = root / "registry" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    repos = list_repos()

    snapshots: list[dict] = []
    errors: list[dict] = []
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(clone_repo, r, scratch): r for r in repos}
        for fut in as_completed(futures):
            repo = futures[fut]
            try:
                repo, commit = fut.result()
            except Exception as exc:                      # noqa: BLE001
                errors.append(dict(repo=repo, error=str(exc)[:200]))
                continue
            snapshots.append(dict(repo=repo, commit=commit))
            base = scratch / repo
            for p in base.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in (".tif", ".tiff"):
                    continue
                if ".git" in p.relative_to(base).parts:
                    continue
                rel = str(p.relative_to(base))
                if rel == ".git":
                    continue
                if is_input(rel):
                    found.append(dict(repo=repo, path=rel, skipped="input/auxiliary source raster"))
                    continue
                found.append(dict(repo=repo, path=rel, abs=str(p)))

    usable: list[dict] = []
    rejected: list[dict] = []
    skipped: list[dict] = []
    seen: dict[str, dict] = {}
    for item in found:
        if "skipped" in item:
            skipped.append({k: v for k, v in item.items() if k != "abs"})
            continue
        p = Path(item["abs"])
        digest = sha256(p)
        source = f"{item['repo']}:{item['path']}"
        rec = seen.get(digest)
        if rec is None:
            target = cache / f"{digest[:24]}.tif"
            if not target.exists():
                shutil.copyfile(p, target)
            ok, why = classify(target)
            rec = dict(sha256=digest, bytes=int(target.stat().st_size),
                       cache_file=str(target.relative_to(root)), sources=[],
                       comparable=ok, reason="" if ok else why)
            seen[digest] = rec
            if not ok:
                rejected.append(dict(sha256=digest, sources=[source], reason=why))
        rec["sources"].append(source)
    usable = [r for r in seen.values() if r["comparable"]]
    for r in usable:
        r["sources"] = sorted(set(r["sources"]))
    usable.sort(key=lambda r: r["sources"][0])

    out = dict(evidence_class="DATA-INVENTORY",
               generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               owner=OWNER, self_repo=SELF,
               method="git sparse clone (--depth 1 --filter=blob:none --sparse '*.tif')",
               repos_scanned=repos, snapshots=sorted(snapshots, key=lambda s: s["repo"]),
               repos_unreachable_or_missing=sorted({e.get("repo", "") for e in errors if e.get("repo")}),
               errors=errors,
               grid=dict(shape=list(SHAPE), crs="EPSG:32611", transform=list(TRANSFORM)),
               n_unique_grid_rasters=len(usable),
               complete_accessible_scan=not errors,
               skipped_inputs=skipped,
               rejected_not_competition_grid=rejected,
               rasters=usable,
               scope=("every accessible sibling GEMSDOE repository reachable from main; "
                      "single-band 3730x3292 EPSG:32611 rasters only; inputs excluded by path"))
    (root / "evidence").mkdir(exist_ok=True)
    (root / "evidence/registry_refreshed.json").write_text(
        json.dumps(out, indent=2, allow_nan=False) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = refresh(workers=a.workers)
    print(f"[registry] repos={len(out['repos_scanned'])} rasters={out['n_unique_grid_rasters']} "
          f"errors={len(out['errors'])} rejected={len(out['rejected_not_competition_grid'])} "
          f"inputs_skipped={len(out['skipped_inputs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
