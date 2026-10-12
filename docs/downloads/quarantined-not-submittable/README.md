# QUARANTINED — do not submit anything in this folder

These two files are the diagnosis of the portal error the owner hit:

> **"Predicted values must be in range [0, 1]"**

They are kept because a negative result is a deliverable and because removing the
evidence would hide the defect. They are **not** submission candidates.

## What was measured, by re-reading the bytes

| file | `nodata` tag | NaN cells | values inside the footprint |
| --- | --- | --- | --- |
| `gems62-lahontan-isobase-99dots-nan.tif` (124,293 B) | `nan` | **7,111,787** | 0.0 and 1.0 |
| `gems62-h62-a-lahontan-isobase-step-38000dots-20261011T201324Z-nan.tif` (185,555 B) | `None` | **7,111,787** | 0.0 and 1.0 |

7,111,787 is exactly the number of cells **outside** the survey footprint
(12,279,160 total cells − 5,167,373 in-footprint cells). So both files encode
"outside the data" as NaN rather than as 0.

## Why that produces that error message

A range test applied to NaN is **False** under IEEE-754 (`np.nan >= 0` is False,
`np.nan <= 1` is False), and `min()`/`max()` over an array containing NaN returns
`nan`, which also fails a `[0, 1]` test. So any portal check written as
`all(0 <= v <= 1)` or `min(v) >= 0 and max(v) <= 1` rejects these bytes with exactly
that message.

**Evidence class: DIAGNOSIS, not an organizer statement.** The message text is the
owner's report of the portal's response; the mechanism above is measured from the
files' own bytes. The competition's own `sample_submission.tif` also carries
`nodata = nan` and the same 7,111,787 NaN cells, so "NaN outside" is clearly
*supported by the organizers' example* — but the portal evidently does not accept
it, and the error the owner saw is the operational fact. This repository therefore
ships **zeros outside the footprint and no nodata tag at all**, which cannot
trigger either mechanism.

## What replaced them

Every file that is offered for download from the site's hero block or from the
executive summary is checked by `tests/test_downloads_are_submittable.py`, which
re-reads each `docs/downloads/*.tif` from disk and asserts:

* single band, `float32`, EPSG:32611, 3730×3292, the sample submission's geotransform;
* `nodata is None`;
* zero NaN anywhere in the file;
* every value in `[0, 1]`.

A file that cannot pass all four can no longer sit in `docs/downloads/`. That is the
structural fix for the complaint, not a note asking the reader to be careful.
