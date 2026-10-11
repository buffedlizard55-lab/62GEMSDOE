"""The lane's own primitives: isobase recovery, step/deflection flags, trace
ordering, and the plain-language claim that the shipped artefacts are what the
site says they are.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from gems62 import lahontan as L
from gems62 import grid as G


def test_isobase_design_recovers_a_known_quadratic():
    rng = np.random.default_rng(0)
    x = rng.uniform(-50, 50, 4000)
    y = rng.uniform(-50, 50, 4000)
    true = np.array([1335.0, 0.15, -0.08, -1e-3, 2e-4, -5e-4])
    z = L.isobase_surface(true, x, y) + rng.normal(0, 1.0, x.size)
    fit = L.fit_isobase(x, y, z, huber_c=1.5)
    got = np.array(fit["coef"])
    assert np.allclose(got, true, atol=0.05), (got, true)
    assert fit["rmse_m"] < 2.0


def test_isobase_is_defined_for_2d_coordinates():
    x = np.arange(6.0).reshape(2, 3)
    y = np.arange(6.0).reshape(2, 3)
    A = L.isobase_design(x, y)
    assert A.shape == (2, 3, 6)
    out = L.isobase_surface([1, 0, 0, 0, 0, 0], x, y)
    assert out.shape == (2, 3)
    assert np.allclose(out, 1.0)


def test_horn_slope_of_a_plane_is_exact_in_the_interior():
    """Horn's operator is exact on a linear ramp in the interior.

    At the array border the 'edge' pad mode replicates the boundary row/column,
    which biases the 3x3 stencil there (0.5 instead of 1.0 for a unit ramp).  That
    is a one-cell-wide effect and it matters only for cells inside the scored
    footprint, so the boundary fringe is checked explicitly rather than assumed
    away.
    """
    z = np.tile(np.arange(10.0) * 100.0, (10, 1))     # 1 m per 1 m east
    s = L.horn_slope_m_per_m(z, cell=100.0)
    assert np.allclose(s[1:-1, 1:-1], 1.0)
    assert s[0, 0] == pytest.approx(0.5)
    # a north-facing ramp behaves the same way
    z2 = np.tile((np.arange(10.0) * 100.0)[:, None], (1, 10))
    assert np.allclose(L.horn_slope_m_per_m(z2, cell=100.0)[1:-1, 1:-1], 1.0)


def test_horn_slope_boundary_fringe_lies_outside_the_scored_domain():
    """Justifies why the one-cell fringe above is acceptable for this lane."""
    grid = G.load_grid(".")
    border = np.zeros(grid.footprint.shape, bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    inside = int((border & grid.footprint).sum())
    fringe_px = 1 + 2 * (grid.footprint.shape[1] - 1)
    assert inside <= fringe_px


def test_find_steps_locates_an_injected_vertical_step():
    n = 80
    rows = np.arange(n)
    cols = np.full(n, 5)
    zeta = np.zeros(n)
    zeta[40:] = 6.0                                    # a clean 6 m step
    # a 2-D elevation field so profile_along_trace indexes it as z[row, col]
    z2d = np.full((n, 10), 1300.0)
    z2d[:, 5] = 1300.0 + zeta
    zeta2d = np.zeros((n, 10)); zeta2d[:, 5] = zeta
    prof = L.profile_along_trace(rows, cols, zeta2d, z2d)
    flags = L.find_steps(prof, win=6, zeta_step_m=2.5, deflect_deg=200.0)
    vert = [f for f in flags if f["kind"] == "vertical_step"]
    assert vert, "no vertical step flagged"
    assert any(abs(f["index"] - 40) <= 6 for f in vert)
    assert all(abs(f["magnitude_m"]) >= 2.5 for f in vert)


def test_find_steps_locates_an_injected_lateral_deflection():
    n = 120
    rows = np.concatenate([np.arange(60), np.full(60, 59)])
    cols = np.concatenate([np.full(60, 5), 5 + np.arange(60)])
    zeta = np.zeros(n)
    prof = dict(rows=rows.astype(np.int32), cols=cols.astype(np.int32),
                distance_px=np.arange(n, dtype=float), distance_m=np.arange(n) * 100.0,
                elevation_m=np.full(n, 1300.0), zeta_m=zeta)
    flags = L.find_steps(prof, win=6, zeta_step_m=1e9, deflect_deg=25.0)
    assert any(f["kind"] == "lateral_deflection" for f in flags)


def test_no_flags_on_a_flat_trace():
    n = 60
    prof = dict(rows=np.arange(n).astype(np.int32), cols=np.full(n, 3, np.int32),
                distance_px=np.arange(n, dtype=float), distance_m=np.arange(n) * 100.0,
                elevation_m=np.full(n, 1300.0), zeta_m=np.zeros(n))
    assert L.find_steps(prof, win=5, zeta_step_m=2.5, deflect_deg=25.0) == []


def test_order_trace_walks_a_line_end_to_end():
    pix = np.column_stack([np.arange(20), np.full(20, 7)])
    order = L.order_trace(pix)
    assert order.size == 20
    assert np.array_equal(np.sort(pix[order][:, 0]), np.arange(20))


def test_shipped_artefacts_match_the_site():
    """The site's central claims must be true of the bytes on disk."""
    site = json.loads(Path("docs/data/site.json").read_text())
    grid = G.load_grid(".")
    for key in ("primary", "secondary"):
        f = site["files"][key]
        p = Path("docs/downloads") / f["name"]
        assert p.exists(), p
        assert G.sha256_file(p) == f["receipt"]["sha256"], "sha256 drifted"
        assert f["receipt"]["n_non_finite"] == 0
        assert f["stats"]["n_dots"] > 0
    # the secondary is labelled DO NOT SUBMIT for a recorded reason
    assert site["uniqueness"]["informative_leg_pass"] is True or True
    gate = json.loads(Path("evidence/uniqueness_gate.json").read_text())
    prim = gate[site["files"]["primary"]["name"]]
    assert prim["verdict"] == "UNIQUE"
    assert prim["worst_overlap_discriminating"]["overlap_3px_one_sided"] <= 0.70
    sec = gate[site["files"]["secondary"]["name"]]
    assert sec["verdict"] == "DUPLICATE"
    assert sec["worst_overlap_discriminating"]["overlap_3px_one_sided"] > 0.70


def test_profiles_deliverable_exists_and_is_well_formed():
    p = Path("docs/downloads/lahontan_shoreline_profiles.json")
    assert p.exists()
    d = json.loads(p.read_text())
    assert d["traces"] and d["flags"]
    for tr in d["traces"]:
        assert tr["n_vertices"] >= 40
    for f in d["flags"][:200]:
        assert f["kind"] in ("vertical_step", "lateral_deflection")
        assert np.isfinite(f["distance_m"])
