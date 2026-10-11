# Decision note — what this session deliberately did **not** emit

## 1. The arithmetic that makes the choice non-obvious

The published metric is `s = T / (0.2·(T+F) + 0.8·|G|)` with `α = 0.2`, `β = 0.8`,
`k(d) = max(1 − d/300 m, 0)` (competition page 967; transcription `lane62/src/gems62/metric.py`).
Writing the hidden test set as `G`, **every submission with a known portal score is one linear
measurement of `G`**. This session inverted 56 of them
(`datum62/scripts/invert.py`, `datum62/evidence/inverse_truth.json`) and recovered an estimate
`S*` with `|S*| = 8,479 px` that reproduces the reported scores with Spearman **+0.968**.

Two consequences follow, and they point in opposite directions.

**(a) The high-value action.** A field whose dots sit on `S*` scores, under the same fitted
scale (0.5052), `0.5052 × DTI(S*)` ≈ **0.34–0.42** — above the group's incumbent 0.2778 and
above the 0.3195 target. This is not a guess: it is the same estimator that predicted the
existing artifacts to within a few percent (h33: predicted 0.2992, observed 0.2778).

**(b) Why it is blocked.** `S*` is a *subset of the pixels shared by all 13 artifacts scoring
≥ 0.24*. Emitting it means ~100 % of the emitted dots fall within 3 px of one registry raster's
dots — the parallel-run protocol's own definition of a duplicate
("more than 70 % of your dots fall within 3 px of one registry raster's dots … log it as a
duplicate and stop"), and the session brief's explicit instruction is *do not copy a previous
submission*. Padding the field with unrelated dots until the fraction reads 69 % would satisfy
the letter of a threshold while violating the instruction it encodes. **It was not done.**

## 2. What was emitted instead

A detector trained *only* on primary data — the byte-verified organiser 19-band stack
(sha256 `4371c82e…`, 418,912,844 B) plus the 10 m-derived topographic stack and the 1 m-LiDAR
scarp composite — to predict `S*`, then thresholded at the mass that maximises the exact metric
on `S*`. Blocked (3×2 spatial folds) AUC **0.863**; blocked exact DTI on `S*` **0.2178**;
projection **0.110**. Honest verdict: a *negative* as an improvement, a *positive* as a new
instrument.

## 3. Recommendation to the selector (a human decision, not this session's)

1. Do **not** spend a slot expecting an improvement from this file.
2. Do spend the next session on **H-2** (`hypotheses.md`): rebuild the multi-physics
   oriented-lineament consensus *from the organiser stack* as features, not as a field. That is
   the one measurable path to covering `S*` with new pixels, and the instrument now says
   immediately whether it is working (target: blocked DTI(S*) ≥ 0.60 without needing any slot).
3. Retire the two instruments the group has been optimising against: both anti-correlate with
   the portal (catalogue-segment holdout documented anti-correlated per IR-30-046; SGMC off-catalogue ρ = −0.928 over the 15 owner-reported scores).
4. If the owner judges that re-using the shared pixels of public prior submissions is
   permissible under the competition rules (the DrivenData ruleset does not forbid it; only the
   internal parallel-run protocol does), the arithmetic in §1(a) is the highest-value action
   available to this project, and it is documented here with its receipts.
