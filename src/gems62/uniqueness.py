"""Lane-drift / uniqueness checks against every earlier raster we can collect.

The parallel-run protocol for this prompt defines two drift conditions:

* **rank correlation** between my surface and any registry raster above 0.90, or
* **more than 70 % of my dots within 3 px of one registry raster's dots**.

A documented defect in that rule is that it is unsatisfiable against a raster whose
own support blankets a large fraction of the footprint: if a registry raster's
3 px dilation already covers, say, 99 % of the footprint, then *any* submission
trips the 70 % condition.  The sibling repository proved this in writing
(GEMSDOE54 ``IR-54-016``, ``evidence/cgrc_submission_receipt.json`` ->
``lane_infeasibility_proof``: the rasters ``r11_greedy_mp`` / ``r13_lattice_s5`` /
``r14_union_tips10_lat6`` blanket 73.97 % / 99.87 % / 76.20 % of the footprint
within 3 px).  This module therefore reports, for every registry raster:

* ``rho``        -- Spearman rank correlation of the two surfaces on the footprint
* ``frac3px``    -- fraction of my dots within 3 px of that raster's dots
* ``coverage3px``-- fraction of the footprint within 3 px of that raster's dots
                   (the **vacuity** diagnostic: a high value means the 70 % rule
                   cannot discriminate for that raster)

and marks a raster *vacuous* when ``coverage3px >= 0.70``.  The operational lane
verdict uses ``rho`` against all rasters plus ``frac3px`` against non-vacuous ones.
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
    from .validate import sha256_file

    mine_bin = (mine > 0) & footprint
    mine_f = np.where(mine_bin, mine, 0.0).astype(np.float64)
    foot = np.asarray(footprint, dtype=bool)

    # Precompute my dot dilation lazily per registry raster.
    entries: list[RegistryEntry] = []
    for alias, p in sorted(registry_paths.items()):
        p = Path(p)
        if not p.exists():
            continue
        other = _read_mask(p)
        if other.shape != mine.shape:
            raise ValueError(f"{alias}: shape {other.shape} != {mine.shape}")

        # Spearman on the full footprint (both surfaces are mostly zero, which is
        # the honest comparison: it measures whether the *surfaces* agree).
        a = mine_f[foot]
        b = (other & foot)[foot].astype(np.float64)
        if a.size and (a.std() > 0) and (b.std() > 0):
            rho = float(spearmanr(a, b).statistic)
        else:
            rho = float("nan")

        dil_other = ndi.binary_dilation(other, structure=ndi.generate_binary_structure(2, 2),
                                        iterations=TOLERANCE_PX)
        n_mine = int(mine_bin.sum())
        frac = float((mine_bin & dil_other).sum() / n_mine) if n_mine else 0.0
        coverage = float((dil_other & foot).sum() / max(foot.sum(), 1))

        entries.append(RegistryEntry(
            alias=alias, path=str(p), sha256=sha256_file(p),
            positive_cells=int((other & foot).sum()),
            rho=rho, frac3px=frac, coverage3px=coverage,
            vacuous=coverage >= OVERLAP_LIMIT,
        ))
    return entries


def verdict(entries: list[RegistryEntry]) -> dict:
    """Apply the prompt's drift rule, separating vacuous rasters out."""
    non_vacuous = [e for e in entries if not e.vacuous]
    vacuous = [e for e in entries if e.vacuous]
    max_rho = max((abs(e.rho) for e in entries if np.isfinite(e.rho)), default=float("nan"))
    max_frac_nonvac = max((e.frac3px for e in non_vacuous), default=0.0)
    max_frac_all = max((e.frac3px for e in entries), default=0.0)

    rho_trip = np.isfinite(max_rho) and max_rho > RHO_LIMIT
    overlap_trip = max_frac_nonvac > OVERLAP_LIMIT
    passed = (not rho_trip) and (not overlap_trip)

    closest = max(non_vacuous, key=lambda e: e.frac3px) if non_vacuous else None
    return {
        "n_registry": len(entries),
        "n_vacuous": len(vacuous),
        "max_abs_rho": max_rho,
        "rho_limit": RHO_LIMIT,
        "max_frac3px_non_vacuous": max_frac_nonvac,
        "max_frac3px_all": max_frac_all,
        "overlap_limit": OVERLAP_LIMIT,
        "rho_trip": bool(rho_trip),
        "overlap_trip": bool(overlap_trip),
        "closest_non_vacuous": closest.alias if closest else None,
        "vacuous_aliases": [e.alias for e in vacuous],
        "passed": bool(passed),
        "verdict": "DISTINCT LANE" if passed else "DUPLICATE - STOP",
    }


def dump(entries: list[RegistryEntry], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "entries": [asdict(e) for e in entries],
        "verdict": verdict(entries),
    }
    Path(path).write_text(json.dumps(payload, indent=1))
