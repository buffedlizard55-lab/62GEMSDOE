"""Literal lane-drift / uniqueness gate for registry rasters.

Standing protocol: stop if positive-rank Spearman is greater than 0.90 against
any one raster, or if more than 70% of this candidate's positive pixels are
within 3 grid cells (300 m) of that raster's positive pixels. Jaccard, base rate,
and reverse overlap are diagnostic only; none can waive a stop.

A uniqueness clearance is fail-closed: the declared inventory must be complete
for its stated scope, every file must be readable/hash-pinned/on the expected
competition grid, and at least one candidate pixel must be present. The report
never implies that a public owner-repository inventory is the organizer's full
registry.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import Callable

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import rankdata

RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
JACCARD_LIMIT = 0.50  # diagnostic only; never a stop rule
OVERLAP_PX = 3


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt(np.dot(a, a) * np.dot(b, b))
    return float(np.dot(a, b) / den) if den > 0 else float("nan")


def _support(a: np.ndarray, footprint: np.ndarray | None = None) -> np.ndarray:
    out = np.asarray(a) > 0.0
    if footprint is not None:
        out &= np.asarray(footprint, bool)
    return out


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size != a.size:
        return float("nan")
    finite = np.isfinite(a) & np.isfinite(b)
    if int(finite.sum()) < 2:
        return float("nan")
    av = np.asarray(a[finite], np.float64)
    bv = np.asarray(b[finite], np.float64)
    if np.ptp(av) == 0 or np.ptp(bv) == 0:
        return float("nan")
    return _pearson(rankdata(av, method="average"), rankdata(bv, method="average"))


def surface_rho(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
                px: int = OVERLAP_PX) -> dict:
    """Full-footprint Spearman and support diagnostics for two arrays.

    Correlation is signed (a negative association is not a duplicate) and uses
    the full valid footprint, consistent with the protocol's "rank-correlation"
    check. Supports use every strictly positive value, not a 0.5 cutoff.
    """
    m = np.asarray(mine, np.float64)
    o = np.asarray(other, np.float64)
    valid = np.asarray(footprint, bool)
    if m.ndim != 2 or o.shape != m.shape or valid.shape != m.shape:
        raise ValueError("candidate, prior and footprint must share one 2-D grid")
    if not np.isfinite(m[valid]).all() or not np.isfinite(o[valid]).all():
        raise ValueError("non-finite candidate/prior values inside the valid footprint")
    rho_full = _spearman(m[valid], o[valid]) if valid.any() else float("nan")
    mine_b = _support(m, valid)
    other_b = _support(o, valid)
    union = mine_b | other_b
    rho_union = _spearman(m[union], o[union]) if union.any() else float("nan")
    inter = int((mine_b & other_b).sum())
    n_union = int(union.sum())
    jacc = inter / n_union if n_union else 0.0
    d_other = (ndimage.distance_transform_edt(~other_b) if other_b.any()
               else np.full(other_b.shape, np.inf, dtype=np.float64))
    n_mine = int(mine_b.sum())
    within = int((mine_b & (d_other <= px)).sum())
    near = d_other <= px
    base = float(near[valid].mean()) if valid.any() else float("nan")
    frac = within / n_mine if n_mine else 0.0
    return dict(
        spearman_full_footprint=rho_full,
        spearman_on_positive_union=rho_union,
        n_mine=n_mine,
        n_other=int(other_b.sum()),
        n_intersection=inter,
        n_union=n_union,
        n_mine_within_3px=within,
        my_dots_within_3px_of_theirs=frac,
        base_rate_within_3px=base,
        enrichment_vs_base_rate=(frac / base) if base > 0 else None,
        jaccard_dot_sets=jacc,
    )


def dot_overlap(mine: np.ndarray, other: np.ndarray, px: int = OVERLAP_PX,
                footprint: np.ndarray | None = None) -> float:
    """One-sided fraction of candidate positive pixels within ``px`` of a prior.

    No dense-reference exemption or symmetric/Jaccard substitution is applied.
    """
    mine_b = _support(mine, footprint)
    other_b = _support(other, footprint)
    n = int(mine_b.sum())
    if n == 0 or not other_b.any():
        return 0.0
    d = ndimage.distance_transform_edt(~other_b)
    return float((d[mine_b] <= px).mean())


def compare(mine: np.ndarray, other: np.ndarray, footprint: np.ndarray,
            px: int = OVERLAP_PX, eligible: np.ndarray | None = None) -> dict:
    """Compatibility wrapper returning the literal one-sided overlap and rho."""
    report = surface_rho(mine, other, footprint, px=px)
    report["pearson"] = float("nan")
    report["spearman"] = report["spearman_full_footprint"]
    report["frac_dots_within_3px"] = report["my_dots_within_3px_of_theirs"]
    report["eligible_base_rate_within_3px"] = report["base_rate_within_3px"]
    return report


def load_registry(paths, footprint_shape=None):
    """Read listed rasters without skipping errors (legacy convenience API)."""
    out = {}
    for path in paths:
        with rasterio.open(path) as src:
            a = src.read(1)
            if footprint_shape is not None and a.shape != tuple(footprint_shape):
                raise ValueError(f"{path}: grid {a.shape} != {tuple(footprint_shape)}")
            out[pathlib.Path(path).name] = a
    return out


def _file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _expected_grid_error(src, expected_grid) -> str | None:
    if expected_grid is None:
        return None
    shape, crs, transform = expected_grid
    if src.shape != tuple(shape):
        return f"grid shape {src.shape} != expected {tuple(shape)}"
    if src.crs != crs:
        return f"grid CRS {src.crs} != expected {crs}"
    if src.transform != transform:
        return "grid transform differs from expected competition grid"
    return None


def compare_array_to_registry(candidate: np.ndarray, manifest: dict,
                              footprint: np.ndarray, px: int = OVERLAP_PX,
                              expected_grid=None,
                              progress: Callable[[int, int, dict], None] | None = None) -> dict:
    """Apply the literal stop rules to every raster in an explicit inventory.

    Parameters
    ----------
    candidate:
        2-D candidate surface or final prediction. Every value ``> 0`` counts as
        support, including fractional probabilities.
    manifest:
        An inventory with ``declared_scope_complete: true``, an empty ``errors``
        list, and one row per expected raster. A missing/unreadable/hash-mismatched
        file makes the result UNCHECKED and prevents clearance.
    footprint:
        Boolean valid competition footprint.
    expected_grid:
        Optional ``(shape, crs, affine_transform)`` tuple from the sample TIFF.
    progress:
        Optional callback ``(index, total, row)``; errors are reported too.
    """
    c = np.asarray(candidate)
    fp = np.asarray(footprint, bool)
    if c.ndim != 2 or c.shape != fp.shape:
        raise ValueError("candidate and footprint must be matching 2-D arrays")
    if px != OVERLAP_PX:
        raise ValueError("the standing protocol fixes the overlap radius at 3 pixels")

    if not isinstance(manifest, dict):
        manifest = {}
        initial_errors = [{"error": "inventory manifest is not an object"}]
    else:
        raw_errors = manifest.get("errors", [])
        initial_errors = (list(raw_errors) if isinstance(raw_errors, list)
                          else [{"error": "inventory errors field is not a list"}])
    scope_complete = bool(manifest.get("declared_scope_complete", False))
    if not scope_complete:
        initial_errors.append({"error": "inventory is not complete for its declared scope"})
    if not isinstance(manifest.get("rasters"), list) or not manifest.get("rasters"):
        initial_errors.append({"error": "inventory contains no raster records"})
        items = []
    else:
        items = manifest["rasters"]

    candidate_errors = []
    if not np.isfinite(c[fp]).all():
        candidate_errors.append("candidate has non-finite values inside the footprint")
    if np.any((c > 0) & ~fp):
        candidate_errors.append("candidate has positive support outside the footprint")
    candidate_support = _support(c, fp)
    if not candidate_support.any():
        candidate_errors.append("candidate has no positive support")
    if expected_grid is not None and c.shape != tuple(expected_grid[0]):
        candidate_errors.append("candidate shape differs from expected competition grid")

    rows: list[dict] = []
    duplicate_count = 0
    inventory_errors = list(initial_errors)
    total = len(items)
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            raw_path = item.get("cache_file") or item.get("path")
            path_value_ok = isinstance(raw_path, (str, pathlib.Path)) and bool(raw_path)
            fallback_name = pathlib.Path(raw_path).name if path_value_ok else "<missing-path>"
            name = item.get("file") or fallback_name
            row = dict(file=name, sources=item.get("sources", []), sha256=item.get("sha256"))
        else:
            raw_path = None
            path_value_ok = False
            name = f"<invalid-row-{index}>"
            row = dict(file=name, sources=[], sha256=None)
        error = None
        path = pathlib.Path(raw_path) if path_value_ok else None
        if not isinstance(item, dict):
            error = "inventory row is not an object"
        elif path is None:
            error = "inventory row has no valid cache_file/path"
        elif not path.is_file():
            error = f"inventory raster is missing: {path}"
        else:
            try:
                expected_sha = item.get("sha256")
                if (not isinstance(expected_sha, str) or len(expected_sha) != 64
                        or any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha)):
                    error = "inventory row is missing a valid SHA-256 pin"
                else:
                    actual_sha = _file_sha256(path)
                    if actual_sha.lower() != expected_sha.lower():
                        error = "SHA-256 does not match the inventory pin"
                if error is None:
                    with rasterio.open(path) as src:
                        if src.count != 1:
                            error = f"raster has {src.count} bands; expected one"
                        elif src.shape != fp.shape:
                            error = f"raster shape {src.shape} != candidate shape {fp.shape}"
                        else:
                            grid_error = _expected_grid_error(src, expected_grid)
                            if grid_error:
                                error = grid_error
                            else:
                                other = src.read(1)
                                if not np.isfinite(other[fp]).all():
                                    error = "registry raster has non-finite values inside the footprint"
                                else:
                                    st = surface_rho(c, other, fp, px=px)
                                    rho = st["spearman_full_footprint"]
                                    ov = st["my_dots_within_3px_of_theirs"]
                                    duplicate_by_rho = bool(np.isfinite(rho) and rho > RHO_LIMIT)
                                    duplicate_by_overlap = bool(ov > OVERLAP_LIMIT)
                                    duplicate = duplicate_by_rho or duplicate_by_overlap
                                    duplicate_count += int(duplicate)
                                    row.update(
                                        **st,
                                        duplicate_by_rho=duplicate_by_rho,
                                        duplicate_by_overlap=duplicate_by_overlap,
                                        duplicate_by_jaccard=bool(st["jaccard_dot_sets"] > JACCARD_LIMIT),
                                        duplicate=duplicate,
                                    )
            except Exception as exc:  # fail closed; never silently skip one prior
                error = f"{type(exc).__name__}: {exc}"
        if error:
            row["error"] = error
            row["duplicate"] = None
            inventory_errors.append({"file": name, "error": error})
        rows.append(row)
        if progress is not None:
            progress(index, total, row)

    verified = len(rows) == total and total > 0 and not inventory_errors
    unique = bool(verified and not candidate_errors and duplicate_count == 0)
    if candidate_errors:
        verdict = "INVALID_CANDIDATE"
    elif not verified:
        verdict = "UNCHECKED_INCOMPLETE_INVENTORY"
    elif duplicate_count:
        verdict = "DUPLICATE_LANE_DRIFT"
    else:
        verdict = "UNIQUE_WITHIN_DECLARED_ACCESSIBLE_SCOPE"

    comparable = [r for r in rows if "spearman_full_footprint" in r]
    max_rho = max((r["spearman_full_footprint"] for r in comparable
                   if np.isfinite(r["spearman_full_footprint"])), default=None)
    max_overlap = max((r["my_dots_within_3px_of_theirs"] for r in comparable), default=None)
    return dict(
        evidence_class="MEASURED",
        phase="unspecified",
        verdict=verdict,
        unique=unique,
        duplicate_count=duplicate_count,
        candidate_support_pixels=int(candidate_support.sum()),
        rho_limit=RHO_LIMIT,
        overlap_limit=OVERLAP_LIMIT,
        overlap_radius_px=OVERLAP_PX,
        rank_rule="signed full-footprint Spearman > 0.90 against any one raster",
        overlap_rule="more than 70% of candidate positive pixels within 3 pixels of any one raster's positive pixels",
        jaccard_diagnostic_only=True,
        inventory=dict(
            declared_scope_complete=scope_complete,
            organizer_registry_complete=bool(manifest.get("organizer_registry_complete", False)),
            scope=manifest.get("scope"),
            verified=verified,
            raster_count=len(rows),
            error_count=len(inventory_errors),
            errors=inventory_errors,
        ),
        candidate_errors=candidate_errors,
        worst_spearman=max_rho,
        worst_overlap=max_overlap,
        rows=rows,
    )
