# Executive summary — how to submit into the competition

**Short version:** download the GeoTIFF from the top of
[the site home page](index.html), go to the competition's submission page, choose that file,
paste the note below, submit. The file is format-legal — all 26 validator checks pass on the
bytes read back from disk — and the portal error you hit before
(*“Predicted values must be in range [0, 1]”*) cannot occur for these bytes.

---

## 1. The file

| | |
|---|---|
| name | `gems62-h62b-lahontan-datumstep-trace-37654dots-20261012T000000Z-zeros.tif` |
| path | [`docs/downloads/`](downloads/gems62-h62b-lahontan-datumstep-trace-37654dots-20261012T000000Z-zeros.tif) |
| size | 231,909 bytes |
| sha256 | `e56752ba2be2b07f50698d88e83551114aba9c0860f0ef1152191579206fac3d` |

## 2. Submit it — click by click

1. Open <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/>
   (login required).
2. **New submission** → **File to submit** → *Choose file* → pick the `.tif` downloaded above.
   A `.zip` containing that single GeoTIFF is also accepted if your browser or network prefers it.
3. **Note (optional)** — paste this, it is exactly 126 characters (the stated limit is 140):

   ```
   H62-B Lahontan base-level isobase steps/deflections, ridge-relief traced, 37654 isolated dots, >=300 m off catalogue. UNSCORED
   ```

4. Press **Create**. The organizer scores it on the hidden test set and returns a number.

**The number does not exist until step 4.** No file in this repository has ever been scored by the
organizer. Everything on this site that looks like a score is labelled
`MEASURED` (computed here), `OWNER-REPORTED` (a score the owner quoted, no receipt),
`OFFICIAL` (quoted from the competition pages) or `MODEL` (algebra on the published metric).
A `MODEL` number is a projection and is never written as a score.

## 3. Why the portal once rejected the file — and why it cannot happen here

The error you saw, verbatim: **“Predicted values must be in range [0, 1]”**
[OFFICIAL — the submission form]. The spec asks for a single-band `float32` raster with values in
`[0, 1]`, matching the CRS, shape and geotransform of the sample submission
[OFFICIAL, competition page 967, *Submission format*]. Two writing habits violate it while looking
correct on screen:

| mechanism | why it trips the portal | status in this file |
|---|---|---|
| a `float32` nodata **sentinel** (e.g. `-3.4028235e38`) written inside the valid footprint | the reader sees an out-of-range float | **absent** — outside the footprint we write `0.0` |
| a **NaN nodata tag** on the band | the reader returns NaN, which is not in `[0, 1]` | **absent** — the file carries no nodata tag at all |

Both are structurally impossible here: `gems62.grid.write_submission` writes one code path, then
`check_submission` **re-opens the file from disk** and re-counts everything. The receipt for the
shipped file reports `nodata = null`, `nan_inside_footprint = 0`, `values_min = 0.0`,
`values_max = 1.0`, `count = 1`, `dtype = float32`, `crs = EPSG:32611`, `shape = (3730, 3292)`,
transform `(100, 0, 243350, 0, −100, 4508550)`.

## 4. What the file contains

37,654 isolated single pixels. No two dots are within 300 m of each other (mean self-kernel
`0.000`, versus `0.032` for the group's champion). No dot is within 300 m of a fault that is
already in the USGS/INGENIOUS catalogue — the organizer does not score mapped faults, and the group
has an organizer-confirmed +0.0178 (0.2600 → 0.2778) for deleting them. The dots are spread over
all six blocks of the grid (block entropy 2.262 bits, versus 2.267 for the champion).

## 5. What is expected of it — stated as a projection, not a score

| quantity | value | class |
|---|---|---|
| mean 300 m kernel credit per dot vs SGMC-minus-catalogue | **0.1683** (1.41× the hard-core control 0.1190; 1.27× the champion's 0.1324) | MEASURED |
| hide-and-recover DTI, independent truth | 0.0728 (champion 0.0741, control 0.0496) | HOLDOUT-DTI |
| hide-and-recover DTI, catalogue truth | 0.000000 — identically zero by arithmetic, see IR-62-HOLDOUT-02 | HOLDOUT-DTI |
| raw projection through the published metric | 0.353 (stable across the whole plausible truth-mass range) | **MODEL** |
| same projection shrunk by its own regression against 13 scored artifacts (slope 0.325, intercept 0.175, r = 0.826, p = 0.0005) | **0.290** | **MODEL** |
| organizer score | **none — unsubmitted** | — |

The residual scatter of that regression is large (±0.12), and there is one documented case
(`p49`) where the same projection over-predicted by 0.121. The honest reading is: this file is
expected to land near or somewhat above the group's best of 0.2778, with a real chance of the
0.32–0.35 band and a real chance of ~0.24. It is the strongest artifact this lane has produced.

## 6. Weekly slots

Promotion to a real submission slot is a separate selector step, subject to the weekly cap shown on
the submission page. This session does not spend a slot by itself — it produces a file and the
evidence for it.
