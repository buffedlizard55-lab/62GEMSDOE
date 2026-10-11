"""The requested 70% asymmetric overlap is a stop rule, not a Jaccard heuristic."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_uniqueness.py"
sys.path.insert(0, str(ROOT / "src"))


def _write(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[0],
                       width=values.shape[1], count=1, dtype="float32", crs="EPSG:32611",
                       transform=Affine(100, 0, 0, 0, -100, values.shape[0] * 100)) as dst:
        dst.write(values.astype(np.float32), 1)


def _run(tmp_path: Path, candidate: np.ndarray, comparator: np.ndarray):
    raster = tmp_path / "candidate.tif"
    footprint = tmp_path / "footprint.tif"
    registry = tmp_path / "registry" / "nested" / "repo"
    comparison = registry / "old.tif"
    report_path = tmp_path / "report.json"
    _write(raster, candidate)
    _write(footprint, np.ones(candidate.shape, dtype=np.float32))
    _write(comparison, comparator)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--raster", str(raster), "--registry",
         str(tmp_path / "registry"), "--footprint", str(footprint), "--out",
         str(report_path)], capture_output=True, text=True, check=False)
    return result, json.loads(report_path.read_text())


def test_dense_registry_comparator_triggers_literal_raw_overlap_stop(tmp_path):
    candidate = np.zeros((32, 32), dtype=np.float32)
    candidate[4, 4] = candidate[12, 17] = candidate[23, 8] = candidate[28, 28] = 1
    dense = np.ones_like(candidate)

    result, report = _run(tmp_path, candidate, dense)

    assert result.returncode == 2
    assert report["verdict"] == "DUPLICATE-STOP"
    assert report["n_registry_files"] == report["n_registry_compared"] == 1
    assert report["worst_overlap"]["alias"] == "nested/repo/old.tif"
    assert report["worst_overlap"]["frac3px"] == 1.0
    assert report["any_overlap_flag"] is True
    assert report["strict_summary"]["n_vacuous_diagnostic_only"] == 1


def test_nonoverlapping_raster_is_not_called_a_duplicate(tmp_path):
    candidate = np.zeros((32, 32), dtype=np.float32)
    candidate[3, 3] = candidate[4, 4] = candidate[5, 5] = 1
    comparator = np.zeros_like(candidate)
    comparator[25, 25] = comparator[26, 26] = comparator[27, 27] = 1

    result, report = _run(tmp_path, candidate, comparator)

    assert result.returncode == 0
    assert report["verdict"] == "NO-STRICT-TRIPWIRE"
    assert report["worst_overlap"]["frac3px"] == 0.0
    assert report["any_rank_flag"] is False
    assert report["any_overlap_flag"] is False


def test_active_gate_receipts_persisted_seed_surface_and_skips_only_itself(tmp_path):
    from scripts.run_lane import strict_registry_gate
    from gems62 import grid

    registry = tmp_path / "registry"
    candidate_path = registry / "current-seed.tif"
    comparator_path = registry / "prior.tif"
    report_path = tmp_path / "preplacement.json"
    candidate = np.zeros((12, 12), dtype=np.float32)
    candidate[1, 1] = 1.0
    comparator = np.zeros_like(candidate)
    comparator[10, 10] = 1.0

    def write_official_origin(path, values):
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", driver="GTiff", height=12, width=12,
                           count=1, dtype="float32", crs=grid.CRS,
                           transform=Affine(*grid.TRANSFORM)) as dst:
            dst.write(values, 1)

    write_official_origin(candidate_path, candidate)
    write_official_origin(comparator_path, comparator)
    report = strict_registry_gate(
        candidate, registry, np.ones_like(candidate, dtype=bool), report_path,
        stage="preplacement-seed-surface", candidate_path=candidate_path)

    assert report["candidate_surface_sha256"] == grid.sha256(candidate_path)
    assert report["candidate_surface_file"] == str(candidate_path)
    assert report["registry_files_discovered"] == 2
    assert report["registry_files_total"] == 1
    assert report["candidate_path_excluded_from_registry"] is True
    assert report["registry_files_checked_until_stop"] == 1
    assert report["strict_summary"]["passed"] is True
    assert report_path.is_file()
