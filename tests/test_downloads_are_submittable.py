"""Every GeoTIFF offered for download must be one the portal can accept.

This test is the structural fix for the complaint that a file downloaded from the
site was rejected by the submission form with

    "Predicted values must be in range [0, 1]"

The two files that produced that error carried NaN outside the survey footprint
(measured: 7,111,787 NaN cells each, exactly the number of out-of-footprint cells).
They now live in ``docs/downloads/quarantined-not-submittable/`` and this test
sweeps ``docs/downloads/*.tif`` -- it does not recurse -- so a non-conforming file
cannot be re-introduced next to the download buttons without failing CI.

The checks are made on the bytes **re-read from disk**, never on an in-memory array,
because the whole failure mode is a property of the file, not of the array.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / "docs" / "downloads"
SAMPLE = ROOT / "data" / "sample_submission.tif"

EXPECTED_SHAPE = (3730, 3292)
EXPECTED_CRS = "EPSG:32611"


def _offered() -> list[pathlib.Path]:
    return sorted(p for p in DOWNLOADS.glob("*.tif"))


def test_download_directory_is_not_empty() -> None:
    assert _offered(), "no download candidates found; the site's hero would 404"


@pytest.mark.parametrize("path", _offered(), ids=lambda p: p.name)
def test_offered_file_is_portal_legal(path: pathlib.Path) -> None:
    with rasterio.open(path) as src:
        arr = src.read(1)
        assert src.count == 1, (path.name, src.count)
        assert src.dtypes[0] == "float32", (path.name, src.dtypes[0])
        assert src.shape == EXPECTED_SHAPE, (path.name, src.shape)
        assert str(src.crs) == EXPECTED_CRS, (path.name, str(src.crs))
        # the sample submission defines the geotransform; compare to 1e-6
        with rasterio.open(SAMPLE) as ref:
            assert all(abs(a - b) < 1e-6 for a, b in zip(tuple(src.transform)[:6],
                                                         tuple(ref.transform)[:6])), path.name
        # mechanism 1: a nodata tag
        assert src.nodata is None or not np.isnan(float(src.nodata)), (
            f"{path.name}: NaN nodata tag -> the portal's range check fails")
    # mechanism 2: NaN values anywhere in the array
    nan_count = int(np.isnan(arr).sum())
    assert nan_count == 0, f"{path.name}: {nan_count} NaN cells"
    # the range itself
    assert int(((arr < 0) | (arr > 1)).sum()) == 0, f"{path.name}: values outside [0, 1]"
    assert np.isfinite(arr).all(), path.name


def test_quarantined_nan_files_are_out_of_the_download_directory() -> None:
    """The two culprits are documented, and they are not offered."""
    q = DOWNLOADS / "quarantined-not-submittable"
    names = {p.name for p in q.glob("*.tif")}
    assert any("nan" in n for n in names), (
        "the quarantined NaN file that caused the portal error is missing; "
        "if it was deleted, delete this assertion deliberately and say so")
    offered = {p.name for p in _offered()}
    assert not (names & offered), "a quarantined file is being offered for download"
