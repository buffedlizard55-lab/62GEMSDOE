"""Strict lane-drift / duplicate checks against registered rasters.

The assignment's two stop conditions are applied literally to *every* comparable registry
raster: Spearman rho > 0.90, or more than 70% of the candidate's positive cells within 3 px of
the comparator's positive cells.  The latter is the asymmetric fraction named in the protocol.
Footprint coverage is retained only as context; it never exempts a dense comparator.  A strict
failure is a stop, not an organizer duplicate ruling.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

from .grid import sha256

TOLERANCE_PX = 3.0
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
    rank_flag: bool
    overlap_flag: bool
    comparable: bool = True
    error: str | None = None


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def compare(
    mine: np.ndarray,
    registry_paths: dict[str, str | Path],
    footprint: np.ndarray,
    *,
    expected_crs: str | None = None,
    expected_transform: tuple[float, ...] | None = None,
    fail_fast: bool = False,
) -> list[RegistryEntry]:
    """Compare a candidate surface or dot raster with registry rasters.

    ``frac3px`` is the fraction of candidate-positive cells within a Euclidean 3-pixel radius
    of any positive registry cell. ``coverage3px`` is reported as a diagnostic only and never
    removes a raster from the strict test. If expected georeferencing is supplied, mismatched
    rasters are recorded as uncomparable. ``fail_fast`` stops after the first strict violation.
    """
    values = np.asarray(mine, dtype=np.float64)
    foot = np.asarray(footprint, dtype=bool)
    if values.ndim != 2 or foot.shape != values.shape:
        raise ValueError("candidate and footprint must be matching 2-D arrays")
    mine_pos = foot & np.isfinite(values) & (values > 0)
    mine_clean = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    fr, fc = np.nonzero(foot)
    if not fr.size:
        raise ValueError("footprint has no cells")
    rng = np.random.default_rng(62)
    sample_idx = rng.choice(fr.size, size=min(10000, fr.size), replace=False)
    bg = (fr[sample_idx], fc[sample_idx])

    entries: list[RegistryEntry] = []
    for alias, raw_path in sorted(registry_paths.items()):
        p = Path(raw_path)
        if not p.is_file():
            entries.append(RegistryEntry(alias, str(p), "", 0, float("nan"), 0.0, 0.0,
                                          False, False, False, False, "file not found"))
            continue
        try:
            with rasterio.open(p) as src:
                other = src.read(1).astype(np.float64)
                other_crs = str(src.crs)
                other_transform = tuple(float(x) for x in src.transform[:6])
        except Exception as exc:
            entries.append(RegistryEntry(alias, str(p), "", 0, float("nan"), 0.0, 0.0,
                                          False, False, False, False, str(exc)))
            continue
        if other.shape != values.shape:
            entries.append(RegistryEntry(alias, str(p), sha256(p), 0, float("nan"), 0.0, 0.0,
                                          False, False, False, False,
                                          f"shape mismatch: {other.shape} != {values.shape}"))
            continue
        if expected_crs is not None and other_crs != expected_crs:
            entries.append(RegistryEntry(alias, str(p), sha256(p), 0, float("nan"), 0.0, 0.0,
                                          False, False, False, False,
                                          f"CRS mismatch: {other_crs} != {expected_crs}"))
            continue
        if (expected_transform is not None and
                other_transform != tuple(float(x) for x in expected_transform[:6])):
            entries.append(RegistryEntry(alias, str(p), sha256(p), 0, float("nan"), 0.0, 0.0,
                                          False, False, False, False,
                                          "transform mismatch"))
            continue

        other_pos = foot & np.isfinite(other) & (other > 0)
        other_clean = np.nan_to_num(other, nan=0.0, posinf=0.0, neginf=0.0)
        rr, cc = np.nonzero(mine_pos | other_pos)
        if rr.size:
            a = np.concatenate([mine_clean[rr, cc], mine_clean[bg]])
            b = np.concatenate([other_clean[rr, cc], other_clean[bg]])
            rho = _spearman(a, b)
        else:
            rho = float("nan")

        if mine_pos.any() and other_pos.any():
            distance = ndimage.distance_transform_edt(~other_pos)
            frac3px = float((distance[mine_pos] <= TOLERANCE_PX).mean())
            coverage3px = float(((distance <= TOLERANCE_PX) & foot).sum() / foot.sum())
        else:
            frac3px = 0.0
            coverage3px = 0.0

        entry = RegistryEntry(
            alias=alias,
            path=str(p),
            sha256=sha256(p),
            positive_cells=int(other_pos.sum()),
            rho=rho,
            frac3px=frac3px,
            coverage3px=coverage3px,
            vacuous=coverage3px >= OVERLAP_LIMIT,  # diagnostic only
            rank_flag=bool(np.isfinite(rho) and rho > RHO_LIMIT),
            overlap_flag=bool(frac3px > OVERLAP_LIMIT),
        )
        entries.append(entry)
        if fail_fast and (entry.rank_flag or entry.overlap_flag):
            break
    return entries


def verdict(entries: list[RegistryEntry]) -> dict:
    """Apply strict thresholds; dense rasters are not excluded from the overlap test."""
    comparable = [e for e in entries if e.comparable]
    finite_rho = [e.rho for e in comparable if np.isfinite(e.rho)]
    max_rho = max(finite_rho, default=float("nan"))
    max_abs_rho = max((abs(r) for r in finite_rho), default=float("nan"))
    max_frac = max((e.frac3px for e in comparable), default=0.0)
    rho_trip = any(e.rank_flag for e in comparable)
    overlap_trip = any(e.overlap_flag for e in comparable)
    incomplete = len(comparable) != len(entries) or not comparable or not finite_rho

    if rho_trip or overlap_trip:
        label = "DUPLICATE - STOP"
    elif incomplete:
        label = "REVIEW INCOMPLETE"
    else:
        label = "NO STRICT TRIPWIRE"
    return {
        "n_registry": len(entries),
        "n_comparable": len(comparable),
        "n_uncomparable": len(entries) - len(comparable),
        "n_vacuous_diagnostic_only": sum(e.vacuous for e in comparable),
        "max_rank_corr": max_rho,
        "max_abs_rank_corr_diagnostic": max_abs_rho,
        "rho_limit_strictly_greater_than": RHO_LIMIT,
        "max_frac3px_all": max_frac,
        "worst_overlap_alias": (max(comparable, key=lambda e: e.frac3px).alias
                                 if comparable else None),
        "overlap_limit_strictly_greater_than": OVERLAP_LIMIT,
        "tolerance_px": TOLERANCE_PX,
        "rho_trip": bool(rho_trip),
        "overlap_trip": bool(overlap_trip),
        "vacuous_is_diagnostic_only": True,
        "passed": bool(not rho_trip and not overlap_trip and not incomplete),
        "verdict": label,
    }


def dump(entries: list[RegistryEntry], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"entries": [asdict(e) for e in entries],
                               "verdict": verdict(entries)}, indent=1, allow_nan=True))
