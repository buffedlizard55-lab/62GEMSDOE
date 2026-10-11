# Why `h33-2-b2` scored 0.2778 — and what would beat it

This answers the session's two questions directly: *why did that artifact score highest in the
group, and can a higher-scoring submission be generated?* Every number is labelled.

## 1. What the artifact actually is — measured here, first-hand

`gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`

| property | value | class |
| --- | --- | --- |
| bytes / sha256 (first 16) | 219,065 / `c55bafc470054e82…` | MEASURED |
| shape / CRS / dtype | 3730×3292 / EPSG:32611 / float32, no NaN | MEASURED |
| values | exactly `{0.0, 1.0}` (binary dot field, **not** a probability surface) | MEASURED |
| positives | **37,654** | MEASURED |
| spatial spread (3×2 blocks) | 12,422 / 9,257 / 8,655 / 1,345 / 1,746 / 4,229 — **all six blocks** | MEASURED |
| live score | 0.2778 | OWNER-REPORTED |

Two facts already separate it from anything this session produced: it is **23× denser** than the
1,660-dot datum lane, and it is **basin-wide** rather than confined to one sub-region.

**What generated it** [SIBLING-MEASURED, read from that repository's own research note and code]:
a multi-physics oriented-lineament consensus — a scale-normalised Hessian line response
(Frangi/Sato, *both* polarities) at σ = 1.2 and 2.5 px on `rtp`, `tmi`, `mag_anom`,
`iso_grav_anom`, `det_elev`, `cond_surf`, `depth_to_base_surf`, the GeoDAWN radiometrics and the
1 m LiDAR scarp composite, multiplied by a **second-order orientation order parameter**
`R = |Σ_p w_p e^{2iθ_p}| / Σ_p w_p`, so a pixel scores only when independent physics agree that a
line exists *and* agree on its strike.

## 2. Why that scores 0.2778 — the arithmetic, not the narrative

The published metric is `DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w + ε)` with a 300 m triangular
kernel [OFFICIAL, competition page 967]. Writing `T = TP_w`, `S = FP_w`, `N = T + FN_w` (the total
kernel-weighted truth mass, so `FN_w = N − T`):

```
DTI = T / (0.2·(T + S) + 0.8·N)
```

Three consequences follow immediately, and they *are* the explanation:

**(a) DTI is strictly decreasing in `S`, so a score of 0.2778 certifies a floor on recall.**
Setting `S = 0` gives the best case, hence

```
T/N  >=  0.8·DTI / (1 − 0.2·DTI)  =  0.8(0.2778)/(1 − 0.2(0.2778))  =  0.2353
```

**The artifact demonstrably found at least 23.5 % (kernel-weighted) of a truth set that is
explicitly defined as the faults *absent* from the USGS/INGENIOUS catalogue** — and any false
positives it carries push the required recall *above* that. This is the strongest true statement
available about it, and **no local instrument in this repository can produce it**, because the
only local truth is the catalogue. That asymmetry is the whole reason the leaderboard exists.

**(b) The metric is recall-dominated, and the marginal bar for adding a dot is low.**
Adding one dot that earns `p` of truth credit and `1 − p` of penalty moves
`T → T + p`, `S → S + (1 − p)`, i.e. the denominator by exactly `0.2`. The score rises iff

```
p  >  0.2 · DTI          →   for this artifact:  p > 0.0556
```

Any dot with better than a **5.6 %** chance of landing within 300 m of a hidden new fault *raises*
the score. That is a low bar, and it is the quantitative reason a 37,654-dot basin-wide field is a
rational design rather than spam — and also why it is very likely **still under-filled**.

**(c) The mechanism justifies high recall by construction.** Per the organizers, a "new fault"
includes *newly mapped geometry of existing systems* [OFFICIAL, thread 11536]. A consensus field
that fires along whole lineament systems inherits the recall of every mapped system and extends
it into the unmapped continuations — exactly the population the test set is drawn from. Dense and
basin-wide is not a bug here; it is the mechanism working.

## 3. Can a higher-scoring submission be generated? Yes — and not by a better holdout

Ranked by expected gain per unit cost, with the reasoning above as the foundation:

1. **Fill the density up to the marginal bar.** At any plausible operating point the bar is
   ~0.01–0.06 truth-credit per dot, while a structured lineament field earns far more than that
   near mapped systems. Sweeping density against `metric.marginal_bar` is hours of work and needs
   no new geology. This is the single highest-EV action available to the group.
2. **Raise `p` by adding physics that agree on the same lines** — not more dots, better dots. The
   untried candidates are ranked in [`hypotheses.md`](hypotheses.md); the pattern that worked
   (several independent fields agreeing on a strike) is the pattern to extend, because each extra
   agreeing field raises `p` without raising `S` proportionally.
3. **Do not optimise the local catalogue proxy.** It is measured to anti-select novelty in two
   independent repositories (ρ = +0.087 versus live; Poisson 0.0669 > h33 0.0067 here). Optimising
   it walks the group *away* from the 0.2778 design.
4. **Change one factor per weekly experiment.** `p` is unobservable locally, so a submission that
   changes both density and detector cannot be interpreted afterwards. The submission page is the
   only ORGANIZER-CONFIRMED channel that exists; treat each slot as an experiment with one variable.

## 4. What this says about the file this session delivered

The datum-offset lane's 1,660 dots sit **23× below** the density of the artifact that scored
0.2778, and 1,641 of them fall in a single 171 × 110 km sub-region. Even if those dots individually
cleared the marginal bar — which is unknowable locally — their *coverage* bounds what they can add.
That is why the verdict on the download page is "legal, unique, low-risk Phase-1 novelty probe,
**not** the lead horse", and why the ranked next step (§3.1) is density calibration rather than
more detector work.

## 5. The claim this document does **not** make

It does not claim 0.2778 is reproducible, or that any file here is comparable to it. The recall
floor in §2(a) is a *necessary condition* implied by the owner-reported score, not a measurement
of that artifact made here; the artifact's own truth (the hidden test faults) is not available in
this sandbox, by the organizers' explicit policy [OFFICIAL, thread 11527].
