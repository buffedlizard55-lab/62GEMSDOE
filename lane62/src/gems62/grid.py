"""The competition grid contract, read from the organiser's own template bytes.

Every value below was measured from `data/official/sample_submission.tif`
(sha256 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc)
and `data/official/existing_faults.tif`
(sha256 7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093)
on 2026-10-11 with rasterio 1.4.4.  See scripts/prepare_data.py --check.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

HEIGHT = 3730
WIDTH = 3292
CRS = "EPSG:32611"
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
RES_M = 100.0
TOTAL_CELLS = HEIGHT * WIDTH           # 12,279,160
FOOTPRINT_PX = 5_167_373               # finite cells of sample_submission.tif
CATALOGUE_PX = 60_988                  # existing_faults == 1
PIXEL_M = 100.0
KERNEL_RADIUS_PX = 3.0

SAMPLE_SUBMISSION_SHA256 = "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"
EXISTING_FAULTS_SHA256 = "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@dataclass
class Grid:
    """Immutable read of the three organiser rasters."""
    footprint: np.ndarray      # bool (H, W) finite cells of sample_submission
    catalogue: np.ndarray      # bool (H, W) existing_faults == 1
    catalogue_nodata: np.ndarray  # bool (H, W) existing_faults == -1
    template: np.ndarray       # float32 (H, W) sample_submission values
    transform: tuple
    crs: str

    @property
    def active(self) -> np.ndarray:
        """Scored domain: footprint AND NOT catalogue (organiser masking rule)."""
        return self.footprint & ~self.catalogue


def official_path(root: str | Path, name: str) -> Path:
    """Resolve one of the three official rasters, with a documented fallback chain.

    IR-62-12 FIX (2026-10-11).  ``load_grid`` hard-coded ``data/official/``, which only
    exists after ``scripts/download_competition_data.sh`` has run *inside* ``lane62/``.  The
    same three rasters are also committed at the repository root (``<repo>/data/``, sha256
    pinned in ``registry/data_pins.json``), and when the lane suite is run from a fresh
    checkout 14 tests errored with ``No such file or directory`` for a file that *was*
    present.  The chain below is: ``lane62/data/official/`` (the lane's own pinned copy),
    then ``<repo>/data/`` (the shared pinned copy), and only then the historical relative
    path so the original error message is unchanged when neither exists.  The bytes are the
    same hash in both places, so this changes nothing about what is measured.
    """
    # ``.resolve()`` is load-bearing: ``Path(".").parent`` is ``Path(".")``, so without it
    # the parent-directory fallback silently pointed back at the lane root and the chain
    # returned the missing candidate (found while re-running the suite, 2026-10-11).
    root = Path(root).resolve()
    cands = [root / "data/official" / name,
             root.parent / "data" / name,
             root / "data" / name]
    for c in cands:
        if c.exists():
            return c
    return cands[0]


def load_grid(root: str | Path = ".") -> Grid:
    root = Path(root)
    with rasterio.open(official_path(root, "sample_submission.tif")) as d:
        tmpl = d.read(1)
        assert d.height == HEIGHT and d.width == WIDTH, (d.height, d.width)
        assert str(d.crs) == CRS, d.crs
        assert tuple(d.transform)[:6] == TRANSFORM, tuple(d.transform)
    with rasterio.open(official_path(root, "existing_faults.tif")) as d:
        ex = d.read(1)
        assert d.height == HEIGHT and d.width == WIDTH
        assert tuple(d.transform)[:6] == TRANSFORM
    return Grid(footprint=np.isfinite(tmpl), catalogue=(ex == 1),
                catalogue_nodata=(ex == -1), template=tmpl,
                transform=TRANSFORM, crs=CRS)
