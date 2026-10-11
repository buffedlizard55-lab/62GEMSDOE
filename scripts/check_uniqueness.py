#!/usr/bin/env python3
"""CLI for the shared, strict registry gate in ``gems62.uniqueness``."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import grid, uniqueness  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True)
    ap.add_argument("--registry", required=True,
                    help="registry folder; GeoTIFF search is recursive")
    ap.add_argument("--footprint", help="official sample raster; defaults to pinned sample")
    ap.add_argument("--out", default="build/uniqueness.json")
    args = ap.parse_args()

    import rasterio

    raster = pathlib.Path(args.raster)
    registry_root = pathlib.Path(args.registry)
    if not registry_root.is_dir():
        raise FileNotFoundError(f"registry directory does not exist: {registry_root}")
    paths = sorted(p for p in registry_root.rglob("*")
                   if p.is_file() and p.suffix.lower() in {".tif", ".tiff"})
    if not paths:
        raise ValueError(f"no GeoTIFFs found recursively under {registry_root}")

    footprint_path = pathlib.Path(args.footprint) if args.footprint else grid.DEFAULT_SAMPLE
    with rasterio.open(raster) as src:
        mine = src.read(1).astype(np.float32)
        candidate_crs = str(src.crs)
        candidate_transform = tuple(float(x) for x in src.transform[:6])
    with rasterio.open(footprint_path) as src:
        footprint = np.isfinite(src.read(1))
    if footprint.shape != mine.shape:
        raise ValueError(f"footprint shape {footprint.shape} != raster shape {mine.shape}")

    registry = {str(p.relative_to(registry_root)): p for p in paths}
    entries = uniqueness.compare(mine, registry, footprint, expected_crs=candidate_crs,
                                 expected_transform=candidate_transform, fail_fast=True)
    summary = uniqueness.verdict(entries)
    comparable = [e for e in entries if e.comparable]
    finite_rank = [e for e in comparable if np.isfinite(e.rho)]
    worst_rank = max(finite_rank, key=lambda e: e.rho) if finite_rank else None
    worst_overlap = max(comparable, key=lambda e: e.frac3px) if comparable else None
    report = {
        "raster": raster.name,
        "raster_sha256": grid.sha256(raster),
        "registry_root": str(registry_root),
        "comparison_scope": ("recursive fail-fast; entries/extrema cover only comparators "
                              "scanned through the first strict violation"),
        "n_registry_files": len(paths),
        "n_registry_scanned": len(entries),
        "n_registry_compared": len(comparable),
        "n_registry_uncomparable_scanned": len(entries) - len(comparable),
        "n_registry_remaining_unscanned": len(paths) - len(entries),
        "scan_stopped_early": len(entries) < len(paths),
        "strict_summary": summary,
        "any_rank_flag": summary["rho_trip"],
        "any_overlap_flag": summary["overlap_trip"],
        "verdict": summary["verdict"].replace(" - ", "-").replace(" ", "-"),
        "worst_rank_corr": asdict(worst_rank) if worst_rank else None,
        "worst_overlap": asdict(worst_overlap) if worst_overlap else None,
        "strict_failures": [asdict(e) for e in entries if e.rank_flag or e.overlap_flag],
        "results": [asdict(e) for e in entries],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, allow_nan=True))
    print(json.dumps({k: report[k] for k in (
        "verdict", "n_registry_files", "n_registry_scanned", "n_registry_compared",
        "n_registry_uncomparable_scanned", "n_registry_remaining_unscanned",
        "worst_rank_corr", "worst_overlap")}, indent=1, allow_nan=True))
    print("wrote", out)
    if summary["verdict"] == "DUPLICATE - STOP":
        return 2
    if summary["verdict"] == "REVIEW INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
