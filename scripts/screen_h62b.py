#!/usr/bin/env python3
"""Experiment 2 — screen the H62-M / H62-Q candidate evidence surfaces.

For each candidate evidence surface this script hard-core thins it (300 m minimum spacing,
catalogue +3 px excluded) and measures the ONE local quantity that has been validated against
organizer scores this session (Experiment 1):

    c = mean 300 m triangular-kernel credit per dot, against SGMC-minus-catalogue

Bars, all MEASURED in this repository:
    hard-core Poisson control inside the footprint    0.1190
    group champion h33 (0.2778 OWNER-REPORTED)        0.1324
    this lane's previous artifact H62-A (38,000 dots) 0.1347

Two nulls are run, because a "habitat" hypothesis can otherwise pass simply by occupying the
right geology:
    * weak null   -- dots uniform in the footprint
    * strong null -- dots uniform inside the *pluvial band the candidate is allowed to use*

Surfaces come from ``scripts/build_surfaces.py`` (cached under build/surfaces/).

Output: evidence/exp2_h62b_screen.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import emit, metric  # noqa: E402

SURF = ROOT / "build" / "surfaces"
M_TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
EXCLUDE_PX = 3           # keep dots 300 m off the mapped catalogue


def load(name: str) -> np.ndarray:
    return np.load(SURF / f"{name}.npy", mmap_mode="r")


def _pct(a: np.ndarray, lo: float = 2.0, hi: float = 98.0) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    g = np.isfinite(a)
    if not g.any():
        return np.zeros_like(a)
    p1, p2 = np.percentile(a[g], [lo, hi])
    return np.clip((a - p1) / max(p2 - p1, 1e-12), 0.0, 1.0).astype(np.float32)


def main() -> int:
    t0 = time.time()
    footprint = np.asarray(load("footprint"), bool)
    poscat = np.asarray(load("catalogue"), bool)
    sgmc = (rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif").read(1) > 0) & footprint
    known = binary_dilation(poscat, np.ones((2 * EXCLUDE_PX + 1,) * 2, bool))
    domain = footprint & ~known
    truth = (sgmc & ~known).astype(np.float32)
    pre = metric.dti_components(np.zeros(footprint.shape, np.float32), truth, valid=domain)

    band = np.asarray(load("band"), bool)
    zs = load("zscore")
    resid = load("resid")
    coh = load("coh")
    fr_datum = load("frangi_datum")
    fr_dem = load("frangi_dem")
    defl = np.asarray(load("defl"), bool)
    tmi = load("tmi_hg")
    grav = load("iso_grav_hg")
    geo_all = np.sqrt(np.clip(tmi * grav, 0.0, 1.0)).astype(np.float32)
    print(f"loaded {time.time()-t0:.0f}s", flush=True)

    rng = np.random.default_rng(20261012)
    surfaces: dict[str, tuple[np.ndarray, np.ndarray]] = {
        # name: (score surface, allowed mask)
        "S1_step_zscore": (_pct(np.abs(zs)), band),
        "S2_resid_abs": (_pct(np.abs(resid)), band),
        "S3_defl_x_step": (_pct(np.abs(zs)) * defl, band),
        "S4_ridge_coherence": (_pct(coh), band),
        "S5_frangi_datum": (_pct(fr_datum), band),
        "S6_step_x_ridge": (_pct(np.abs(zs)) * _pct(coh), band),
        "S7_step_x_ridge_x_geo": (_pct(np.abs(zs)) * _pct(coh) * geo_all, band),
        "S8_geo_only": (geo_all, band),
        "S9_frangi_dem": (_pct(fr_dem), band),
        "S10_band_habitat_null": (rng.random(footprint.shape).astype(np.float32), band),
        "S11_footprint_null": (rng.random(footprint.shape).astype(np.float32), footprint),
        "S12_elev_window_1308_1360": (
            np.where((np.asarray(load("dem")) >= 1308) & (np.asarray(load("dem")) <= 1360),
                     1.0, 0.0).astype(np.float32), footprint),
        "S13_step_x_ridge_wholemap": (_pct(np.abs(zs)) * _pct(coh), footprint),
    }

    rows = []
    for name, (score, allowed) in surfaces.items():
        rr, cc = emit.hard_core_topk(np.asarray(score), allowed, min_px=3.0,
                                     n=M_TARGET, exclude=known)
        if len(rr) == 0:
            rows.append(dict(name=name, M=0, c=None))
            continue
        pred = np.zeros(footprint.shape, np.float32)
        pred[rr, cc] = 1.0
        comp = metric.dti_components(pred, truth, valid=domain, precomputed=None)
        rows.append(dict(name=name, M=int(len(rr)), c=float(comp.tp_w / len(rr)),
                         tp=float(comp.tp_w), fp=float(comp.fp_w),
                         coverage=float(comp.tp_w / max(comp.tp_w + comp.fn_w, 1e-9))))
        print(f"  {name:28s} M={len(rr):6d}  c={comp.tp_w/len(rr):.4f}", flush=True)
        del pred
    rows.sort(key=lambda r: (r.get("c") is not None, r.get("c") or 0), reverse=True)

    out = dict(
        experiment="E2 H62-M/H62-Q hypothesis screening",
        instrument="mean 300 m kernel credit per dot vs SGMC-minus-catalogue, catalogue+3px masked",
        metric="gems62.metric.dti_components (alpha 0.2, beta 0.8, 300 m triangular)",
        m_target=M_TARGET, exclude_catalogue_px=EXCLUDE_PX,
        bars=dict(poisson_hardcore_control=0.1190, champion_h33=0.1324, lane_h62a=0.1347),
        truth_pixels=int((sgmc & ~known).sum()),
        band_pixels=int(band.sum()),
        rows=rows, seconds=round(time.time() - t0, 1),
    )
    (ROOT / "evidence" / "exp2_h62b_screen.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({r["name"]: r.get("c") for r in rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
