"""The duplicate gate must implement the literal parallel-run thresholds.

Dense comparators can make dot overlap uninformative, but the protocol still
requires a trip to be logged rather than silently substituted with Jaccard.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems62.uniqueness import RegistryEntry, compare, verdict  # noqa: E402


def row(alias: str, *, rho: float, frac: float, coverage: float) -> RegistryEntry:
    return RegistryEntry(alias, f"{alias}.tif", "0" * 64, 10, rho, frac, coverage,
                         vacuous=coverage >= 0.70)


def test_vacuous_overlap_still_trips_the_binding_rule():
    result = verdict([row("blanketing", rho=0.0, frac=0.95, coverage=0.99)])
    assert result["n_vacuous"] == 1
    assert result["max_frac3px_all"] == 0.95
    assert result["max_frac3px_non_vacuous"] == 0.0
    assert result["overlap_trip"] is True
    assert result["verdict"] == "DUPLICATE - STOP"


def test_positive_rank_correlation_above_limit_trips():
    result = verdict([row("correlated", rho=0.91, frac=0.0, coverage=0.01)])
    assert result["rho_trip"] is True
    assert result["verdict"] == "DUPLICATE - STOP"


def test_negative_correlation_is_not_a_positive_drift_trip():
    result = verdict([row("anticorrelated", rho=-0.99, frac=0.0, coverage=0.01)])
    assert result["rho_trip"] is False
    assert result["passed"] is True


def test_exactly_seventy_percent_is_not_more_than_seventy_percent():
    result = verdict([row("boundary", rho=0.0, frac=0.70, coverage=0.10)])
    assert result["overlap_trip"] is False
    assert result["passed"] is True


def test_empty_registry_is_unverified_not_a_distinctness_pass():
    result = verdict([])
    assert result["passed"] is False
    assert result["overlap_trip"] is False
    assert result["verdict"] == "NOT VERIFIED - EMPTY REGISTRY"
    assert result["n_registry"] == 0
    assert math.isnan(result["max_rho"])


def test_rank_threshold_is_strictly_exceeded():
    result = verdict([row("boundary", rho=0.90, frac=0.0, coverage=0.01)])
    assert result["rho_trip"] is False
    assert result["passed"] is True


def test_dot_tolerance_is_euclidean_not_square_dilation(tmp_path):
    profile = {
        "driver": "GTiff", "height": 9, "width": 9, "count": 1,
        "dtype": "float32", "transform": from_origin(0, 900, 100, 100),
        "crs": "EPSG:32611", "nodata": -9999,
    }

    def save(path, values):
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(values.astype(np.float32), 1)

    mine = np.zeros((9, 9), dtype=np.float32)
    mine[1, 1] = 1
    registry = np.zeros_like(mine)
    registry[4, 4] = 1  # diagonal distance is sqrt(18), greater than 3 px
    path = tmp_path / "diagonal.tif"
    save(path, registry)
    entry = compare(mine, {"diagonal": path}, np.ones_like(mine, dtype=bool))[0]
    assert entry.frac3px == 0.0

    registry.fill(0)
    registry[1, 4] = 1  # exactly 3 px away, so it is inside the inclusive tolerance
    save(path, registry)
    entry = compare(mine, {"horizontal": path}, np.ones_like(mine, dtype=bool))[0]
    assert entry.frac3px == 1.0


def test_registry_support_outside_footprint_cannot_trip_overlap(tmp_path):
    profile = {
        "driver": "GTiff", "height": 9, "width": 9, "count": 1,
        "dtype": "float32", "transform": from_origin(0, 900, 100, 100),
        "crs": "EPSG:32611", "nodata": -9999,
    }
    mine = np.zeros((9, 9), dtype=np.float32)
    mine[1, 1] = 1
    registry = np.zeros_like(mine)
    registry[1, 4] = 1
    footprint = np.ones_like(mine, dtype=bool)
    footprint[1, 4] = False
    path = tmp_path / "outside-footprint.tif"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(registry, 1)
    entry = compare(mine, {"outside": path}, footprint)[0]
    assert entry.positive_cells == 0
    assert entry.frac3px == 0.0


def test_uniqueness_cli_does_not_certify_an_empty_registry(tmp_path):
    profile = {
        "driver": "GTiff", "height": 9, "width": 9, "count": 1,
        "dtype": "float32", "transform": from_origin(0, 900, 100, 100),
        "crs": "EPSG:32611", "nodata": -9999,
    }
    candidate = np.zeros((9, 9), dtype=np.float32)
    candidate[4, 4] = 1
    raster = tmp_path / "candidate.tif"
    with rasterio.open(raster, "w", **profile) as dst:
        dst.write(candidate, 1)
    registry = tmp_path / "empty-registry"
    registry.mkdir()
    output = tmp_path / "gate.json"
    subprocess.run([
        sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "check_uniqueness.py"),
        "--raster", str(raster), "--registry", str(registry), "--out", str(output),
    ], check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert report["n_registry"] == 0
    assert report["verdict"] == "NOT VERIFIED - EMPTY REGISTRY"
    assert report["protocol_gate"]["passed"] is False
