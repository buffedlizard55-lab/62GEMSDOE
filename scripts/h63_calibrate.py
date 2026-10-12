#!/usr/bin/env python3
"""H63M — calibrate the proxy instrument against the group's score-anchored registry.

The problem this solves
-----------------------
``evidence/h63a_emission.json`` shows a supervised model on the official 19-band stack
reaches AUC 0.50 on held-out spatial blocks: no spatially transferable signal.  So the
only ranking instrument available is a *pattern* instrument, and a pattern instrument
has to be calibrated against artifacts whose live score is known.

The statistic
-------------
For an emission of mass S with weighted credit T,

    DTI = T / (alpha*S + beta*K)          (exact when the emitted kernel mass equals the
                                           credit; alpha 0.2, beta 0.8, K = hidden truth)

so **credit per unit mass, c = T/S, at fixed K is the entire ranking**.  For *random*
dots the same quantity has a closed form that this script verifies against measurement:

    c_random = (pi*R^2/3) * K / A          (A = scored area, R = 3 cells)

i.e. c_random depends only on the truth's area density, not on the emission mass.

The calibration
---------------
Every registry raster carries an owner-reported live score.  Inverting the identity
above gives that raster's *implied* credit per unit mass against the **hidden** truth,
c_hidden.  This script measures each raster's credit per unit mass against the two free
proxies (SGMC off-catalogue faults, and the competition catalogue) and reports the
transfer ratio r = c_hidden / c_proxy.  If r is stable across rasters it is a usable
transfer constant; if it is not, the instrument cannot rank and that is recorded.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
REG = HERE / "data" / "registry"
K_PLAN = 9400.0          # hidden-truth mass, cells (MODEL input, sensitivity swept)


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def measure(mask: np.ndarray, truth: np.ndarray, valid: np.ndarray):
    m = np.asarray(mask, bool) & valid
    S = float(m.sum())
    if S == 0:
        return dict(mass=0.0, tp=0.0, fp=0.0, fn=0.0, dti=0.0, cm=0.0)
    c = dti_components(m.astype(np.float32), truth, valid=valid,
                       pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
    return dict(mass=S, tp=round(c.tp_w, 2), fp=round(c.fp_w, 2), fn=round(c.fn_w, 2),
                dti=round(c.dti, 5), cm=round(c.tp_w / S, 5))


def main() -> int:
    t0 = time.time()
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    A = float(usable.sum())

    src = json.loads((HERE / "registry" / "registry_sources.json").read_text())
    scores = {e["alias"]: e.get("owner_reported_score") for e in src["entries"]}

    rows = []
    for p in sorted(REG.glob("*.tif")):
        alias = p.stem
        with rasterio.open(p) as s:
            a = s.read(1).astype(np.float32)
        m = np.isfinite(a) & (a > 0)
        mp, mc = measure(m, pro, usable), measure(m, cat, usable)
        dcat = ndi.distance_transform_edt(~cat) * PIXEL_M
        dmed = float(np.median(dcat[m])) if m.any() else float("nan")
        rows.append({"alias": alias, "score": scores.get(alias),
                     "mass": mp["mass"], "proxy": mp, "catalogue": mc,
                     "median_dcat_m": round(dmed, 1),
                     "frac_dcat_lt300": round(float((dcat[m] < 300).mean()), 4) if m.any() else None})
        log(f"  {alias:38s} score={scores.get(alias)} M={mp['mass']:9.0f} "
            f"cm_proxy={mp['cm']:.4f} cm_cat={mc['cm']:.4f}")

    # ---- the closed-form random control, verified against an emission ----------
    rng = np.random.default_rng(62)
    flat = np.flatnonzero(usable.ravel())
    ctrl = np.zeros(usable.size, bool)
    ctrl[flat[rng.choice(flat.size, size=60_000, replace=False)]] = True
    ctrl = ctrl.reshape(usable.shape)
    cpc, ccc = measure(ctrl, pro, usable), measure(ctrl, cat, usable)
    c_rand = {}
    for nm, K in (("proxy_off", float(pro.sum())), ("catalogue", float(cat.sum()))):
        c_rand[nm] = {"closed_form": round((np.pi * 3.0 ** 2 / 3.0) * K / A, 5)}
    c_rand["proxy_off"]["measured"] = cpc["cm"]
    c_rand["catalogue"]["measured"] = ccc["cm"]

    # ---- implied credit per unit mass against the HIDDEN truth ----------------
    cal = []
    for r in rows:
        s = r["score"]
        if not s:
            continue
        S = r["mass"]
        for K in (8000.0, K_PLAN, 12000.0):
            c_h = s * (ALPHA * S + BETA * K) / S          # implied cm on the hidden set
            r.setdefault("implied", {})[str(int(K))] = {
                "cm_hidden": round(c_h, 5),
                "r_vs_proxy": round(c_h / r["proxy"]["cm"], 4) if r["proxy"]["cm"] else None,
                "r_vs_catalogue": round(c_h / r["catalogue"]["cm"], 4) if r["catalogue"]["cm"] else None,
            }
        cal.append(r)

    rr = [r["implied"][str(int(K_PLAN))]["r_vs_proxy"] for r in cal
          if r["implied"][str(int(K_PLAN))]["r_vs_proxy"]]
    rc = [r["implied"][str(int(K_PLAN))]["r_vs_catalogue"] for r in cal
          if r["implied"][str(int(K_PLAN))]["r_vs_catalogue"]]

    def stats(v):
        v = np.array(v, float)
        return {"n": int(v.size), "median": round(float(np.median(v)), 4),
                "mean": round(float(v.mean()), 4), "min": round(float(v.min()), 4),
                "max": round(float(v.max()), 4), "iqr": [round(float(x), 4) for x in
                                                        np.percentile(v, [25, 75])]}

    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("MEASURED (registry rasters fetched from public sibling repos, "
                           "exact 300 m kernel) + OWNER-REPORT (the score column) + MODEL "
                           "(the inversion, which assumes K and is never a score)"),
        "scored_area_cells": int(A),
        "K_planning_cells": K_PLAN,
        "random_control": {"mass": cpc["mass"], **c_rand},
        "transfer_ratio_r_vs_proxy": stats(rr),
        "transfer_ratio_r_vs_catalogue": stats(rc),
        "rasters": rows,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_calibration.json").write_text(json.dumps(res, indent=1))
    log("\nrandom control: " + json.dumps(c_rand))
    log("transfer ratio r = cm_hidden / cm_proxy : " + json.dumps(stats(rr)))
    log("transfer ratio r = cm_hidden / cm_catalogue : " + json.dumps(stats(rc)))
    log("\n%-40s %7s %9s %9s %9s" % ("alias", "score", "cm_proxy", "cm_hidden", "r"))
    for r in sorted(cal, key=lambda d: -(d["score"] or 0)):
        im = r["implied"][str(int(K_PLAN))]
        log("%-40s %7s %9.4f %9.4f %9s" % (
            r["alias"], r["score"], r["proxy"]["cm"], im["cm_hidden"], im["r_vs_proxy"]))
    log("wrote " + str(EV / "h63_calibration.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
