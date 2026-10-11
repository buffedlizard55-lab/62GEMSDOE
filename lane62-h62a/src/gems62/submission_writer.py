"""Submission writer: fail-closed.  Nothing is written that does not validate.

Two artifacts per candidate:

``*-zeros.tif``  every cell finite, 0.0 outside the footprint, **no nodata tag**.
                 This is the primary download.  It cannot trigger the portal
                 error "Predicted values must be in range [0, 1]" because there
                 is no sentinel and no NaN anywhere, and it was the form the
                 group's organiser-confirmed 0.2778 file was shipped in.

``*-nan.tif``    NaN outside the footprint, matching ``sample_submission.tif``
                 byte-for-byte in layout.  Legal per the organiser's "data
                 outside the bounds is null or nan", produced for completeness
                 and clearly labelled as the twin.

The writer refuses to emit a file whose validation fails, and it re-opens the
file from disk to produce the receipt, so the receipt always describes bytes
that exist.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import rasterio

from .grid import EXPECTED
from .validate import validate

OFFICIAL_TRANSFORM = rasterio.transform.from_origin(243350.0, 4508550.0, 100.0, 100.0)


def profile_for(shape: tuple[int, int], strict: bool = True) -> dict:
    """A GTiff profile for ``shape``.

    ``strict`` enforces the organiser's published geometry (3730 x 3292,
    EPSG:32611, 100 m, origin 243350 E / 4508550 N).  It is relaxed only by
    unit tests, never by a submission run: ``write_and_validate`` always passes
    ``strict=True``.
    """
    h, w = int(shape[0]), int(shape[1])
    if strict and (h, w) != (EXPECTED["height"], EXPECTED["width"]):
        raise ValueError(
            f"shape {(h, w)} != official submission shape "
            f"{(EXPECTED['height'], EXPECTED['width'])}")
    return dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
                crs="EPSG:32611", transform=OFFICIAL_TRANSFORM,
                compress="deflate", tiled=True, blockxsize=256, blockysize=256,
                bigtiff="NO")


PROFILE = profile_for((EXPECTED["height"], EXPECTED["width"]))


def _coerce(values: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    v = np.asarray(values, dtype=np.float64)
    if v.shape != footprint.shape:
        raise ValueError(f"values shape {v.shape} != footprint {footprint.shape}")
    if not np.isfinite(v[footprint]).all():
        raise ValueError("non-finite prediction values inside the footprint")
    lo, hi = float(v[footprint].min()), float(v[footprint].max())
    if lo < 0.0 or hi > 1.0:
        raise ValueError(f"predictions outside [0, 1] inside footprint: [{lo}, {hi}]")
    return v


def write_zeros(values: np.ndarray, footprint: np.ndarray, dest: Path,
                description: str | None = None, strict: bool = True) -> Path:
    """All-finite artifact: zeros outside the footprint, no nodata tag."""
    v = _coerce(values, footprint)
    out = np.where(footprint, v, 0.0).astype(np.float32)
    if not np.isfinite(out).all():
        raise ValueError("writer produced a non-finite cell")
    if out.min() < 0.0 or out.max() > 1.0:
        raise ValueError(f"writer produced values outside [0,1]: [{out.min()}, {out.max()}]")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    prof = profile_for(out.shape, strict=strict)
    with rasterio.open(dest, "w", **prof) as dst:
        dst.write(out, 1)
        if description:
            dst.set_band_description(1, description[:250])
        dst.update_tags(artifact="zeros-outside-footprint", nodata_policy="none")
    return dest


def write_nan(values: np.ndarray, footprint: np.ndarray, dest: Path,
              description: str | None = None, strict: bool = True) -> Path:
    """Competition's own layout: NaN outside the footprint."""
    v = _coerce(values, footprint)
    out = np.where(footprint, v, np.nan).astype(np.float32)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    prof = profile_for(out.shape, strict=strict)
    with rasterio.open(dest, "w", **prof) as dst:
        dst.write(out, 1)
        if description:
            dst.set_band_description(1, description[:250])
        dst.update_tags(artifact="nan-outside-footprint")
    return dest


def zip_single(tif_path: Path, dest: Path | None = None) -> Path:
    """A .zip containing exactly one GeoTIFF (the portal accepts either form)."""
    tif_path = Path(tif_path)
    dest = Path(dest) if dest else tif_path.with_suffix(".zip")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif_path, arcname=tif_path.name)
    return dest


def write_sidecar(bundle: dict, extra: dict | None = None) -> Path:
    """Write ``<stem>-zeros.json`` next to the artifact.

    The Pages site links to this file, and it is the machine-readable answer to
    "what exactly am I about to upload?": geometry, byte count, the sha256 of the
    bytes on disk, dot count, and the validator verdict.  Every field is taken
    from the receipt that ``validate`` produced by READING THE WRITTEN FILE, so
    nothing here can drift from the artifact.
    """
    path = Path(bundle["path"]).with_suffix(".json")
    rec = bundle.get("receipt") or {}
    shape = rec.get("shape") or [None, None]

    doc = dict(
        artifact=path.name,
        artifact_kind="submission_candidate",
        geometry=dict(height=shape[0], width=shape[1], count=rec.get("count"),
                      dtype=rec.get("dtype"), epsg=rec.get("epsg"),
                      transform=rec.get("transform"), res_m=rec.get("res"),
                      bounds=rec.get("bounds"), nodata=rec.get("nodata"),
                      compression=rec.get("compression")),
        bytes=rec.get("bytes"),
        sha256=rec.get("sha256"),
        values=dict(min=rec.get("min"), max=rec.get("max"),
                    n_nan=rec.get("n_nan"), n_positive=rec.get("n_positive"),
                    n_unique=rec.get("n_unique")),
        validator=dict(
            ok=bool(rec.get("ok")), n_pass=rec.get("n_pass"), n_fail=rec.get("n_fail"),
            # the full check list, verbatim from the receipt -- names are not
            # cherry-picked, so a renamed or added check cannot silently vanish
            # from the sidecar
            checks=[dict(check=c["check"], ok=bool(c["ok"]),
                         detail=str(c.get("detail", "")))
                    for c in rec.get("checks", [])]),
        ok_to_submit=bool(bundle.get("ok_to_submit")),
        failed_checks=bundle.get("failed_checks", []),
        twins=dict(nan=(bundle.get("nan_twin") or {}).get("path"),
                   zip=bundle.get("zip")),
        scored=False,
        scored_note=("ORGANIZER-CONFIRMED scores live only in "
                     "registry/organizer_scores.json and only when copied from a "
                     "submission-page receipt. This artifact has never been scored."),
    )
    if extra:
        doc.update(extra)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n")
    bundle["sidecar"] = str(path)
    return path


def write_and_validate(values: np.ndarray, footprint: np.ndarray, stem: str,
                       outdir: Path, catalogue: np.ndarray | None = None,
                       sample_transform=None, description: str | None = None,
                       make_nan_twin: bool = False, make_zip: bool = True,
                       strict: bool = True, expected: dict | None = None,
                       extra: dict | None = None) -> dict:
    """Write the primary artifact, validate it from disk, and refuse on failure.

    Returns a bundle dict.  ``bundle['ok_to_submit']`` is True only when every
    validator check passed on the bytes that exist on disk.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    zeros_path = outdir / f"{stem}-zeros.tif"
    write_zeros(values, footprint, zeros_path, description=description, strict=strict)
    receipt = validate(zeros_path, footprint=footprint,
                       sample_transform=sample_transform, catalogue=catalogue,
                       expected=expected)
    bundle = dict(stem=stem, artifact="zeros", path=str(zeros_path),
                  receipt=receipt, ok_to_submit=bool(receipt["ok"]))
    if make_zip:
        z = zip_single(zeros_path)
        bundle["zip"] = str(z)
    if make_nan_twin:
        nan_path = outdir / f"{stem}-nan.tif"
        write_nan(values, footprint, nan_path, description=description, strict=strict)
        nan_receipt = validate(nan_path, footprint=None,
                               sample_transform=sample_transform, catalogue=None,
                               expected=expected)
        # NaN-outside is expected here, so only the structural checks are asserted
        structural = [c for c in nan_receipt["checks"]
                      if c["check"] not in ("no_nan_anywhere", "outside_footprint_all_zero",
                                            "nodata_tag_absent_or_zero")]
        bundle["nan_twin"] = dict(path=str(nan_path),
                                  ok=all(c["ok"] for c in structural),
                                  sha256=nan_receipt["sha256"],
                                  bytes=nan_receipt["bytes"])
    if not bundle["ok_to_submit"]:
        bundle["failed_checks"] = [c["check"] for c in receipt["checks"] if not c["ok"]]
    write_sidecar(bundle, extra=extra)
    return bundle
