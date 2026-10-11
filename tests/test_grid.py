"""Regression tests for the published GeoTIFF contract and the shared writer."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems62 import grid as G, validate  # noqa: E402


@pytest.fixture(scope="module")
def footprint():
    with rasterio.open(G.DEFAULT_SAMPLE) as src:
        return np.isfinite(src.read(1))


def test_writer_emits_nan_outside_and_validates_written_bytes(tmp_path, footprint):
    values = np.zeros(G.SHAPE, dtype=np.float32)
    positions = np.flatnonzero(footprint.ravel())[:3]
    values.ravel()[positions] = 1.0
    path = tmp_path / "candidate.tif"

    receipt = G.write_submission(path, values, footprint=footprint)

    assert receipt["legal"] is True
    assert receipt["meta"]["driver"] == "GTiff"
    assert receipt["checks"]["geotiff"] is True
    assert receipt["failed_checks"] == []
    assert receipt["n_non_finite_inside_footprint"] == 0
    assert receipt["n_non_nan_outside_footprint"] == 0
    assert receipt["n_nan_total"] == int((~footprint).sum())
    assert receipt["meta"]["nodata"] is None
    compat_report = validate.validate_submission(path, footprint)
    assert compat_report.passed is True
    with rasterio.open(path) as src:
        arr = src.read(1)
        assert src.count == 1
        assert src.dtypes == ("float32",)
        assert src.crs.to_epsg() == 32611
        assert src.shape == G.SHAPE
        assert np.isfinite(arr[footprint]).all()
        assert np.isnan(arr[~footprint]).all()
        assert np.array_equal(arr[footprint], values[footprint])


def test_writer_fails_closed_on_bad_shape_and_nodata_tag(footprint, tmp_path):
    with pytest.raises(ValueError, match="footprint shape"):
        G.write_submission(tmp_path / "bad-shape.tif", np.zeros((4, 5)),
                           footprint=np.ones((4, 5), dtype=bool))
    with pytest.raises(ValueError, match="nodata tags are disabled"):
        G.write_submission(tmp_path / "bad-nodata.tif", np.zeros(G.SHAPE),
                           footprint=footprint, nodata=np.nan)


def test_writer_rejects_nonfinite_or_out_of_range_inside(footprint, tmp_path):
    values = np.zeros(G.SHAPE, dtype=np.float32)
    first = int(np.flatnonzero(footprint.ravel())[0])
    values.ravel()[first] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        G.write_submission(tmp_path / "nan-inside.tif", values, footprint=footprint)
    values.ravel()[first] = 1.01
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        G.write_submission(tmp_path / "range-inside.tif", values, footprint=footprint)


def test_compatibility_validator_rejects_old_finite_zeros_outside(footprint):
    path = G.REPO_ROOT / "docs" / "downloads" / "gemsdoe62-datum-lahontan-isobase-v8.tif"
    report = validate.validate_submission(path, footprint)
    assert report.passed is False
    assert "all_nan_outside_footprint" in report.failures
    assert report.nan_inside_footprint == 0
    assert report.nan_outside_footprint == 0


def test_checker_enforces_shape_in_its_legal_gate(tmp_path, footprint):
    path = tmp_path / "wrong-shape.tif"
    with rasterio.open(path, "w", driver="GTiff", height=2, width=3, count=1,
                       dtype="float32", crs=G.CRS, transform=Affine(*G.TRANSFORM)) as dst:
        dst.write(np.zeros((2, 3), dtype=np.float32), 1)
    receipt = G.check_submission(path, footprint=footprint)
    assert receipt["checks"]["shape"] is False
    assert receipt["legal"] is False
    assert "shape" in receipt["failed_checks"]
