"""Compatibility wrapper around the canonical ``gems62.grid`` submission validator.

All format rules live in ``grid.check_submission`` so old call sites cannot keep accepting
finite-zero outside masks while the shared writer requires NaN there. A local pass is never an
organizer acceptance receipt.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rasterio

from .grid import check_submission, sha256


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    """Backwards-compatible spelling for the shared file-hash helper."""
    return sha256(path)


@dataclass
class ValidationReport:
    path: str
    sha256: str
    bytes: int
    count: int
    dtype: str
    crs: str
    shape: tuple[int, int]
    transform: tuple[float, ...]
    nodata: float | None
    values_min: float
    values_max: float
    nan_inside_footprint: int
    nan_outside_footprint: int
    outside_encoding: str
    positive_cells: int
    max_positive_value: float
    unique_positive_values: list[float]
    passed: bool
    failures: list[str]
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, default=str)


def validate_submission(path: str | Path, footprint: np.ndarray,
                        *, expected_positive_values: tuple[float, ...] = (1.0,)) -> ValidationReport:
    """Validate using the same fail-closed contract as ``grid.write_submission``."""
    path = Path(path)
    receipt = check_submission(path, footprint=footprint)
    with rasterio.open(path) as src:
        arr = src.read(1)
    foot = np.asarray(footprint, dtype=bool)
    inside = arr[foot]
    outside = arr[~foot]
    finite_inside = inside[np.isfinite(inside)]
    positives = inside[np.isfinite(inside) & (inside > 0)]
    unique = np.unique(positives).astype(float).tolist() if positives.size else []
    notes: list[str] = []
    if expected_positive_values and unique:
        unexpected = [v for v in unique if v not in expected_positive_values]
        if unexpected:
            notes.append(f"positive values beyond {expected_positive_values}: {unexpected[:5]}")

    meta = receipt["meta"]
    return ValidationReport(
        path=str(path),
        sha256=receipt["sha256"],
        bytes=receipt["bytes"],
        count=meta["count"],
        dtype=meta["dtype"],
        crs=meta["crs"],
        shape=tuple(meta["shape"]),
        transform=tuple(meta["transform"]),
        nodata=meta["nodata"],
        values_min=float(finite_inside.min()) if finite_inside.size else float("nan"),
        values_max=float(finite_inside.max()) if finite_inside.size else float("nan"),
        nan_inside_footprint=int((~np.isfinite(inside)).sum()),
        nan_outside_footprint=int((~np.isfinite(outside)).sum()),
        outside_encoding=("all NaN outside the footprint"
                          if receipt["checks"]["all_nan_outside_footprint"]
                          else "not all NaN outside the footprint"),
        positive_cells=int(positives.size),
        max_positive_value=float(positives.max()) if positives.size else 0.0,
        unique_positive_values=unique[:10],
        passed=receipt["legal"],
        failures=list(receipt["failed_checks"]),
        notes=notes,
    )
