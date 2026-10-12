# Next steps — ranked by expected value per unit of work

## 1. Fit the published rebound field instead of a free smooth isobase (H62-P) — highest science value

The flagged steps are 24–83 m, which is too large to be post-15 ka fault offset
([IR-62-B-04](irregularities.md)). The cure is to make the isobase
`plane + published rebound field` instead of `smooth(base, 6 km)`, which turns the residual into
metres of fault offset and removes the degeneracy the repository already records as IR-62-03.

**Source needed:** the shoreline-elevation station tables in Adams, Wesnousky & Bills (1999),
*Isostatic rebound and palinspastic reconstruction of Lake Lahontan* — and the GSA/USGS data
repository item that accompanies it. **Not obtainable from this sandbox**: the sandbox reaches only
`github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org`. It
must be fetched by hand or by a runner with general network access, then committed as a small CSV
with the source DOI. Until then H62-P cannot be validated and is not proposed as viable.

## 2. One submission slot, one variable

The single most useful piece of information the group can buy is an organizer score for a file whose
*only* difference from the champion is known. This artifact differs from the champion in mechanism,
data (absolute DEM), mass (identical, 37,654), isolation (0.000 vs 0.032) and credit (1.27×). That is
too many variables to interpret afterwards. The recommended next submission is a **single-variable**
variant: the same trace pipeline with the mass moved to 30,000 or to 45,000, so the mass response
curve can be read off a real receipt.

## 3. Get an independent, basin-aware truth set

The SGMC compilation is a bedrock map: credit on the roughest decile is 47× the flattest, and
depth-to-basement is inverted (0.265 where cover is thinnest, 0.045 where it is thickest). It
therefore cannot see the population this lane exists to find, and every "the pluvial band is below
chance" measurement (four times now: 0.03×, 0.61×, 0.026×, 0.26×) may be an artefact of that
blindness. What is needed is a Quaternary/basin-floor fault compilation for Nevada — the USGS
Quaternary Fault and Fold Database and the Nevada Bureau of Mines and Geology 1:250 k county maps
are the two free official candidates. Both are outside this sandbox's network; both must be fetched
and rasterised on the competition grid before any basin-floor hypothesis can be tested rather than
assumed.

## 4. Fix the lane-drift rule, in the shared template, once

The 70 %-within-3-px leg is unfalsifiable against any comparator whose halo covers most of the
footprint (32 of 340 here are formally "vacuous"; two more fire at 1.21–1.27× the uniform null).
The template should report, for every comparator, the **containment ratio to a uniform-random null**
alongside the raw fraction, and should treat only the ratio — plus ρ and Jaccard — as evidence. The
previous session proposed habitat nulls; a uniform null plus ρ and Jaccard is simpler and is
sufficient for the two comparators that fire here.

## 5. Do not spend more effort on band-restricted detectors

Experiment 2 measured eight band-restricted evidence surfaces, including the band's own uniform
null, all at 0.25–0.26× the random control. Whatever the truth is about basin-floor faults, a
detector that only fires inside a smooth, low-relief band cannot be validated with any instrument
this repository can build, and it measurably does not pay.

## 6. Housekeeping

* Commit the leaderboard scrape daily (the scheduled workflow already does) so the target stays
  current — the brief's target was stale by five ranks.
* Refresh `research/registry_measurements.json` as sibling repositories ship; the structural model
  (LOO R² = 0.586) is only as good as its 87 anchors, all of which are OWNER-REPORTED.
* `data/labels.tif` and `data/existing_faults.tif` being byte-identical
  ([IR-62-B-02](irregularities.md)) should be re-checked against a fresh
  DrivenData download; if the real `labels.tif` differs, several proxy numbers in the group change.

## Limitations that block the work

1. **No DrivenData credentials** — `training_features.tif`, `labels.tif`, `sample_submission.tif`
   and `1m_DEM_links.csv` all sit behind a login; the copies here are owner mirrors, hash-pinned
   but not organizer-authenticated.
2. **No general network** — only five hosts are reachable, so USGS TNM, ScienceBase, the Nevada
   Bureau and the GSA data repository cannot be queried from here. Anything from them has to be
   brought in by hand or by a GitHub runner.
3. **No organizer truth, by policy** — the test set is explicitly not shared (forum thread 11527).
4. **2 CPU / 3 GB RAM** — the surface pipeline was rewritten to cache float32 surfaces under
   `build/` for this reason; anything that needs the 418 MB stack in memory at once will not run.
5. **Weekly submission cap** — promotion to a real slot is a separate selector step.
