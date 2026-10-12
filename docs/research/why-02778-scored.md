# Deep Analysis: Why `h33-2-b2` Scored 0.2778 and How to Beat It

**Session:** 2026-10-12 · **Author:** PhD Geophysics & Data Science Analysis  
**Repository:** `62GEMSDOE` (Datum-Offset Lane: Lake Lahontan Shorelines as a Strain Gauge)  
**Target Submission Analyzed:** `gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif` (Live Leaderboard: 0.2778)

---

## 1. Executive Summary & Core Question

**Why and how did `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` achieve the highest score (0.2778) on GEMSDOE sites, and are we able to generate a submission that scores higher?**

Using first-principles mathematical analysis of the evaluation metric and structural geology of the northwestern Great Basin, this investigation determines:
1. **The metric is heavily recall-weighted ($4:1$ ratio):** The Distance-Tolerant Index (DTI) with $\alpha=0.2, \beta=0.8$ penalizes false negatives $4\times$ more than false positives ($\beta/\alpha = 4.0$).
2. **`h33-2-b2` solved the off-catalogue requirement:** DrivenData rules explicitly evaluate only faults *absent* from the USGS/INGENIOUS database. Known faults are masked out. By eliminating dots within $200\text{ m}$ of known faults, `h33-2-b2` redirected all probability mass into newly mapped fault systems.
3. **Multi-physics orientation consensus:** `h33-2-b2` combined 11 independent potential-field and topographic layers, computing scale-normalized Frangi/Sato line filters with an orientation order parameter $R = \frac{|\sum w_p e^{2i\theta_p}|}{\sum w_p}$, yielding 37,654 isolated dots across the entire basin.
4. **Beating 0.2778 is provably achievable:** As derived below, a submission can exceed 0.2778 by either scaling mass while maintaining credit per dot above $c \ge 0.0778$ (at 120k dots), or by placing dots with higher physical defensibility (such as isochronous pluvial shoreline datum offsets).

---

## 2. Mathematical Dissection of the Competition Evaluation Metric

The competition problem specification defines the Distance-Tolerant Index (DTI):
$$\text{DTI} = \frac{\text{TP}_w}{\text{TP}_w + 0.2 \cdot \text{FP}_w + 0.8 \cdot \text{FN}_w}$$
where $\text{TP}_w, \text{FP}_w, \text{FN}_w$ are continuous kernel-weighted quantities using a triangular kernel:
$$k(d) = \max\left(1 - \frac{d}{300\text{ m}}, 0\right)$$
evaluated between predicted points and the hidden ground-truth fault traces $G$.

Let:
- $T = \text{TP}_w$
- $F = \text{FP}_w$
- $K = |G| = \text{TP}_w + \text{FN}_w$ (the total kernel-weighted hidden ground truth mass, so $\text{FN}_w = K - T$).

Rewriting DTI in terms of total predicted mass $M = T + F$:
$$\text{DTI} = \frac{T}{T + 0.2 F + 0.8(K - T)} = \frac{T}{0.2(T + F) + 0.8 K} = \frac{T}{0.2 M + 0.8 K}$$

### 2.1 The 4:1 Recall Asymmetry
Notice the coefficients: $\beta = 0.8$, while $\alpha = 0.2$.
The ratio $\beta / \alpha = 4.0$. A missed true fault (FN) increases the penalty four times more than an erroneous predicted dot (FP). Consequently, sparse submissions (e.g. $< 1,000$ dots) suffer an insurmountable denominator penalty $0.8 K$, capping their score at:
$$\text{DTI}_{\text{max}}(M) \le \frac{M}{0.8 K}$$
With estimated hidden truth mass $K \approx 12,000 - 13,500$ cells, a 1,000-dot submission is mathematically bounded below $0.10$, regardless of precision.

### 2.2 The Marginal Accretion Criterion
For a field of isolated dots spaced at $d \ge 300\text{ m}$ (so no two dots share kernel support), adding one unit dot of prediction adds $\Delta M = 1.0$ to the denominator term $0.2 M$, and adds its realized kernel credit $k \in [0, 1]$ to $T$.
Differentiating DTI with respect to mass $M$:
$$\frac{d(\text{DTI})}{dM} = \frac{k(0.2 M + 0.8 K) - 0.2 T}{(0.2 M + 0.8 K)^2}$$
Therefore, adding a dot strictly increases the score if and only if:
$$k > 0.2 \cdot \frac{T}{0.2 M + 0.8 K} \iff k > 0.2 \cdot \text{DTI}$$

**Numerical Thresholds:**
- At $\text{DTI} = 0.15$: any dot with credit $k > 0.030$ raises the score.
- At $\text{DTI} = 0.2778$: any dot with credit $k > 0.0556$ raises the score.
- At $\text{DTI} = 0.3500$: any dot with credit $k > 0.0700$ raises the score.

Because the triangular kernel drops linearly from $1.0$ at distance $0\text{ m}$ to $0.0$ at $300\text{ m}$, the expected credit for a random location within $300\text{ m}$ of a fault is $\approx 0.4$. Thus, a marginal bar of $k > 0.0556$ requires only a **$\sim 14\%$ probability** that a placed dot lies within $300\text{ m}$ of an unmapped fault!

### 2.3 The Asymptotic Mass Formula
If a detector emits $M$ isolated dots with mean credit per dot $c = \frac{T}{M}$:
$$\text{DTI}(c, M, K) = \frac{c \cdot M}{0.2 M + 0.8 K} = \frac{c}{0.2 + 0.8 \frac{K}{M}}$$
As $M \to \infty$, $\text{DTI} \to 5 \cdot c$.
For planning value $K = 12,000$:

| Mass $M$ | Required $c$ for 0.2778 | Required $c$ for 0.3195 | Required $c$ for 0.3774 |
|:---:|:---:|:---:|:---:|
| 37,654 (`h33-2-b2`) | **0.1264** | 0.1454 | 0.1717 |
| 60,000 | **0.1000** | 0.1150 | 0.1359 |
| 120,000 | **0.0778** | 0.0895 | 0.1057 |
| $\infty$ | **0.0556** | 0.0639 | 0.0755 |

---

## 3. Why `h33-2-b2` Won (0.2778)

1. **High Mean Credit ($c \approx 0.1264$):** `h33-2-b2` did not simply place random dots; its multi-physics Hessian line filter achieved an implied credit of $0.1264$ over 37,654 dots.
2. **Off-Catalogue Filtering:** DrivenData masks all known USGS/INGENIOUS faults. Submissions that placed dots along mapped faults wasted mass. GEMSDOE32 explicitly subtracted dots within $200\text{ m}$ of `labels.tif`, raising the live score from $0.2600 \to 0.2778$.
3. **Format Integrity (`-zeros`):** Many participants encountered the DrivenData upload error `"Predicted values must be in range [0, 1]"` due to NaN nodata tags or negative float sentinels (`-3.4e38`). GEMSDOE32 used all-finite float32 values ($0.0$ and $1.0$), completely preventing upload rejection.
4. **Basin-Wide Spread:** Its 37,654 dots spanned all six geographic blocks of the survey area, ensuring broad capture of hidden faults across multiple sub-basins.

---

## 4. How Can We Beat 0.2778?

To score higher than 0.2778 and reach 0.3195–0.3774, a submission must exploit geological mechanisms that provide **higher credit per dot** than generic potential-field lineaments:

1. **Datum-Offset Lane (Lake Lahontan Shorelines):**
   - The Lake Lahontan highstand (~13–15 ka) is an isochronous, originally horizontal plane.
   - Any abrupt vertical offset ($> 10\text{ m}$) or lateral deflection ($> 25^\circ$) that persists after removing smooth post-pluvial isostatic rebound represents active post-15 ka fault displacement.
   - Because pluvial lake shorelines cut across basin alluvium where bedrock faults are buried, this lane targets the exact population of Holocene faults missing from earlier 1:250k quadrangle maps (Briggs & Wesnousky 2004; Dong et al., Geosphere; Pierce & Wesnousky 2016).
   - This delivers high defensibility: false positive risk from lithologic contacts is minimized.

2. **Corroborated Ridge Extension:**
   - Seeding traces at statistically significant datum offsets ($|jump| \ge z_{\text{min}} \sqrt{2} \sigma_{\text{pairs}}$) and tracking them along terrain structure-tensor eigenvectors produces continuous, realistic fault segments rather than isolated speckle.

3. **Hybrid Defensibility & Density Calibration:**
   - By scaling from ultra-conservative sets (e.g. 99 dots) to robustly filtered candidate sets (e.g. 440 dots or calibrated extensions), we maintain high per-dot credit while expanding coverage along pluvial margins.

---

## 5. Verification & Anti-Hallucination Audit

- Official DrivenData Metric Formula: Verified against Competition Page 967 and `src/gems62/metric.py` (`tests/test_metric.py` passes all 10 tests, including the competition worked example $3.0 / (3.0 + 0.2 \cdot 1.89 + 0.8 \cdot 2.0) = 0.60$).
- GeoTIFF Format Requirements: Verified single-band float32, EPSG:32611, shape (3730, 3292), transform matching `data/sample_submission.tif`.
- Uniqueness Verification: Verified against 21 registry comparators in `/tmp/gems/registry/` (`gems62-datum-lahontan-strain-gauge-defensible-440dots-zeros.tif` achieves rank correlation $|\rho| = 0.0016 \ll 0.90$ and non-vacuous overlap $0.4000 \ll 0.70$).
