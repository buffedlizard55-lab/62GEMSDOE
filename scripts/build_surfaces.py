#!/usr/bin/env python3
"""Build and cache every intermediate surface the H62-B lane needs, in float32.

The sandbox has ~3 GB of RAM and the competition grid is 12.28 M cells, so the pipeline is
written to keep only one scratch array alive at a time and to cache the results under ``build/``
(git-ignored) instead of recomputing them.  Everything is float32 on disk; the two smoothing
primitives that need extra precision upcast internally and downcast on return.

Outputs (build/surfaces/): base.npy hab.npy slope.npy relief.npy band.npy isobase.npy
resid.npy zscore.npy step.npy defl.npy az_contour.npy coh.npy relief_st.npy az_st.npy
frangi_datum.npy frangi_dem.npy tmi_hg.npy iso_grav_hg.npy rtp.npy geod_2ndinv.npy
geod_shearrate.npy depth_base.npy
"""
from __future__ import annotations

import gc
import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import datum, datum_base as db, emit  # noqa: E402

OUT = ROOT / "build" / "surfaces"


def save(name: str, a: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / f"{name}.npy", np.asarray(a, dtype=np.float32))
    del a
    gc.collect()


def load(name: str) -> np.ndarray:
    return np.load(OUT / f"{name}.npy")


def _pct(a: np.ndarray, lo: float = 2.0, hi: float = 98.0) -> np.ndarray:
    g = np.isfinite(a)
    p1, p2 = np.percentile(a[g], [lo, hi])
    return np.clip((a - p1) / max(p2 - p1, 1e-12), 0.0, 1.0).astype(np.float32)


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    cat = rasterio.open(ROOT / "data/existing_faults.tif").read(1)
    footprint = cat != -1
    np.save(OUT / "footprint.npy", footprint)
    np.save(OUT / "catalogue.npy", (cat == 1) & footprint)
    del cat
    gc.collect()

    z = rasterio.open(ROOT / "data/geodawn_dem_a2_100m.tif").read(1).astype(np.float32)
    z[z < -99999] = np.nan
    z = np.where(footprint, z, np.nan)
    save("dem", z)
    print(f"dem {time.time()-t0:.0f}s", flush=True)

    base = db.base_level(z.astype(np.float32))
    save("base", base)
    hab = db.height_above_base(z, base)
    save("hab", hab)
    del hab
    gc.collect()
    print(f"base {time.time()-t0:.0f}s", flush=True)

    slope = db.horn_slope(z).astype(np.float32)
    save("slope", slope)
    relief = db.local_relief(z).astype(np.float32)
    relief = np.where(footprint, relief, np.nan)
    save("relief", relief)
    band = db.pluvial_band(db.height_above_base(z, base), slope, relief)
    save("band", band)
    print(f"band {int(band.sum())} px  {time.time()-t0:.0f}s", flush=True)
    del slope, relief
    gc.collect()

    iso = db.isobase(base, band).astype(np.float32)
    save("isobase", iso)
    resid = (base - iso).astype(np.float32)
    save("resid", resid)
    print(f"isobase {time.time()-t0:.0f}s", flush=True)

    zs, step = db.robust_step(resid.astype(np.float64), band)
    save("zscore", zs)
    save("step", step)
    del zs, step
    gc.collect()
    print(f"step flags {time.time()-t0:.0f}s", flush=True)

    az_c = db.contour_azimuth(base).astype(np.float32)
    save("az_contour", az_c)
    defl = db.deflection(az_c.astype(np.float64), band)
    save("defl", defl)
    del az_c, defl
    gc.collect()
    print(f"deflection {time.time()-t0:.0f}s", flush=True)

    az_st, coh, rel_st = emit.structure_tensor(z.astype(np.float64), footprint, sigma_px=5.0)
    save("az_st", az_st)
    save("coh", coh)
    save("relief_st", rel_st)
    del az_st, coh, rel_st
    gc.collect()
    print(f"structure tensor {time.time()-t0:.0f}s", flush=True)

    # Frangi on |grad resid| = "the pluvial datum is offset here"; on |grad z| = "there is a
    # scarp here".  Both polarities are kept; the difference between them is the lane's content.
    gr = np.hypot(*np.gradient(np.where(np.isfinite(resid), resid, 0.0).astype(np.float32)))
    fr, _ = datum.frangi_ridge(gr.astype(np.float32), 100.0, sigma_m=200.0)
    save("frangi_datum", fr)
    del gr, fr, _
    gc.collect()
    gz = np.hypot(*np.gradient(np.where(np.isfinite(z), z, 0.0).astype(np.float32)))
    fr2, _ = datum.frangi_ridge(gz.astype(np.float32), 100.0, sigma_m=200.0)
    save("frangi_dem", fr2)
    del gz, fr2, _, resid, base, iso, band, z
    gc.collect()
    print(f"frangi {time.time()-t0:.0f}s", flush=True)

    with rasterio.open(ROOT / "data/training_features.tif") as src:
        for band_no, name in ((3, "tmi_hg"), (18, "iso_grav_hg"), (2, "rtp"),
                              (4, "geod_2ndinv"), (7, "geod_shearrate"),
                              (15, "depth_base")):
            a = src.read(band_no)
            a[a < -3.0e38] = np.nan
            save(name, _pct(np.abs(a.astype(np.float32))))
            del a
            gc.collect()
    print(f"geophysics {time.time()-t0:.0f}s", flush=True)

    (OUT / "manifest.json").write_text(json.dumps(
        dict(built_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             files=sorted(p.name for p in OUT.glob("*.npy")),
             seconds=round(time.time() - t0, 1)), indent=1))
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
