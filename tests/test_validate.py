"""The writer must be fail-closed and the validator must catch every clause of
the published submission format.
"""
from __future__ import annotations

import numpy as np
import pytest
import rasterio

from gems62 import grid as G
from gems62.validate import validate_submission, write_submission, dots_on_catalogue


@pytest.fixture(scope="module")
def grid():
    return G.load_grid(".")


def _small_values(shape, footprint):
    v = np.zeros(shape)
    idx = np.flatnonzero(footprint.ravel())[:100]
    v.ravel()[idx] = 1.0
    return v


def test_writer_produces_a_valid_file(tmp_path, grid):
    v = _small_values(grid.footprint.shape, grid.footprint)
    out = tmp_path / "t.tif"
    rep = write_submission(out, v, grid.footprint, outside="zero")
    assert rep["portal_error_cannot_occur"] is True
    assert all(c["ok"] for c in rep["checks"])
    with rasterio.open(out) as d:
        assert d.nodata is None
        assert d.count == 1
        assert str(d.dtypes[0]) == "float32"
        a = d.read(1)
    assert np.isfinite(a).all()
    assert a.min() >= 0 and a.max() <= 1


def test_writer_rejects_out_of_range(tmp_path, grid):
    v = np.zeros(grid.footprint.shape)
    idx = np.flatnonzero(grid.footprint.ravel())[0]
    v.ravel()[idx] = 1.2
    with pytest.raises(ValueError):
        write_submission(tmp_path / "bad.tif", v, grid.footprint)


def test_writer_rejects_nan_inside(tmp_path, grid):
    v = np.zeros(grid.footprint.shape)
    idx = np.flatnonzero(grid.footprint.ravel())[0]
    v.ravel()[idx] = np.nan
    with pytest.raises(ValueError):
        write_submission(tmp_path / "bad.tif", v, grid.footprint)


def test_validator_catches_a_wrong_transform(tmp_path, grid):
    v = _small_values(grid.footprint.shape, grid.footprint)
    out = tmp_path / "t.tif"
    write_submission(out, v, grid.footprint)
    with rasterio.open(out, "r+") as d:
        d.transform = rasterio.Affine(50.0, 0, 243350.0, 0, -50.0, 4508550.0)
    with pytest.raises(AssertionError):
        validate_submission(out, grid.footprint)


def test_validator_catches_a_nodata_tag(tmp_path, grid):
    """Mechanism M2 of the portal error: a nodata tag on the submission."""
    v = _small_values(grid.footprint.shape, grid.footprint)
    out = tmp_path / "t.tif"
    write_submission(out, v, grid.footprint)
    with rasterio.open(out, "r+") as d:
        d.nodata = np.nan
    with pytest.raises(AssertionError):
        validate_submission(out, grid.footprint)


def test_dots_on_catalogue_counts_waste(grid):
    """IR-30-047: mass on a catalogue pixel earns neither TP nor FP."""
    v = np.zeros(grid.footprint.shape)
    cat = np.flatnonzero(grid.catalogue.ravel())[:5]
    free = np.flatnonzero(grid.active.ravel())[:5]
    v.ravel()[cat] = 1.0
    v.ravel()[free] = 1.0
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "t.tif"
        write_submission(out, v, grid.footprint)
        r = dots_on_catalogue(out, grid.catalogue, grid.footprint)
    assert r["n_positive"] == 10
    assert r["n_positive_on_catalogue"] == 5
    assert r["mass_on_catalogue"] == pytest.approx(5.0)


def test_shipped_files_are_valid(grid):
    """Whatever is in docs/downloads must satisfy the contract it claims."""
    from pathlib import Path
    for p in sorted(Path("docs/downloads").glob("*.tif")):
        if "nanoutside" in p.name:
            continue
        rep = validate_submission(p, grid.footprint)
        assert rep["sha256"]
        assert rep["max_inside"] <= 1.0 and rep["min_inside"] >= 0.0
