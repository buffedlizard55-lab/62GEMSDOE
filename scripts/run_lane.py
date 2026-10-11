#!/usr/bin/env python3
"""62GEMSDOE lane driver -- Lake Lahontan shoreline datum-offset strain gauge.

Run:  python3 scripts/run_lane.py            (from the repository root)

Writes every number quoted on the site into evidence/*.json and docs/data/*.json,
plus the candidate GeoTIFFs and their receipts into docs/downloads/.

Nothing here is a competition score.  Every artefact is labelled
MEASURED / MODEL / HOLDOUT-DTI and the writer is fail-closed.

METHOD, in the lane's own words
-------------------------------
 1. Map shoreline benches in the DEM.
 2. Fit a smooth isobase, allowing for post-pluvial isostatic rebound.
 3. Flag abrupt steps or lateral deflections along strike.
 4. Seed a trace at each flag, extend it while DEM-ridge evidence supports it.
 5. Emit dotted lines.
 6. First deliverable: shoreline elevation-versus-distance profiles with the
    flagged steps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from skimage import measure as skm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid as G                              # noqa: E402
from gems62 import holdout as H                           # noqa: E402
from gems62 import lahontan as L                          # noqa: E402
from gems62.metric import dti_exact, credit_bar           # noqa: E402
from gems62.validate import (validate_submission, write_submission,          # noqa: E402
                             dots_on_catalogue)

EV = ROOT / "evidence"
DL = ROOT / "docs" / "downloads"
DD = ROOT / "docs" / "data"
for p in (EV, DL, DD):
    p.mkdir(parents=True, exist_ok=True)


def jdefault(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def dump(name: str, obj):
    with open(EV / f"{name}.json", "w") as fh:
        json.dump(obj, fh, indent=1, default=jdefault)
    return obj


# --------------------------------------------------------------------- data
print("[1] load")
g = G.load_grid(ROOT)
print("    footprint", int(g.footprint.sum()), "catalogue", int(g.catalogue.sum()),
      "active", int(g.active.sum()))
with rasterio.open(ROOT / "data/external/geodawn_dem_a2_100m.tif") as d:
    z = d.read(1).astype(np.float64)
    tr = d.transform
z[z <= -99999] = np.nan
assert z.shape == (G.HEIGHT, G.WIDTH)
dem_valid = np.isfinite(z) & g.footprint
DEM_SHA = G.sha256_file(ROOT / "data/external/geodawn_dem_a2_100m.tif")
print("    DEM valid in footprint", int(dem_valid.sum()),
      "missing", int(g.footprint.sum() - dem_valid.sum()))
dump("dem_provenance", dict(
    file="data/external/geodawn_dem_a2_100m.tif", sha256=DEM_SHA,
    provenance_class="OWNER-MIRROR of a public USGS GeoDAWN product; mirrored in the group's "
                     "60GEMSDOE repository. NOT organiser-authenticated.",
    grid=dict(epsg=32611, height=G.HEIGHT, width=G.WIDTH, transform=list(G.TRANSFORM),
              pixel_m=100.0),
    source="GeoDAWN area-2 absolute-elevation DEM on the competition 100 m grid",
    limits="the organiser's own training_features.tif was NOT obtainable: the DrivenData data "
           "page is login-walled (verified 2026-10-11: redirects to /accounts/login/)."))

h, w = z.shape
jj, ii = np.meshgrid(np.arange(w), np.arange(h))
x_km = (tr.c + (jj + 0.5) * 100.0) / 1000.0
y_km = (tr.f - (ii + 0.5) * 100.0) / 1000.0

# --------------------------------------------------- isobase (block medians)
print("[2] isobase from block medians of the highstand search band")
PICK_LO, PICK_HI = 1320.0, 1350.0
picks = dem_valid & (z >= PICK_LO) & (z <= PICK_HI)
print("    pick pixels", int(picks.sum()), "=", round(picks.sum() * 1e-2, 1), "km2")
# Block medians give a shoreline-level estimate per 20 km cell that is robust to
# the fact that a pixel-level fit inside a narrow band is rank-deficient.
BLK = 200  # 20 km
by, bx = h // BLK + 1, w // BLK + 1
block_rows, block_cols, block_med, block_n = [], [], [], []
for b_i in range(by):
    for b_j in range(bx):
        r1, r2 = b_i * BLK, min(h, (b_i + 1) * BLK)
        c1, c2 = b_j * BLK, min(w, (b_j + 1) * BLK)
        sel = picks[r1:r2, c1:c2]
        n = int(sel.sum())
        if n < 300:
            continue
        block_rows.append((r1 + r2) / 2)
        block_cols.append((c1 + c2) / 2)
        block_med.append(float(np.median(z[r1:r2, c1:c2][sel])))
        block_n.append(n)
block_rows = np.array(block_rows); block_cols = np.array(block_cols)
block_med = np.array(block_med)
bxk = tr.c + (block_cols + 0.5) * 100.0
byk = tr.f - (block_rows + 0.5) * 100.0
x0, y0 = float(bxk.mean()) / 1000.0, float(byk.mean()) / 1000.0
fit = L.fit_isobase(bxk / 1000.0 - x0, byk / 1000.0 - y0, block_med,
                    huber_c=1.5, iters=40)
print(f"    blocks {len(block_med)}  rmse {fit['rmse_m']:.2f} m  "
      f"tilt E {fit['tilt_x_m_per_km']:.3f} m/km  N {fit['tilt_y_m_per_km']:.3f} m/km")
isob = L.isobase_surface(fit["coef"], x_km - x0, y_km - y0)
zeta = np.where(dem_valid, z - isob, np.nan)
res_pick = zeta[picks]
dump("isobase", dict(
    picks_band_m=[PICK_LO, PICK_HI],
    method="robust (Huber, c=1.5) quadratic fit to the median highstand-band elevation of "
           "every 20 x 20 km block containing >= 300 pick pixels -- a rank-sufficient "
           "design, unlike a pixel-level fit confined to a narrow band",
    form="b(x,y) = c0 + c1*x + c2*y + c3*x^2 + c4*x*y + c5*y^2, x/y in km",
    centre_km=[x0, y0], coef=fit["coef"],
    n_blocks=int(block_med.size), block_pixels=block_n,
    median_block_elevation_m=[float(v) for v in block_med],
    rmse_m=fit["rmse_m"], residual_scale_m=fit["residual_scale_m"],
    tilt_east_m_per_km=fit["tilt_x_m_per_km"], tilt_north_m_per_km=fit["tilt_y_m_per_km"],
    residual_of_picks_m=dict(median=float(np.median(res_pick)),
                             p16=float(np.percentile(res_pick, 16)),
                             p84=float(np.percentile(res_pick, 84)),
                             n=int(res_pick.size)),
    literature_check="Adams, Wesnousky & Bills (1999) and Adams et al. (2008): the highstand "
                     "shoreline stands ~1340 m near the basin centre and ~1318 m at the "
                     "northern edge, a northward tilt of order 20 m, from post-pluvial "
                     "isostatic rebound.",
    evidence_class="MEASURED"))

# ------------------------------------------------- lake plain and margin
print("[3] highstand lake plain and its outer margin")
plain = dem_valid & (z <= isob) & (z >= isob - 400.0)
plain = ndi.binary_opening(plain, np.ones((3, 3), bool))
plain = ndi.binary_closing(plain, np.ones((7, 7), bool))
plain = ndi.binary_fill_holes(plain)
lab_p, n_p = ndi.label(plain, np.ones((3, 3), int))
sz = np.bincount(lab_p.ravel()); sz[0] = 0
plain = lab_p == int(np.argmax(sz))
print("    lake plain", int(plain.sum()), "px =", round(float(plain.sum()) * 1e-2, 1), "km2",
      "components", int(n_p))
dump("lake_plain", dict(
    definition="terrain at or below the fitted highstand isobase and no more than 400 m below "
               "it, morphologically cleaned and reduced to its largest connected component. "
               "This is the area inundated at the Sehoo highstand -- the datum's own footprint.",
    px=int(plain.sum()), km2=round(float(plain.sum()) * 1e-2, 1),
    n_components=int(n_p), evidence_class="MEASURED"))

# ----------------------------------- DELIVERABLE 1: contour profiles + flags
print("[4] shoreline contour traces, profiles and flagged steps")
phi = np.where(dem_valid, z - isob, np.nan)
phi_f = np.where(dem_valid, z - isob, np.nan)
# marching-squares zero contour of the datum residual -> clean polylines
cs = skm.find_contours(np.nan_to_num(phi_f, nan=1e6), level=0.0)
cs = [c for c in cs if len(c) >= 40]
print("    raw contours:", len(cs), " total vertices:", int(sum(len(c) for c in cs)))

traces, profiles_out, flags_all = [], [], []
for c in cs:
    r = np.clip(np.round(c[:, 0]).astype(int), 0, h - 1)
    q = np.clip(np.round(c[:, 1]).astype(int), 0, w - 1)
    ok = dem_valid[r, q]
    if ok.sum() < 40:
        continue
    r, q = r[ok], q[ok]
    tidx = np.flatnonzero(ok)
    d = np.hypot(np.diff(r), np.diff(q)).cumsum()
    d = np.concatenate([[0.0], d])
    pr = dict(rows=r.astype(np.int32), cols=q.astype(np.int32),
              distance_px=d, distance_m=d * 100.0,
              elevation_m=z[r, q].astype(float), zeta_m=zeta[r, q].astype(float))
    fl = L.find_steps(pr, win=6, zeta_step_m=2.5, deflect_deg=25.0)
    tid = len(traces)
    traces.append(dict(id=tid, n_vertices=int(r.size),
                       length_km=round(float(d[-1]) * 0.1, 2),
                       n_flags=len(fl),
                       bbox=[int(r.min()), int(q.min()), int(r.max()), int(q.max())]))
    profiles_out.append(dict(trace_id=tid,
                             distance_m=[float(v) for v in pr["distance_m"]],
                             elevation_m=[float(v) for v in pr["elevation_m"]],
                             zeta_m=[float(v) for v in pr["zeta_m"]],
                             rows=r.tolist(), cols=q.tolist()))
    for f in fl:
        f["trace_id"] = tid
        flags_all.append(f)
print("    kept traces:", len(traces), " flags:", len(flags_all),
      " vertical:", sum(1 for f in flags_all if f["kind"] == "vertical_step"),
      " deflection:", sum(1 for f in flags_all if f["kind"] == "lateral_deflection"))
dump("profiles", dict(
    n_traces=len(traces), traces=traces, flags=flags_all,
    thresholds=dict(window_px=6, zeta_step_m=2.5, heading_change_deg=25.0),
    evidence_class="MEASURED",
    note="Deliverable 1.  Each flag is a candidate datum break: a fault paring the shoreline "
         "up/down (vertical_step) or offsetting it along strike (lateral_deflection)."))
with open(DL / "lahontan_shoreline_profiles.json", "w") as fh:
    json.dump(dict(descriptor="Deliverable 1: elevation-versus-distance profiles of the mapped "
                              "Lake Lahontan highstand shoreline, with flagged steps",
                   grid=dict(epsg=32611, transform=list(G.TRANSFORM)),
                   thresholds=dict(window_px=6, zeta_step_m=2.5, heading_change_deg=25.0),
                   traces=traces, flags=flags_all, profiles=profiles_out), fh, default=jdefault)

# -------------------------------------------------------- scarp evidence
print("[5] DEM-ridge / scarp evidence field")
def _u8(path, band_no):
    with rasterio.open(path) as d:
        a = d.read(band_no).astype(np.float64)
        nod = d.nodata
        v = np.ones(a.shape, bool) if nod is None else (a != nod)
    a = np.where(v, a, np.nan)
    lo, hi = np.nanpercentile(a, [2, 98])
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)

TOPO = ROOT / "data/external/topo_10m_derived_100m_u8.tif"
LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
with rasterio.open(TOPO) as d:
    topo_tags = {i: d.tags(i).get("band_name") for i in range(1, d.count + 1)}
LIDAR_BANDS = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
               "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
E = (0.30 * _u8(LIDAR, 8) + 0.20 * _u8(LIDAR, 7) + 0.20 * _u8(LIDAR, 3)
     + 0.20 * _u8(TOPO, 6) + 0.10 * _u8(TOPO, 8))
E = np.where(dem_valid, np.nan_to_num(E, nan=0.0), np.nan)
dump("evidence_field", dict(
    formula="0.30*cross_max + 0.20*upface_max + 0.20*step_max + 0.20*curv_prof_absmax "
            "+ 0.10*hs_lineament",
    topo_band_names=topo_tags, lidar_band_names=LIDAR_BANDS,
    lidar_band_name_provenance="OWNER-DOCUMENTED (60GEMSDOE docs/research/"
                               "geothermal-vents-knowledge.md).  The GeoTIFF carries NO band "
                               "tags -- this is not organiser metadata.",
    shas=dict(topo_10m_derived_100m_u8=G.sha256_file(TOPO),
              lidar_scarp_features_u8=G.sha256_file(LIDAR)),
    ir70_data_01_fix="bands are addressed by TAG where the file is tagged and by documented "
                     "order where it is not -- never by a remembered index.",
    evidence_class="MEASURED (derived) / OWNER-DOCUMENTED (lidar order)"))

# ------------------------------------------------------------- emission
print("[6] emission")
Ef = np.nan_to_num(E, nan=0.0)
seeds = [(f["row"], f["col"], f["kind"], abs(f["magnitude_m"])) for f in flags_all]
print("    seeds (flagged datum breaks):", len(seeds))
E_thr = float(np.nanpercentile(Ef[plain], 60))


def walk(r0, c0, max_len=45):
    win = 9
    r1, r2 = max(0, r0 - win), min(h, r0 + win + 1)
    c1, c2 = max(0, c0 - win), min(w, c0 + win + 1)
    gy, gx = np.gradient(Ef[r1:r2, c1:c2])
    Jxx, Jyy, Jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
    theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
    out = []
    for s in (+1.0, -1.0):
        dr, dc = np.cos(theta) * s, np.sin(theta) * s
        rr, cc = float(r0), float(c0)
        path = []
        for _ in range(max_len):
            rr += dr; cc += dc
            ri, ci = int(round(rr)), int(round(cc))
            if not (0 <= ri < h and 0 <= ci < w) or not dem_valid[ri, ci]:
                break
            look = Ef[max(0, ri - 1):ri + 2, max(0, ci - 1):ci + 2]
            if look.size == 0 or look.mean() < E_thr:
                break
            path.append((ri, ci))
        out.append(path)
    return out


prim = np.zeros((h, w), bool)
for (r0, c0, kind, mag) in seeds:
    for path in walk(r0, c0):
        for (ri, ci) in path:
            prim[ri, ci] = True
print("    primary pixels before de-clump:", int(prim.sum()))

from scipy.spatial import cKDTree


def thin(mask, min_sep_px, strength):
    yy, xx = np.nonzero(mask)
    if yy.size == 0:
        return np.zeros_like(mask)
    s = strength[yy, xx]
    order = np.argsort(-s)
    pts = np.column_stack([yy, xx]).astype(float)
    tree = cKDTree(pts)
    keep = np.zeros(yy.size, bool)
    banned = np.zeros(yy.size, bool)
    for i in order:
        if banned[i]:
            continue
        keep[i] = True
        banned[tree.query_ball_point(pts[i], min_sep_px)] = True
    out = np.zeros_like(mask)
    out[yy[keep], xx[keep]] = 1.0
    return out


SEP_PX = 2.8284271247461903     # 282.8 m -- the spacing measured as best on the live board
prim_thin = thin(prim, SEP_PX, Ef)
sec_mask = plain & (E > float(np.nanpercentile(E[plain], 99.0)))
sec_thin = thin(sec_mask, SEP_PX, Ef)
print("    primary after de-clump:", int(prim_thin.sum()),
      " secondary pool:", int(sec_thin.sum()), " (top 1% scarp evidence inside the plain)")


def prune_catalogue(raster, px=3):
    out = raster.copy()
    out[ndi.binary_dilation(g.catalogue, iterations=int(px))] = 0.0
    return out


prim_final = prune_catalogue(prim_thin, 3)
sec_final = prune_catalogue(sec_thin, 3)
print("    after 3 px catalogue prune: primary", int((prim_final > 0).sum()),
      " secondary", int((sec_final > 0).sum()))

# ------------------------------------------------------------- holdout
print("[7] holdout and controls")
with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
    sgmc = d.read(1)
truthB = H.sgmc_truth(sgmc, g.catalogue, g.footprint)
print("    instrument B truth px:", int(truthB.sum()))
results = {}
for name, rast in (("primary_lane_literal", prim_final), ("secondary_lake_plain", sec_final)):
    pred = rast > 0
    n_px = int(pred.sum())
    A = H.hide_and_recover(pred, g.catalogue, g.footprint, rows=2, cols=2)
    B = dti_exact(pred.astype(float), truthB, valid=g.footprint, known=g.catalogue)
    rng = np.random.default_rng(62)
    idx = np.flatnonzero(g.active)
    ctrl = np.zeros_like(pred)
    if n_px:
        ctrl.ravel()[rng.choice(idx, min(n_px, idx.size), replace=False)] = True
    Bc = dti_exact(ctrl.astype(float), truthB, valid=g.footprint, known=g.catalogue)
    Ac = H.hide_and_recover(ctrl, g.catalogue, g.footprint, rows=2, cols=2)
    results[name] = dict(
        n_positive_px=n_px,
        instrument_A=A, instrument_A_random_dots=dict(pooled=Ac["pooled"], ci95=Ac["ci95"]),
        instrument_B=B, instrument_B_random_dots=Bc,
        credit_bar_at_B=credit_bar(B["dti"]) if B["dti"] > 0 else None)
    print(f"    {name}: n={n_px}  A={A['pooled']['dti']:.6f} (ctrl {Ac['pooled']['dti']:.6f})  "
          f"B={B['dti']:.6f} (ctrl {Bc['dti']:.6f})")
dump("holdout", dict(
    instrument_A=dict(description="whole catalogue segments hidden by 2x2 spatial block, "
                                  "dilated by 3 px = the 300 m kernel radius; pooled DTI over "
                                  "the whole grid with visible catalogue masked",
                      caveat="IR-30-046 (measured by the group 2026-10-03): this proxy ranks "
                             "ANTI-correlated with the public portal scores.  Never a "
                             "promotion gate on its own."),
    instrument_B=dict(description="SGMC 1:750k state-map fault traces rasterised to this grid "
                                  "minus the competition catalogue = 'mapped but not "
                                  "catalogued', the class the competition actually scores",
                      truth_px=int(truthB.sum()),
                      sha256=G.sha256_file(ROOT / "data/external/derived_sgmc_faults_100m.tif"),
                      caveat="public, independent, but 1:750k generalisation is coarse and it "
                             "is still not the organiser's private expert set."),
    results=results))

canary = {}
for nm, arr in (("cross_max", _u8(LIDAR, 8)), ("upface_max", _u8(LIDAR, 7)),
                ("step_max", _u8(LIDAR, 3)), ("curv_prof_absmax", _u8(TOPO, 6)),
                ("hs_lineament", _u8(TOPO, 8)), ("lidar_relief", _u8(LIDAR, 9)),
                ("neg_abs_zeta", -np.abs(np.nan_to_num(zeta, nan=0.0)))):
    canary[nm] = H.feature_auc(np.nan_to_num(arr, nan=0.0), truthB, g.active)
    print(f"    canary AUC {nm}: {canary[nm]:.4f}")
mx = float(np.nanmax(list(canary.values())))
dump("leakage_canary", dict(
    rule="AUC above 0.90 means leakage until proven otherwise.", truth="instrument B",
    auc=canary, max_auc=mx, verdict="pass" if mx < 0.90 else "FAIL",
    evidence_class="MEASURED"))

# ------------------------------------------------------------ write files
print("[8] write")
outA = DL / "gems62-lahontan-datum-step-dotted-primary-zeros.tif"
repA = write_submission(outA, prim_final, g.footprint, outside="zero")
repA["dots_on_catalogue"] = dots_on_catalogue(outA, g.catalogue, g.footprint)
dump("receipt_primary", repA)
outB = DL / "gems62-lahontan-postdatum-scarp-dotted-secondary-zeros.tif"
repB = write_submission(outB, sec_final, g.footprint, outside="zero")
repB["dots_on_catalogue"] = dots_on_catalogue(outB, g.catalogue, g.footprint)
dump("receipt_secondary", repB)
print("    primary  ", repA["sha256"][:16], repA["n_positive_inside_footprint"], "dots")
print("    secondary", repB["sha256"][:16], repB["n_positive_inside_footprint"], "dots")
print("done")
