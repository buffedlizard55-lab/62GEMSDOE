"""Fail-closed GeoTIFF packaging for the GEMS submission.

Ported from the shared template ``gems57.submission_writer`` with one change:
the template's ``gates.format_report`` is replaced by an explicit comparison
against the organiser's ``sample_submission.tif`` read from disk, because this
repository has no ``gates`` module.  Everything else is identical behaviour.

The writer never clips, fills, or otherwise repairs model output.  It validates
in memory, writes to private temporary paths, validates the on-disk TIFF and
ZIP, and only then atomically replaces the requested outputs.  Local format
validity is neither a uniqueness clearance nor organiser acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from . import grid
from .validate import assert_valid, validate


def _temp_path(parent: Path, stem: str, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{stem}.", suffix=suffix, dir=parent)
    os.close(fd)
    return Path(name)


def format_report(path: Path, sample: Path) -> dict:
    """Compare a written TIFF against the organiser's sample submission grid.

    The comparison is made on the file itself, not on the array that produced
    it, because the file is what is uploaded.
    """
    import rasterio

    got = grid.read_geotiff(path)
    want = grid.read_geotiff(sample)
    with rasterio.open(path) as src:
        arr = src.read(1)
    problems = []
    if (got["height"], got["width"]) != (want["height"], want["width"]):
        problems.append(f"shape ({got['height']}, {got['width']}) != "
                        f"template ({want['height']}, {want['width']})")
    if got["crs"] != want["crs"]:
        problems.append(f"crs {got['crs']} != template {want['crs']}")
    if got["transform"] != want["transform"]:
        problems.append(f"transform {got['transform']} != template {want['transform']}")
    if got["bands"] != want["bands"]:
        problems.append(f"band count {got['bands']} != template {want['bands']}")
    if got["dtype"] != want["dtype"]:
        problems.append(f"dtype {got['dtype']} != template {want['dtype']}")
    n_nonzero = int(np.count_nonzero(arr))
    if n_nonzero == 0:
        problems.append("submission is empty")
    return dict(ok=not problems, problems=problems,
                sha256=got["sha256"], bytes=got["bytes"],
                shape=[got["height"], got["width"]], crs=got["crs"],
                transform=got["transform"], count=int(got["bands"]),
                dtype=got["dtype"], n_nonzero=n_nonzero,
                min=float(arr.min()), max=float(arr.max()),
                n_nan=int(np.isnan(arr).sum()), n_inf=int(np.isinf(arr).sum()))


def write_submission(path, prediction, sample, footprint, *, note, name,
                     catalogue=None, metadata=None):
    """Write a locally validated single-band GeoTIFF and a one-TIFF ZIP.

    ``name`` and ``note`` are limited to 140 characters.  The prediction must
    already be a 2-D finite float field in ``[0,1]``, aligned with the
    footprint, with no positive support outside it.  If ``catalogue`` is
    supplied the candidate must also have zero positive pixels on mapped faults.
    """
    if not isinstance(name, str) or not name.strip() or len(name) > 140:
        raise ValueError("name must contain 1..140 non-whitespace characters")
    if not isinstance(note, str) or not note.strip() or len(note) > 140:
        raise ValueError("note must contain 1..140 non-whitespace characters")

    p = np.asarray(prediction)
    fp = np.asarray(footprint, dtype=bool)
    if p.ndim != 2 or p.shape != fp.shape:
        raise ValueError("prediction and footprint must be matching 2-D arrays")
    if not np.issubdtype(p.dtype, np.number):
        raise ValueError("prediction must be numeric")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("prediction must already be normalized, finite and in "
                         "[0,1]; no silent repair")
    if np.any((p > 0) & ~fp):
        raise ValueError("positive prediction mass outside the valid footprint")
    cat = None
    if catalogue is not None:
        cat = np.asarray(catalogue, dtype=bool)
        if cat.shape != p.shape:
            raise ValueError("catalogue shape must match the prediction grid")
        if np.any((p > 0) & cat):
            raise ValueError("positive prediction mass on the mapped catalogue")

    path = Path(path)
    if path.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("submission path must end in .tif or .tiff")
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = Path(sample)
    if not sample.is_file():
        raise FileNotFoundError(f"sample grid does not exist: {sample}")

    zip_path = path.with_suffix(".zip")
    receipt_path = path.with_suffix(".json")
    existing = [c for c in (path, zip_path, receipt_path) if c.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing submission outputs: {existing}")
    tmp_tif = tmp_zip = tmp_receipt = None
    committed = []
    try:
        tmp_tif = _temp_path(path.parent, path.stem, path.suffix)
        tmp_zip = _temp_path(path.parent, path.stem, ".zip")
        tmp_receipt = _temp_path(path.parent, path.stem, ".json")

        # grid.write_geotiff itself rejects shape, dtype, NaN/inf and range drift.
        grid.write_geotiff(tmp_tif, p.astype(np.float32, copy=False), nodata=None)
        report = format_report(tmp_tif, sample)
        if not report["ok"]:
            raise ValueError(f"on-disk template validator rejected output: {report['problems']}")
        local_validation = validate(tmp_tif, fp, cat if cat is not None else np.zeros_like(fp))
        try:
            if not local_validation["all_checks_passed"]:
                failed = [k for k, v in local_validation["checks"].items() if not v]
                raise AssertionError(f"failed checks: {failed}")
            assert_valid(tmp_tif, fp, cat if cat is not None else np.zeros_like(fp))
        except AssertionError as exc:
            raise ValueError(f"on-disk range/format validator rejected output: {exc}") from exc
        if report["n_nonzero"] != int((p > 0).sum()):
            raise ValueError("on-disk positive support changed during serialization")
        local_validation["file"] = str(path)
        report["path"] = str(path)

        # A submission ZIP contains ONLY the one TIFF; evidence stays adjacent.
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            info = zipfile.ZipInfo(path.name, date_time=(2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, tmp_tif.read_bytes())
        with zipfile.ZipFile(tmp_zip) as z:
            if z.namelist() != [path.name] or z.read(path.name) != tmp_tif.read_bytes():
                raise IOError("single-TIFF ZIP roundtrip failed")

        receipt = dict(
            file=path.name,
            sha256=report["sha256"],
            bytes=tmp_tif.stat().st_size,
            submission_name=name,
            note=note,
            note_chars=len(note),
            validator=local_validation,
            template_report=report,
            zip_file=zip_path.name,
            zip_sha256=hashlib.sha256(tmp_zip.read_bytes()).hexdigest(),
            approved_for_weekly_slot=False,
            promoted=False,
            submission_slots_used=0,
            status=("locally validated within separately recorded inventory scope; "
                    "not organizer acceptance or slot approval"),
            metadata=metadata or {},
        )
        tmp_receipt.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n",
                               encoding="utf-8")

        # Stage auxiliary files first and commit the TIFF last as the primary artifact.
        for source, destination in ((tmp_zip, zip_path), (tmp_receipt, receipt_path),
                                    (tmp_tif, path)):
            os.replace(source, destination)
            committed.append(destination)
        return receipt
    except Exception:
        # A failed validation or serialization must never leave a new partial deliverable.
        for destination in committed:
            try:
                destination.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for temporary in (tmp_tif, tmp_zip, tmp_receipt):
            if temporary is None:
                continue
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
