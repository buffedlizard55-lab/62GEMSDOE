"""Lane-drift / uniqueness checks against every earlier raster we can collect.

The parallel-run protocol for this prompt defines two binding drift conditions:

* **rank correlation** with any registry raster greater than 0.90; or
* **more than 70 % of the candidate's dots within 3 px of any one registry raster's dots**.

This module applies those literal thresholds to every comparator. It also reports a
*vacuity diagnostic*: a registry raster whose 3 px dilation covers a large fraction of the
footprint can cause the dot-overlap rule to trip for candidates that are not substantively
similar. That defect is real, but it does not authorize silently replacing the specified gate
with Jaccard or dropping dense comparators. A trip is recorded as ``DUPLICATE - STOP``; the
vacuity diagnostic is retained so a selector can separately flag that the protocol itself is
uninformative for that comparator.

Per comparator it reports:

* ``rho``         -- Spearman rank correlation of the candidate surface and registry values
* ``frac3px``     -- fraction of candidate positive cells within 3 px of that raster's positives
* ``coverage3px`` -- fraction of the footprint within 3 px of that raster's positives
* ``vacuous``     -- whether the comparator's 3 px dilation blankets at least 70 % of the
                     footprint; diagnostic only, never a reason to suppress a trip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

from .grid import PIXEL_M

#: 3 px at 100 m, the protocol's dot-proximity tolerance.
TOLERANCE_PX = 3
#: Drift limits from the prompt's parallel-run protocol.
RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70


@dataclass
class RegistryEntry:
    alias: str
    path: str
    sha256: str
    positive_cells: int
    rho: float
    frac3px: float
    coverage3px: float
    vacuous: bool


def protocol_verdict(max_rho: float, max_frac3px: float, *,
                     n_comparators: int | None = None,
                     rho_limit: float = RHO_LIMIT,
                     overlap_limit: float = OVERLAP_LIMIT) -> dict:
    """Apply the binding thresholds; density diagnostics cannot suppress a trip.

    With an explicitly empty registry there is no evidence of distinctness, so
    return an unverified verdict rather than treating the absence of comparisons
    as a pass.
    """
    rho_trip = bool(np.isfinite(max_rho) and max_rho > rho_limit)
    overlap_trip = bool(max_frac3px > overlap_limit)
    empty_registry = n_comparators == 0
    passed = not empty_registry and not (rho_trip or overlap_trip)
    verdict = ("NOT VERIFIED - EMPTY REGISTRY" if empty_registry else
               "DUPLICATE - STOP" if rho_trip or overlap_trip else "DISTINCT LANE")
    return dict(rho_trip=rho_trip, overlap_trip=overlap_trip, passed=passed,
                verdict=verdict, rho_limit=rho_limit, overlap_limit=overlap_limit,
                n_comparators=n_comparators)


def _read_mask(path: str | Path) -> np.ndarray:
    with rasterio.open(path) as src:
        arr = src.read(1)
    out = np.zeros(arr.shape, dtype=bool)
    finite = np.isfinite(arr)
    out[finite] = arr[finite] > 0
    return out


def compare(
    mine: np.ndarray,
    registry_paths: dict[str, str | Path],
    footprint: np.ndarray,
) -> list[RegistryEntry]:
    """Compare a candidate surface against a set of registry rasters."""
    from .grid import sha256 as sha256_file

    mine = np.asarray(mine)
    foot = np.asarray(footprint, dtype=bool)
    if mine.shape != foot.shape:
        raise ValueError(f"candidate shape {mine.shape} != footprint shape {foot.shape}")
    mine_bin = np.isfinite(mine) & (mine > 0) & foot
    mine_f = np.where(mine_bin, mine, 0.0).astype(np.float64)

    entries: list[RegistryEntry] = []
    for alias, p in sorted(registry_paths.items()):
        p = Path(p)
        if not p.exists():
            continue
        other = _read_mask(p)
        if other.shape != mine.shape:
            raise ValueError(f"{alias}: shape {other.shape} != {mine.shape}")
        other &= foot

        # Spearman on the full footprint (both surfaces are mostly zero, which is
        # the honest comparison: it measures whether the *surfaces* agree).
        a = mine_f[foot]
        b = (other & foot)[foot].astype(np.float64)
        if a.size and (a.std() > 0) and (b.std() > 0):
            rho = float(spearmanr(a, b).statistic)
        else:
            rho = float("nan")

        # Euclidean pixel distance matches the explicit "within 3 px" protocol;
        # square/Chebyshev dilation would incorrectly include diagonal offsets.
        if other.any():
            distance = ndi.distance_transform_edt(~other)
            near_other = distance <= TOLERANCE_PX
        else:
            near_other = np.zeros_like(other, dtype=bool)
        n_mine = int(mine_bin.sum())
        frac = float((mine_bin & near_other).sum() / n_mine) if n_mine else 0.0
        coverage = float((near_other & foot).sum() / max(foot.sum(), 1))

        entries.append(RegistryEntry(
            alias=alias, path=str(p), sha256=sha256_file(p),
            positive_cells=int((other & foot).sum()),
            rho=rho, frac3px=frac, coverage3px=coverage,
            vacuous=coverage >= OVERLAP_LIMIT,
        ))
    return entries


def verdict(entries: list[RegistryEntry]) -> dict:
    """Apply the literal binding drift rule to *all* registry rasters.

    A dense/vacuous comparator can make the specified overlap test uninformative,
    but it does not alter the protocol threshold. Keep the non-vacuous maximum as
    a diagnostic and let the strict all-comparator result control the verdict.
    """
    non_vacuous = [e for e in entries if not e.vacuous]
    vacuous = [e for e in entries if e.vacuous]
    finite_rho = [e.rho for e in entries if np.isfinite(e.rho)]
    max_rho = max(finite_rho, default=float("nan"))
    max_abs_rho = max((abs(v) for v in finite_rho), default=float("nan"))
    max_frac_nonvac = max((e.frac3px for e in non_vacuous), default=0.0)
    max_frac_all = max((e.frac3px for e in entries), default=0.0)

    # "exceeds 0.90" is positive rank correlation, not absolute correlation.
    protocol = protocol_verdict(max_rho, max_frac_all, n_comparators=len(entries))
    closest = max(entries, key=lambda e: e.frac3px) if entries else None
    closest_non_vacuous = max(non_vacuous, key=lambda e: e.frac3px) if non_vacuous else None
    return {
        "n_registry": len(entries),
        "n_vacuous": len(vacuous),
        "max_rho": max_rho,
        "max_abs_rho": max_abs_rho,
        "max_abs_rho_diagnostic": max_abs_rho,
        "rho_limit": protocol["rho_limit"],
        "max_frac3px_non_vacuous": max_frac_nonvac,
        "max_frac3px_all": max_frac_all,
        "overlap_limit": protocol["overlap_limit"],
        "rho_trip": protocol["rho_trip"],
        "overlap_trip": protocol["overlap_trip"],
        "closest_all": closest.alias if closest else None,
        "closest_non_vacuous": (closest_non_vacuous.alias if closest_non_vacuous else None),
        "vacuous_aliases": [e.alias for e in vacuous],
        "passed": protocol["passed"],
        "verdict": protocol["verdict"],
    }


def dump(entries: list[RegistryEntry], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "entries": [asdict(e) for e in entries],
        "verdict": verdict(entries),
    }
    Path(path).write_text(json.dumps(payload, indent=1))
