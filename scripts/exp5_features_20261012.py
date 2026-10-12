#!/usr/bin/env python3
"""EXP-5 (session arena/7b275dfb-62gemsdoe): feature builder for H-2R / H62-Z1/Z3/Z4.

Builds the champion-mechanism features (scale-normalised Hessian line response, both
polarities, + cross-band orientation order parameter) from the byte-verified organiser
stack, plus the geothermal-vent interaction features (H62-Z1), the depth-to-basement step
features (H62-Z3) and the drainage-deflection features (H62-Z4).

Every feature plane is written to build/cache/ as float16 (.npy) together with a
meta.json naming its provenance.  NaNs (organiser nodata) are filled with 0 after a
robust per-band standardisation, and a *_nanflag feature records where the fill happened.

Usage: .venv/bin/python scripts/exp5_features_20261012.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CACHE = ROOT / "build" / "cache"

SIGMAS = (1.2, 2.5)          # px; 120 m and 250 m at 100 m/px
BETA_FRANGI = 0.5
# bands of the organiser stack (1-based) used for the line-consensus
STACK_BANDS = {  # name -> band index in gems-geodawn-numerical-features.tif
    "rtp": 2, "tmi": 14, "mag_anom": 1, "iso_grav_anom": 13, "det_elev": 12,
    "cond_surf": 17, "depth_to_base_surf": 15, "tc": 6, "TMI_up150": None,
    "iso_grav_anom_hg": 18, "tmi_hg": 3, "tmi_vg": 9,
}


def robust_std(a: np.ndarray, m: np.ndarray) -> float:
    v = a[m]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 1.0
    s = float(np.percentile(v, 75) - np.percentile(v, 25))
    return s if s > 1e-9 else max(float(v.std()), 1e-9)


def hessian_vesselness(zm: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (vess_max, strike_angle, s_norm) for a standardised plane."""
    # scale-normalised second derivatives
    Hxx = ndi.gaussian_filter(zm, sigma, order=(0, 2), mode="nearest") * sigma * sigma
    Hyy = ndi.gaussian_filter(zm, sigma, order=(2, 0), mode="nearest") * sigma * sigma
    Hxy = ndi.gaussian_filter(zm, sigma, order=(1, 1), mode="nearest") * sigma * sigma
    tr = Hxx + Hyy
    disc = np.sqrt((Hxx - Hyy) ** 2 + 4.0 * Hxy ** 2)
    lam_a = 0.5 * (tr + disc)          # larger eigenvalue
    lam_b = 0.5 * (tr - disc)          # smaller eigenvalue
    # direction of lam_a; strike of the structure = direction of lam_b = phi_a + pi/2
    phi_a = 0.5 * np.arctan2(2.0 * Hxy, Hxx - Hyy)
    strike = phi_a + 0.5 * np.pi
    absa, absb = np.abs(lam_a), np.abs(lam_b)
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = np.where(absa > 1e-12, absb / np.maximum(absa, 1e-12), 0.0)
    s = np.sqrt(lam_a ** 2 + lam_b ** 2)
    c = max(float(np.percentile(s, 99.0)) * 0.5, 1e-9)
    v = np.exp(-(rb ** 2) / (2 * BETA_FRANGI ** 2)) * (1.0 - np.exp(-(s ** 2) / (2 * c ** 2)))
    # Frangi line measure is symmetric in polarity here (both polarities kept via rb only)
    return v.astype(np.float32), strike.astype(np.float32), s.astype(np.float32)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as d:
        tmpl = d.read(1)
    footprint = np.isfinite(tmpl)
    H, W = footprint.shape
    with rasterio.open(ROOT / "data" / "labels.tif") as d:
        catalogue = (d.read(1) == 1) & footprint

    meta = dict(shape=[H, W], features=[], generated_utc=None)

    def save(name: str, arr: np.ndarray, prov: str) -> None:
        assert arr.shape == (H, W), (name, arr.shape)
        np.save(CACHE / f"feat_{name}.npy", arr.astype(np.float16))
        meta["features"].append(dict(name=name, provenance=prov))
        print(f"  saved {name}", flush=True)

    # ---------------- organiser stack: standardised fill + nanflag ----------------
    with rasterio.open(ROOT / "build" / "ext" / "gems-geodawn-numerical-features.tif") as d:
        stack_names = list(d.descriptions)
        for bidx, bname in enumerate(stack_names, start=1):
            short = (bname.split(" - ")[0] if bname else f"b{bidx}")
            a = d.read(bidx).astype(np.float32)
            nod = d.nodata
            bad = ~np.isfinite(a)
            if nod is not None and np.isfinite(nod):
                bad |= (a == np.float32(nod))
            m = footprint & ~bad
            mu = float(np.median(a[m])) if m.any() else 0.0
            sd = robust_std(a, m)
            zm = np.where(bad, mu, a)
            zm = ((zm - mu) / sd).astype(np.float32)
            zm[~np.isfinite(zm)] = 0.0
            save(f"org_{short}", zm, f"organiser stack band {bidx} '{bname}', robust-standardised, nodata->median")
            if bad.any():
                save(f"org_{short}_nanflag", bad.astype(np.float32),
                     f"nodata flag for organiser band {bidx}")

    # ---------------- H-2R: vesselness + strike + coherence ----------------
    def load_f(name: str) -> np.ndarray:
        return np.load(CACHE / f"feat_{name}.npy").astype(np.float32)

    line_bands = ["rtp", "tmi", "mag_anom", "iso_grav_anom", "det_elev",
                  "cond_surf", "depth_to_base_surf", "tc", "iso_grav_anom_hg", "tmi_hg"]
    line_bands = [b for b in line_bands if (CACHE / f"feat_org_{b}.npy").exists()]
    for sigma in SIGMAS:
        wsum = np.zeros((H, W), np.float32)
        wx = np.zeros((H, W), np.float32)
        wy = np.zeros((H, W), np.float32)
        vote = np.zeros((H, W), np.float32)
        vsum = np.zeros((H, W), np.float32)
        threshes = []
        for b in line_bands:
            zm = load_f(f"org_{b}")
            v, strike, _ = hessian_vesselness(zm, sigma)
            save(f"vess_{b}_s{sigma}", v, f"H-2R Frangi line response (both polarities), {b}, sigma={sigma} px")
            t = float(np.percentile(v[footprint], 90.0))
            threshes.append(t)
            vote += (v >= t).astype(np.float32)
            vsum += v
            wsum += v
            wx += v * np.cos(2.0 * strike)
            wy += v * np.sin(2.0 * strike)
        R = np.sqrt(wx ** 2 + wy ** 2) / np.maximum(wsum, 1e-9)
        R[wsum <= 1e-9] = 0.0
        save(f"orient_R_s{sigma}", R.astype(np.float32),
             f"H-2R orientation order parameter R=|sum w e^2itheta|/sum w, sigma={sigma}")
        save(f"vote90_s{sigma}", vote, f"k-of-N vote count at per-band 90th pct vesselness, sigma={sigma}")
        save(f"vess_mean_s{sigma}", (vsum / len(line_bands)).astype(np.float32),
             f"mean vesselness over {len(line_bands)} line bands, sigma={sigma}")

    # ---------------- H62-Z1: geothermal vent features ----------------
    import csv
    hot_rows, hot_w = [], []
    n_rows = 0
    with open(ROOT / "build" / "ext" / "gdr_wellspring_in_footprint.csv") as fh:
        for row in csv.DictReader(fh):
            n_rows += 1
            try:
                r, c = int(row["row"]), int(row["col"])
            except (ValueError, KeyError):
                continue
            if not (0 <= r < H and 0 <= c < W):
                continue
            tclass = (row.get("thermalclass") or "").strip().lower()
            try:
                temp = float(row.get("temp_c") or "nan")
            except ValueError:
                temp = float("nan")
            geo = []
            for k in ("geothermquartz_c", "geothermchalc_c", "geothermcat_c"):
                try:
                    geo.append(float(row.get(k) or "nan"))
                except ValueError:
                    pass
            gmax = max([g for g in geo if np.isfinite(g)], default=float("nan"))
            hot = (tclass in ("hot", "warm")) or (np.isfinite(temp) and temp >= 40.0) \
                  or (np.isfinite(gmax) and gmax >= 60.0)
            if hot:
                w = np.nanmax([temp if np.isfinite(temp) else 0.0,
                               gmax if np.isfinite(gmax) else 0.0, 40.0]) / 100.0
                hot_rows.append((r, c))
                hot_w.append(float(w))
    hot_rows = np.array(hot_rows, dtype=np.int64)
    hot_w = np.array(hot_w, dtype=np.float32)
    print(f"GDR rows {n_rows}, thermal features {len(hot_rows)}", flush=True)
    hot_mask = np.zeros((H, W), bool)
    if len(hot_rows):
        hot_mask[hot_rows[:, 0], hot_rows[:, 1]] = True
        dpx = ndi.distance_transform_edt(~hot_mask).astype(np.float32)
        save("vent_dpx", dpx, f"distance (px) to nearest thermal spring/well; {len(hot_rows)} of {n_rows} GDR rows")
        dens = np.zeros((H, W), np.float32)
        dens[hot_rows[:, 0], hot_rows[:, 1]] = hot_w
        for sig, tag in ((20.0, "2km"), (50.0, "5km"), (100.0, "10km")):
            k = ndi.gaussian_filter(dens, sig, mode="nearest")
            save(f"vent_kd_{tag}", k.astype(np.float32),
                 f"temperature/chemistry-weighted GDR thermal density, gaussian sigma={sig} px ({tag})")
    # volcanic vents
    vcount = 0
    vmask = np.zeros((H, W), bool)
    with open(ROOT / "build" / "ext" / "gdr_volcanic_vents_in_footprint.csv") as fh:
        for row in csv.DictReader(fh):
            try:
                r, c = int(row["row"]), int(row["col"])
            except (ValueError, KeyError):
                continue
            if 0 <= r < H and 0 <= c < W:
                vmask[r, c] = True
                vcount += 1
    vd = ndi.distance_transform_edt(~vmask).astype(np.float32)
    save("vvent_dpx", vd, f"distance (px) to nearest GDR volcanic vent ({vcount} rows)")

    # ---------------- H62-Z3: depth-to-basement step features ----------------
    for b, tag in (("depth_to_base_surf", "d2b"), ("cond_surf", "cond")):
        zm = load_f(f"org_{b}")
        zm_s = ndi.gaussian_filter(zm, 2.0, mode="nearest")
        gy, gx = np.gradient(zm_s)
        gmag = np.sqrt(gx ** 2 + gy ** 2).astype(np.float32)
        save(f"step_{tag}", gmag, f"H62-Z3 cross-strike gradient magnitude of {b} (smoothed sigma=2 px)")

    # ---------------- H62-Z4: drainage-deflection features ----------------
    with rasterio.open(ROOT / "build" / "ext" / "dem10_chi_100m_i16.tif") as d:
        for bidx, short in ((3, "ksn"), (4, "logarea"), (5, "zmean")):
            a = d.read(bidx).astype(np.float32)
            a[a == -32768.0] = np.nan
            m = footprint & np.isfinite(a)
            mu = float(np.nanmedian(a[m])) if m.any() else 0.0
            sd = robust_std(a, m)
            zm = np.where(np.isfinite(a), (a - mu) / sd, 0.0).astype(np.float32)
            save(f"chi_{short}", zm, f"H62-Z4 dem10 chi-stack band {bidx}, robust-standardised")
    with rasterio.open(ROOT / "build" / "ext" / "topo_10m_derived_100m_u8.tif") as d:
        for bidx, short in ((7, "aspect_coh"), (8, "hs_line"), (6, "curv_abs")):
            a = d.read(bidx).astype(np.float32) / 255.0
            save(f"topo_{short}", a, f"H62-Z4 topo10 band {bidx}, u8->unit")
    # deflection proxy: gradient of aspect coherence + high local curvature
    coh = load_f("topo_aspect_coh")
    gy, gx = np.gradient(ndi.gaussian_filter(coh, 1.5, mode="nearest"))
    save("topo_coh_grad", np.sqrt(gx ** 2 + gy ** 2).astype(np.float32),
         "H62-Z4 deflection proxy: gradient magnitude of aspect coherence")

    # ---------------- LiDAR scarp corroboration bands ----------------
    with rasterio.open(ROOT / "build" / "ext" / "lidar_scarp_features_u8.tif") as d:
        for bidx, short in ((1, "ex_max"), (3, "step_max"), (6, "downface"), (10, "coh100")):
            a = d.read(bidx).astype(np.float32) / 255.0
            save(f"lidar_{short}", a, f"1 m LiDAR scarp composite band {bidx}, u8->unit")

    import time
    meta["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta["line_bands"] = line_bands
    (CACHE / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"features total: {len(meta['features'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
