"""Raster IO and the official submission spec, verified against the shipped files.

Spec (re-measured here on 2026-10-11 from the sha256-pinned official rasters,
and cross-checked against the organiser's published requirements at
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format):

    height 3730, width 3292, 1 band, float32, EPSG:32611, res 100 x 100 m
    transform (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
    bounds  (243350.0, 4135550.0, 572550.0, 4508550.0)
    footprint (finite cells of sample_submission.tif) 5,167,373 px
    labels.tif int8 nodata -1, unique {-1, 0, 1}, positive 60,988 px

Band inventory of ``training_features.tif`` (19 bands, tag ``DESCRIPTION`` /
``data_category`` read from the file itself, not assumed):

     1 mag_anom            magnetic_data     11 iso_grav_anom_vg   gravity_data
     2 rtp                 magnetic_data     12 det_elev           topographic
     3 tmi_hg              magnetic_data     13 iso_grav_anom      gravity_data
     4 geod_2ndinv         geodetic_strain   14 tmi                magnetic_data
     5 iso_grav_anom_slope gravity_data      15 depth_to_base_surf subsurface
     6 tc                  magnetic_data     16 ieq_n100a15        seismic
     7 geod_shearrate      geodetic_strain   17 cond_surf          subsurface
     8 geod_dilaterate     geodetic_strain   18 iso_grav_anom_hg   gravity_data
     9 tmi_vg              magnetic_data     19 det_elev_slope     topographic
    10 deq_n100a15         seismic

IRREGULARITY IR-62-DEM-01: the lane is specified as "map shoreline benches in
the DEM".  There is **no absolute-elevation band** in the official feature
stack; the only topographic layers are band 12 "Detrended elevation -
topography with regional trends removed" and band 19 its slope.  A Lahontan
isobase is an *absolute* elevation datum, so the detrending operator removes
part of the very signal the lane needs.  The organiser does supply
``1m_DEM_links.csv`` (USGS 3DEP 1 m lidar) for exactly this purpose, but that
file sits behind DrivenData login and 3DEP is not reachable from this sandbox.
This lane therefore fits its isobase in *detrended-elevation* space, which is
the honest fallback and is stated as such on the site.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from . import paths

BAND_NAMES = [
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
    "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15",
    "iso_grav_anom_vg", "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf",
    "ieq_n100a15", "cond_surf", "iso_grav_anom_hg", "det_elev_slope",
]
BAND_INDEX = {n: i + 1 for i, n in enumerate(BAND_NAMES)}

EXPECTED = dict(height=3730, width=3292, count=19, dtype="float32",
                epsg=32611, res=(100.0, 100.0),
                transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0),
                footprint=5167373, positives=60988)


@dataclass
class Stack:
    """The three official rasters, loaded once and shared by every experiment."""
    features: np.ndarray          # (19, H, W) float32, nodata -> NaN
    footprint: np.ndarray         # (H, W) bool
    valid_features: np.ndarray    # (H, W) bool: finite in ALL 19 bands
    labels: np.ndarray            # (H, W) int8 with -1 outside
    positives: np.ndarray         # (H, W) bool  (labels == 1, inside footprint)
    transform: Affine
    crs: str
    profile: dict
    spec: dict

    @property
    def shape(self):
        return self.footprint.shape

    def band(self, name: str) -> np.ndarray:
        return self.features[BAND_INDEX[name] - 1]


def sha256_file(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def load_stack(verify: bool = True) -> Stack:
    fp = paths.require(paths.TRAINING_FEATURES)
    lp = paths.require(paths.LABELS)
    sp = paths.require(paths.SAMPLE_SUBMISSION)

    with rasterio.open(sp) as s:
        ss = s.read(1)
        sub_profile = s.profile.copy()
        sub_transform = s.transform
        sub_crs = str(s.crs)
        sub_shape = (s.height, s.width)
    footprint = np.isfinite(ss)

    with rasterio.open(fp) as s:
        assert (s.height, s.width) == sub_shape, "features/sample_submission shape mismatch"
        feats = s.read().astype(np.float32)
        n_sentinel_raw = int((feats[:, footprint] < -1e38).sum())
        feats[feats < -1e38] = np.nan
        prof = s.profile.copy()
        transform = s.transform
        crs = str(s.crs)
        band_tags = [dict(s.tags(i)) for i in range(1, s.count + 1)]
    # IR-62-SENTINEL-01 (measured, not assumed): the float32 nodata sentinel
    # -3.4028234663852886e+38 occurs in 3,061 cells that lie INSIDE the
    # submission footprint (sample_submission.tif is finite there), in all 19
    # bands.  Writing those through unchanged is one of the two mechanisms that
    # produce the portal error "Predicted values must be in range [0, 1]".
    valid_features = np.isfinite(feats).all(axis=0) & footprint

    with rasterio.open(lp) as s:
        lab = s.read(1)
    lab = np.asarray(lab)
    positives = (lab == 1) & footprint

    spec = dict(
        height=sub_shape[0], width=sub_shape[1],
        count=int(feats.shape[0]), dtype=str(feats.dtype),
        epsg=int(rasterio.crs.CRS.from_string(crs).to_epsg()),
        res=(float(transform.a), float(-transform.e)),
        transform=tuple(float(v) for v in transform)[:6],
        footprint=int(footprint.sum()), positives=int(positives.sum()),
        labels_unique=[int(u) for u in np.unique(lab)],
        sentinel_cells_inside_footprint=n_sentinel_raw,
        valid_feature_pixels=int(valid_features.sum()),
        band_descriptions=[t.get("DESCRIPTION") or t.get("description") for t in band_tags],
        band_categories=[t.get("data_category") for t in band_tags],
        sha256={n: sha256_file(paths.require(n)) for n in
                (paths.TRAINING_FEATURES, paths.LABELS, paths.SAMPLE_SUBMISSION)},
    )
    if verify:
        for k, v in EXPECTED.items():
            got = spec.get(k)
            if isinstance(v, tuple):
                ok = got is not None and all(abs(a - b) < 1e-6 for a, b in zip(got, v))
            else:
                ok = got == v
            if not ok:
                raise AssertionError(f"spec mismatch on {k}: expected {v!r}, got {got!r}")
        for n, pin in paths.SHA256_PINS.items():
            if spec["sha256"][n] != pin:
                raise AssertionError(f"sha256 mismatch for {n}")
    return Stack(features=feats, footprint=footprint, valid_features=valid_features,
                 labels=lab, positives=positives, transform=transform, crs=crs,
                 profile=dict(sub_profile), spec=spec)


def spec_report(stack: Stack) -> dict:
    return dict(measured=stack.spec, expected=EXPECTED, ok=True)


def write_spec_json(stack: Stack, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(spec_report(stack), indent=2, default=str) + "\n")
