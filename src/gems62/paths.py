"""Filesystem layout for the 62GEMSDOE lane.

The official competition rasters are ~419 MB and are *not* committed to git
(the repository's ignore conventions keep generated artifacts and large
datasets out).  They live in a local data root that defaults to the
``GEMS62_DATA`` environment variable, then ``<repo>/data``, then the shared
sandbox cache ``~/.cache/gems62/data``.

Every path helper returns a :class:`pathlib.Path`; nothing in this module
invents data.  ``require()`` raises with an actionable message instead of
silently substituting a synthetic fixture.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TRAINING_FEATURES = "training_features.tif"
LABELS = "labels.tif"
SAMPLE_SUBMISSION = "sample_submission.tif"

# sha256 pins published in the sibling-repo data bridge manifest
# (buffedlizard55-lab/6GEMSDOE : data/bridge/manifest.json) and independently
# re-measured here on 2026-10-11.  See registry/data_manifest.json.
SHA256_PINS = {
    TRAINING_FEATURES: "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    LABELS: "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    SAMPLE_SUBMISSION: "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}


def _candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("GEMS62_DATA")
    if env:
        out.append(Path(env).expanduser())
    out.append(REPO_ROOT / "data")
    out.append(Path.home() / ".cache" / "gems62" / "data")
    return out


def data_dir() -> Path:
    """First candidate directory that actually contains the feature raster."""
    for c in _candidates():
        if (c / TRAINING_FEATURES).is_file():
            return c
    return _candidates()[0]


def require(name: str) -> Path:
    for c in _candidates():
        p = c / name
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"{name} not found in any of: {[str(c) for c in _candidates()]}. "
        "Place the official competition rasters there (see "
        "scripts/download_competition_data.sh)."
    )


def out_dir(sub: str = "") -> Path:
    d = REPO_ROOT / "out"
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def docs_dir(sub: str = "") -> Path:
    d = REPO_ROOT / "docs"
    if sub:
        d = d / sub
    d.mkdir(parents=True, exist_ok=True)
    return d
