# Official sources, read line by line

Every claim in this repository that is labelled OFFICIAL traces to one of the entries below.
**Nothing here is quoted from memory.** Where a source could not be read from this sandbox, that
is stated with the reason.

## Competition

| # | source | what was read from it | class |
| --- | --- | --- | --- |
| 1 | [Competition page 967, DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | the metric verbatim: `DTI = TP_w/(TP_w + 0.2·FP_w + 0.8·FN_w + ε)` with triangular kernel `k(d) = max(1 − d/R, 0)`, `R = 300 m`; the submission format: same CRS, bounds and 100 m grid as the training data (EPSG:32611), values `null`/`nan` permitted outside the footprint, **single layer, `float32`, values in `[0, 1]`** | OFFICIAL |
| 2 | [Scoring clarification, thread 11516](https://community.drivendata.org/t/scoring-clarification-…-11516) | known USGS/INGENIOUS fault pixels are **masked / excluded from evaluation in both rounds**; including or excluding them does not matter | OFFICIAL |
| 3 | [Where do you draw the line, thread 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536) | a "new fault" is any fault pixel **not** already captured by USGS/INGENIOUS, *explicitly including newly mapped geometry of existing systems* | OFFICIAL |
| 4 | [How were the new test faults identified, thread 11527](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527) | chrisk-dd (2026-09-23): organizers will **not** share data sources, fault types or coverage behind the test faults beyond the problem description; **Phase 2 (the largest prize pool) will use a test set updated by expert review of all Phase 1 submissions** | OFFICIAL |
| 5 | [Official rules, FY26 OSTI 96647 (PDF)](https://docs.nlr.gov/docs/fy26osti/96647.pdf) | $300,000 total prize pool, September 2026 edition; section structure including 3.4 Feedback, 3.6.1 Public Leaderboard, 3.6.2 Private Dataset Testing, 3.6.3 Interviews. **Only the first chunk of the PDF was read** — sections beyond that are unverified | OFFICIAL, partial |

## Data

| # | source | what was read from it | class |
| --- | --- | --- | --- |
| 6 | [USGS TNM Access API](https://tnmaccess.nationalmap.gov/api/v1/products) | the official 3DEP discovery endpoint: 19 products listed for the n40w119 bbox with S3 download URLs of the form `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/historical/n40w119/USGS_13_n40w119_<date>.tif`, sizes 319–379 MB. Receipt committed as `evidence/tnm_probe.json` | OFFICIAL |
| 7 | USGS 3DEP | no use restrictions; acknowledgement required: "Map services and data available from U.S. Geological Survey, National Geospatial Program" | OFFICIAL |

**Reachability, measured:** this sandbox gets `HTTP 000` from USGS/TNM hosts. GitHub Actions
runners do not, which is why all 3DEP fetching happens on a runner
(`.github/workflows/dem-fetch.yml` + `scripts/fetch_3dep.py`) and the result is transported into
the repository as bytes. Run **38169727207** is the successful six-tile fetch; see `data.md`.

## Science cited by the session brief — **not independently verified here**

These three works are named in the brief and motivate the assigned lane. They were **not** fetched
or read from this sandbox, so nothing about their content is asserted here beyond "the brief cites
them". Marked **[CITED-IN-BRIEF]** wherever they appear.

* Briggs & Wesnousky, *JGR* 2004 — features displaced since the Lahontan highstand used to
  constrain slip on the Pyramid Lake fault zone.
* Dong and coauthors, *Geosphere* — Lahontan shorelines displaced along a strike-slip fault
  outboard of the Wassuk Range front.
* Pierce & Wesnousky, *SCEC poster* 2016 — two previously unmapped northwest-striking segments in
  the centre of Smith Valley, offsetting Holocene sediments.

## Sibling repositories (this group, not official)

Used **only** as internal comparison, never as truth. The registry of 289 prior rasters under
`/tmp/registry` is the group's own output; the calibration numbers quoted from
`sibling h33-hypotheses.md` / `evidence/h33_holdout.json` are **[SIBLING-MEASURED]** and are
attributed to those repositories wherever they appear.

## Claims this repository explicitly does **not** make

* No organizer-confirmed score exists for any file produced in this repository. None is claimed.
* No number from the local holdout is presented as a score. See `irregularities.md` §4.
* No fault "identified" by this repository is asserted to be a fault; the emission is a set of
  datum-offset candidates with a named non-tectonic confuser for each (`run-card.md`).
