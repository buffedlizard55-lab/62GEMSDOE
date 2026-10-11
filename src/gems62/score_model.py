"""The metric accounting that decides which lane can score, and how much mass it needs.

Everything here is ALGEBRA on the *published* metric plus one inherited planning
input (the hidden truth mass ``G``).  It is explicitly **a MODEL, not a score and
not a projection written as a score** -- the protocol for this prompt forbids
writing a projection as a score, and the organizer's own page says the public
score may differ from the final score (rules section 3.2).

The algebra
-----------
With unit-valued, non-overlapping dots, ``T = c*N`` (``c`` = mean kernel credit per
dot, ``N`` = emitted mass), ``FP_w = N - T`` and ``FN_w = G - T``.  Substituting
into the published index and using ``alpha + beta = 1``:

    DTI = c * N / (alpha*N + beta*G) = c / (alpha + beta*G/N)

Two consequences, both used to judge a lane before any submission slot is spent:

* **Mass-starved lanes are capped by N.**  As ``N -> 0`` with ``c <= 1``,
  ``DTI -> c*N/(beta*G)``: a lane emitting a few hundred dots cannot exceed a few
  percent **even if every dot is perfect**.
* **At fixed N, only placement quality moves the index.**  ``DTI`` is linear in
  ``c``, so the entire question "can this lane win?" reduces to
  ``c_max(N) = DTI_target * (alpha + beta*G/N)``.

The marginal rule for adding one more dot: profitable iff its credit exceeds
``alpha * DTI``, i.e. within ``R*(1 - alpha*DTI)`` of a truth pixel.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from .metric import ALPHA, BETA, RADIUS_M

#: Hidden-truth mass, in 100 m cells.  Inherited planning value: the sibling
#: repository inverted two owner-recorded rows of the same artifact family
#: (0.2600 at 44,090 dots and 0.2778 at 37,654 dots, both unreceipted) and solved
#: for G; the solution is only self-consistent for G in 10,000-14,100 cells.
#: LABEL: MODEL input, not a measurement of the organizer's labels.
TRUTH_MASS_RANGE_CELLS = (10_000, 14_100)
TRUTH_MASS_PLANNING_CELLS = 12_000

#: Observed mean credit per dot for the best-scoring prior family, derived from the
#: same inversion: T = 0.2778 * (0.2*37,654 + 0.8*12,000) = 4,900 over 37,654 dots.
OBSERVED_FAMILY_MEAN_CREDIT = 0.130


@dataclass
class ScoreModel:
    label: str
    n_dots: int
    mean_credit: float
    truth_mass_cells: int
    dti: float
    marginal_bar_credit: float
    marginal_bar_distance_m: float
    is_upper_bound: bool

    def as_dict(self) -> dict:
        return asdict(self)


def model_dti(n_dots: int, mean_credit: float, truth_mass_cells: int) -> float:
    """``DTI = c*N / (alpha*N + beta*G)`` -- exact for non-overlapping unit dots."""
    if n_dots <= 0 or truth_mass_cells <= 0:
        return 0.0
    return (mean_credit * n_dots) / (ALPHA * n_dots + BETA * truth_mass_cells)


def perfect_placement_ceiling(n_dots: int, truth_mass_cells: int = TRUTH_MASS_PLANNING_CELLS) -> float:
    """The **largest** DTI a file with ``n_dots`` dots can reach at any placement.

    Every dot at full kernel credit (``c = 1``) is the best possible case, so this
    is a hard upper bound for a unit-dot emission of that mass.  It is the number
    that decides whether a sparse, high-precision lane is even worth a slot.
    """
    return model_dti(n_dots, 1.0, truth_mass_cells)


def mean_credit_required(target_dti: float, n_dots: int,
                         truth_mass_cells: int = TRUTH_MASS_PLANNING_CELLS) -> float:
    """Placement quality a file of this mass must achieve to hit ``target_dti``."""
    if n_dots <= 0:
        return float("inf")
    return target_dti * (ALPHA + BETA * truth_mass_cells / n_dots)


def mass_required(target_dti: float, mean_credit: float,
                  truth_mass_cells: int = TRUTH_MASS_PLANNING_CELLS) -> float:
    """Mass a file must emit to hit ``target_dti`` at a given placement quality."""
    denom = mean_credit - ALPHA * target_dti
    if denom <= 0:
        return float("inf")
    return BETA * truth_mass_cells * target_dti / denom


def marginal_bar(dti_value: float) -> tuple[float, float]:
    """``(credit, distance_m)`` beyond which an added dot *lowers* the index."""
    credit = ALPHA * dti_value
    return credit, RADIUS_M * (1.0 - credit)


def comparison_table(
    target_dti: float,
    *,
    truth_mass_cells: int = TRUTH_MASS_PLANNING_CELLS,
    observed_credit: float = OBSERVED_FAMILY_MEAN_CREDIT,
) -> dict:
    """The numbers that decide "can this lane beat the target?"."""
    ceil_225 = perfect_placement_ceiling(225, truth_mass_cells)
    return {
        "target_dti": target_dti,
        "truth_mass_cells": truth_mass_cells,
        "observed_family_mean_credit": observed_credit,
        "perfect_placement_ceiling_at_225_dots": ceil_225,
        "mass_required_at_observed_credit": mass_required(target_dti, observed_credit, truth_mass_cells),
        "mass_required_at_credit_0.20": mass_required(target_dti, 0.20, truth_mass_cells),
        "credit_required_at_40000_dots": mean_credit_required(target_dti, 40_000, truth_mass_cells),
        "credit_required_at_25000_dots": mean_credit_required(target_dti, 25_000, truth_mass_cells),
        "marginal_bar_credit": marginal_bar(target_dti)[0],
        "marginal_bar_distance_m": marginal_bar(target_dti)[1],
        "label": "MODEL (algebra on the published metric with an inherited G input), "
                 "NOT a score and NOT a projection written as a score",
    }
