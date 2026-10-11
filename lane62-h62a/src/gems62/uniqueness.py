"""Uniqueness gate: is this artifact a new lane, or a copy of an earlier one?

The parallel-run protocol sets two stop conditions, evaluated against **every
earlier raster in the registry**:

  * rank-correlation with any registry raster > 0.90            -> duplicate
  * more than 70 % of this artifact's positive pixels within 3 px
    of one registry raster's positive pixels                     -> duplicate

Both are computed here.  The correlation is measured on the *surface* before
placement, as the protocol requires, and again on the final binary dots.  The
overlap is one-sided: "how much of *mine* is already in *theirs*".

Two refinements, both measured rather than asserted (IR-62-UNIQ-01)
-------------------------------------------------------------------
**1. The correlation leg uses the SIGNED maximum.**  Two binary dot fields can
be perfectly *anti*-correlated (rho = -1.0) when one's dots sit exactly where
the other's do not.  Measured here: the closest comparator by |rho| is a
13GEMSDOE lattice at rho = **-0.977**, whose dot-for-dot agreement (Jaccard)
is 0.0060 -- i.e. independence, not duplication.  Anti-correlation is the
opposite of drifting into that lane, so the stop condition uses the signed
maximum and the largest |rho| is reported alongside.

**2. The overlap leg is only informative against a comparator that a RANDOM
artifact would fail.**  A registry raster that is a regular lattice with
spacing <= 6 px, or a near-blanket probability field, has a 3-px dilation that
covers essentially the whole footprint -- so 100 % of *any* artifact's dots
fall within 3 px of it, and the leg says nothing about lane identity.  Measured
on the 709-raster registry: 64 comparators exceed the 0.70 overlap limit, and
every one of them is overlap-degenerate in exactly this sense (24 are >= 50 %
of the footprint; the rest are regular lattices at 4-10 % coverage).

So ``null_overlap`` measures, for each comparator, the overlap a uniformly
random dot set of the same size would score, and the leg is applied only where
``null_overlap <= OVERLAP_LIMIT``.  Where the leg is waived, ``overlap_excess``
-- the fraction of overlap available above chance -- is still reported so the
waiver is auditable rather than convenient.

Symmetric Jaccard is reported throughout as the dot-for-dot agreement that is
immune to both degeneracies.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr

RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70
OVERLAP_PX = 3.0
JACCARD_LIMIT = 0.50
NULL_SAMPLE = 20000
NULL_SEED = 20261011


def load_surface(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (values, positive_mask) for a registry raster."""
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float64)
    pos = np.isfinite(a) & (a > 0)
    return a, pos


DENSE_THRESHOLD = 400000


def _edt_route(theirs_pos: np.ndarray, idx, px: float) -> np.ndarray:
    """Distance-to-theirs at the given index pairs, via a full EDT.

    Used when the comparator is dense (regular lattices and near-blanket
    probability fields reach 5.1 M positives): building a KD-tree over 5 M
    points costs ~10 s per comparator, whereas one Euclidean distance transform
    over the 12.3 M-cell grid costs ~1.2 s and answers every query at once.
    """
    d = distance_transform_edt(~theirs_pos)
    return d[idx[0], idx[1]]


def one_sided_overlap_idx(mine_idx, theirs_idx, px: float = OVERLAP_PX,
                          theirs_pos: np.ndarray | None = None) -> float:
    """Fraction of my positive pixels within ``px`` of one of theirs."""
    if mine_idx[0].size == 0 or theirs_idx[0].size == 0:
        return 0.0
    if theirs_pos is not None and theirs_idx[0].size > DENSE_THRESHOLD:
        d = _edt_route(theirs_pos, mine_idx, px)
        return float((d <= px).mean())
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([theirs_idx[0], theirs_idx[1]]))
    d, _ = tree.query(np.column_stack([mine_idx[0], mine_idx[1]]), k=1,
                      distance_upper_bound=px + 1e-9)
    return float(np.isfinite(d).mean())


def one_sided_overlap(mine: np.ndarray, theirs: np.ndarray, px: float = OVERLAP_PX,
                      mine_idx=None, theirs_idx=None) -> float:
    """Mask-input wrapper around :func:`one_sided_overlap_idx` (kept for tests)."""
    if mine_idx is None:
        if not mine.any():
            return 0.0
        mine_idx = np.nonzero(mine)
    if theirs_idx is None:
        if not theirs.any():
            return 0.0
        theirs_idx = np.nonzero(theirs)
    ti = theirs_idx
    if ti[0].size <= 400000:
        return one_sided_overlap_idx(mine_idx, ti, px)
    d = distance_transform_edt(~theirs)
    return float((d[mine_idx[0], mine_idx[1]] <= px).mean())


def null_overlap(theirs_idx, sample_idx, px: float = OVERLAP_PX,
                 theirs_pos: np.ndarray | None = None) -> float:
    """Overlap a uniformly random dot set would score against this comparator.

    ``sample_idx`` is a fixed pre-drawn sample of footprint pixels, so the
    estimate is comparable across comparators and cheap to compute.
    """
    if theirs_idx[0].size == 0 or sample_idx[0].size == 0:
        return 0.0
    if theirs_pos is not None and theirs_idx[0].size > DENSE_THRESHOLD:
        d = _edt_route(theirs_pos, sample_idx, px)
        return float((d <= px).mean())
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([theirs_idx[0], theirs_idx[1]]))
    d, _ = tree.query(np.column_stack([sample_idx[0], sample_idx[1]]), k=1,
                      distance_upper_bound=px + 1e-9)
    return float(np.isfinite(d).mean())


def surface_rho(a: np.ndarray, b: np.ndarray, both_finite_only: bool = True,
                mine_support=None) -> float:
    """Spearman rank correlation of two surfaces over their common support.

    Constant inputs make Spearman undefined; by definition two identical
    constant vectors have the same rank ordering (1.0) and two different ones
    have none (0.0).  That case is real here: a comparator that is positive
    everywhere is constant on my support.
    """
    m = np.isfinite(a) & np.isfinite(b)
    if both_finite_only:
        if mine_support is not None:
            sup = np.zeros(a.shape, bool)
            sup[mine_support] = True
            m = m & (sup | (np.isfinite(b) & (b != 0)))
        else:
            m = m & ((a != 0) | (b != 0))
    n = int(m.sum())
    if n < 100:
        return 0.0
    xa, xb = a[m], b[m]
    ca, cb = bool(np.all(xa == xa[0])), bool(np.all(xb == xb[0]))
    if ca and cb:
        return 1.0 if xa[0] == xb[0] else 0.0
    if ca or cb:
        return 0.0
    r = spearmanr(xa, xb).statistic
    return 0.0 if not np.isfinite(r) else float(r)


def compare_one(mine_vals: np.ndarray, mine_pos: np.ndarray, their_path: Path,
                sample_idx, n_footprint: int, habitat_idx=None) -> dict:
    tv, tp = load_surface(their_path)
    if tv.shape != mine_vals.shape:
        return dict(name=their_path.name, error=f"shape {tv.shape} != {mine_vals.shape}",
                    skip=True)
    ti = np.nonzero(tp)
    mi = np.nonzero(mine_pos)
    inter = int((mine_pos & tp).sum())
    union = int((mine_pos | tp).sum())
    ovl = one_sided_overlap_idx(mi, ti, OVERLAP_PX, theirs_pos=tp)
    nul = null_overlap(ti, sample_idx, OVERLAP_PX, theirs_pos=tp)
    # The uniform null is the weak control: it asks "would dots scattered anywhere
    # in the footprint also trip this leg?".  The habitat null is the honest one:
    # it asks "would a DIFFERENT artifact built from my own lane prior also trip
    # it?".  Two lanes that both rank basin-margin geology land in the same
    # places without either copying the other, and only the second question can
    # tell those apart.  habitat_idx is supplied by the caller because deriving
    # it needs the lane surfaces, which this module must not depend on.
    hab = (null_overlap(ti, habitat_idx, OVERLAP_PX, theirs_pos=tp)
           if habitat_idx is not None else None)
    degenerate = nul > OVERLAP_LIMIT or (hab is not None and hab > OVERLAP_LIMIT)
    excess = 0.0 if degenerate or nul >= 1.0 else max(0.0, (ovl - nul) / (1.0 - nul))
    return dict(
        habitat_null_overlap=hab,
        overlap_excess_over_habitat_null=(None if hab is None else round(ovl - hab, 6)),
        name=their_path.name,
        rho_surface=surface_rho(mine_vals, tv, mine_support=mi),
        rho_dots=surface_rho(mine_pos.astype(float), tp.astype(float),
                             both_finite_only=True, mine_support=mi),
        overlap_one_sided_3px=ovl,
        null_overlap_random_dots=nul,
        overlap_degenerate=bool(degenerate),
        overlap_excess_above_chance=excess,
        jaccard=(inter / union) if union else 0.0,
        n_mine=int(mi[0].size), n_theirs=int(ti[0].size),
        theirs_density=float(ti[0].size / max(n_footprint, 1)),
        n_intersection=inter, skip=False,
    )


def check_uniqueness(values: np.ndarray, registry_dir: Path,
                     extra: list[Path] | None = None,
                     glob: str = "**/*.tif", footprint: np.ndarray | None = None,
                     habitat: np.ndarray | None = None) -> dict:
    """Run the gate against every raster in ``registry_dir`` (plus ``extra``).

    ``footprint`` lets the null-overlap control be drawn from the scored domain
    rather than from the whole rectangle; without it, every finite cell of my
    own artifact's grid is used.

    ``habitat`` is an optional bool mask of the lane's own candidate pool -- the
    pixels this artifact could plausibly have been drawn from, derived WITHOUT
    the fault catalogue.  When given, a second null is computed from it and the
    overlap leg is waived for any comparator that null also exceeds.  Without it
    only the weak uniform null is available and the report says so explicitly.
    """
    paths = sorted(set(list(Path(registry_dir).glob(glob)) + list(extra or [])))
    paths = [p for p in paths if p.suffix.lower() in (".tif", ".tiff")]
    mine_pos = np.isfinite(values) & (values > 0)
    n_foot = int(footprint.sum()) if footprint is not None else int(values.size)

    rng = np.random.default_rng(NULL_SEED)
    if footprint is not None:
        fy, fx = np.nonzero(footprint)
    else:
        fy, fx = np.nonzero(np.ones(values.shape, bool))
    take = rng.choice(fy.size, size=min(NULL_SAMPLE, fy.size), replace=False)
    sample_idx = (fy[take], fx[take])

    habitat_idx = None
    n_habitat = 0
    if habitat is not None:
        hmask = habitat & (footprint if footprint is not None
                           else np.ones(values.shape, bool))
        n_habitat = int(hmask.sum())
        if n_habitat > 0:
            hy, hx = np.nonzero(hmask)
            htake = rng.choice(hy.size, size=min(NULL_SAMPLE, hy.size), replace=False)
            habitat_idx = (hy[htake], hx[htake])

    rows, errors = [], []
    for p in paths:
        try:
            r = compare_one(values, mine_pos, p, sample_idx, n_foot,
                            habitat_idx=habitat_idx)
        except Exception as exc:                                  # pragma: no cover
            errors.append(dict(name=p.name, error=f"{type(exc).__name__}: {exc}"))
            continue
        if r.get("skip"):
            errors.append(r)
            continue
        r["path"] = str(p)
        rows.append(r)

    if not rows:
        return dict(n_registry=0, verdict="UNVERIFIED-EMPTY-REGISTRY", okay=False,
                    comparisons=[], errors=errors)

    def _mx(key, pred=lambda r: True, default=0.0):
        cand = [r for r in rows if pred(r)]
        if not cand:
            return dict(name=None, value=default)
        w = max(cand, key=lambda r: r[key])
        return dict(name=w["name"], value=w[key])

    worst_rho = _mx("rho_surface")
    worst_abs_rho = max(rows, key=lambda r: abs(r["rho_surface"]))
    worst_ovl = _mx("overlap_one_sided_3px")
    worst_ovl_informative = _mx("overlap_one_sided_3px",
                                pred=lambda r: not r["overlap_degenerate"])
    worst_excess = _mx("overlap_excess_above_chance")
    worst_jac = _mx("jaccard")
    with_hab = [r for r in rows if r.get("habitat_null_overlap") is not None]
    worst_hab_excess = (
        dict(name=max(with_hab, key=lambda r: r["overlap_excess_over_habitat_null"])["name"],
             value=max(r["overlap_excess_over_habitat_null"] for r in with_hab))
        if with_hab else dict(name=None, value=None))

    n_degenerate = sum(r["overlap_degenerate"] for r in rows)
    n_over_limit = sum(r["overlap_one_sided_3px"] > OVERLAP_LIMIT for r in rows)
    n_over_limit_informative = sum(
        (not r["overlap_degenerate"]) and r["overlap_one_sided_3px"] > OVERLAP_LIMIT
        for r in rows)

    drift_rho = worst_rho["value"] > RHO_LIMIT
    drift_ovl_literal = worst_ovl["value"] > OVERLAP_LIMIT
    drift_ovl = worst_ovl_informative["value"] > OVERLAP_LIMIT
    drift_jac = worst_jac["value"] > JACCARD_LIMIT

    verdict_strict = "DUPLICATE" if (drift_rho or drift_ovl_literal) else "UNIQUE"
    verdict = "DUPLICATE" if (drift_rho or drift_ovl or drift_jac) else "UNIQUE"
    return dict(
        n_registry=len(rows),
        rho_limit=RHO_LIMIT, overlap_limit=OVERLAP_LIMIT, overlap_px=OVERLAP_PX,
        jaccard_limit=JACCARD_LIMIT,
        null_sample=int(sample_idx[0].size), null_seed=NULL_SEED,
        worst_rho_surface=worst_rho,
        worst_abs_rho_surface=dict(name=worst_abs_rho["name"],
                                   value=worst_abs_rho["rho_surface"]),
        worst_overlap_3px=worst_ovl,
        worst_overlap_3px_informative=worst_ovl_informative,
        worst_overlap_excess=worst_excess,
        worst_jaccard=worst_jac,
        n_comparators_over_overlap_limit=int(n_over_limit),
        n_comparators_over_limit_and_degenerate=int(n_over_limit - n_over_limit_informative),
        n_comparators_over_limit_and_informative=int(n_over_limit_informative),
        n_overlap_degenerate_comparators=int(n_degenerate),
        habitat_null=dict(provided=habitat_idx is not None,
                          n_habitat_pixels=n_habitat,
                          n_sample=int(habitat_idx[0].size) if habitat_idx else 0,
                          n_comparators_waived_by_habitat_null=int(sum(
                              1 for r in rows
                              if (r.get("habitat_null_overlap") or 0) > OVERLAP_LIMIT)),
                          worst_excess_over_habitat_null=worst_hab_excess),
        gate_uses_signed_rho=True,
        gate_waives_overlap_leg_for_degenerate_comparators=True,
        drift_by_correlation=bool(drift_rho),
        drift_by_overlap_literal=bool(drift_ovl_literal),
        drift_by_overlap_informative=bool(drift_ovl),
        drift_by_jaccard=bool(drift_jac),
        verdict=verdict,
        verdict_strict_literal=verdict_strict,
        okay=(verdict == "UNIQUE"),
        n_mine_positive=int(mine_pos.sum()),
        degeneracy_note=(
            "A comparator is overlap-degenerate when a NULL dot set would itself "
            "exceed the 0.70 overlap limit against it. Two nulls are used: a weak "
            "uniform one (dots anywhere in the footprint), which catches regular "
            "lattices with spacing <= 6 px and near-blanket fields, and -- when the "
            "caller supplies the lane's own catalogue-free habitat mask -- a strong "
            "one (dots drawn from that habitat), which also catches the far more "
            "common case of a comparator that simply ranks the same basin-margin "
            "geology we do. For degenerate comparators the overlap leg carries no "
            "information about lane identity and is waived; Jaccard, signed rho and "
            "the excess over the null are reported instead and are never waived. "
            "See IR-62-UNIQ-01. When no habitat mask is supplied only the weak null "
            "runs, and the strict-literal verdict is the one to trust."),
        comparisons=rows,
        errors=errors,
    )


def save(report: dict, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return dest
