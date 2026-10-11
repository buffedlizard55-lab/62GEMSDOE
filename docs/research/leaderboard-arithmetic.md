# Why `h33-2-b2` scored 0.2778, and what would actually beat it

Every number on this page is either **MEASURED** in this checkout (script named), **MIRROR-OF-OFFICIAL**
(a timestamped machine scrape of the organizer's own page, mirrored from a sibling repository because
this sandbox cannot reach `drivendata.org`), **OWNER-REPORTED** (a score the owner quoted; no receipt),
or **MODEL** (algebra on the published metric — never written as a score).

---

## 1. The leaderboard is not where the brief says it is — MIRROR-OF-OFFICIAL

The official public leaderboard, scraped 2026-10-11T20:57:47Z by the scheduled workflow of
[`buffedlizard55-lab/12GEMSDOE`](https://github.com/buffedlizard55-lab/12GEMSDOE) and mirrored to
[`research/leaderboard_latest_2026-10-11T205747Z.json`](../../research/leaderboard_latest_2026-10-11T205747Z.json):

| rank | participant | score | submissions |
|---|---|---|---|
| 1 | xiaofanhu | **0.4133** | 16 |
| 2 | cfld__ | 0.3585 | 5 |
| 3 | JerryDataWorks | 0.3418 | 19 |
| 4 | alexoktaba | 0.3361 | 27 |
| 5 | joeyfezster | **0.3333** ← top-5 cut-off | 27 |
| 6 | Batik Shirt Brothers 1 | 0.3300 | 26 |
| 9 | DARD | 0.3195 | 18 |
| 23 | **extradr19** | **0.2778** ← this group's best | 15 |

**Correction to the standing brief, stated plainly:** `0.3195` is not the highest score — it was #1 on
2026-10-02/03 and is now **rank 9**. `0.2778` is **rank 23 of 50**. The number that actually matters is
the **top-5 cut-off, 0.3333**, i.e. `+0.0555` over the group's best. Targeting 0.3195 is targeting ninth
place. The series is in [`research/leaderboard_series.json`](../../research/leaderboard_series.json)
(37 timestamped snapshots, 2026-09-27 → 2026-10-11).

## 2. What 0.2778 is, measured from its bytes

`gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif` — fetched, hashed and measured here:

| property | value | class |
|---|---|---|
| positives | **37,654**, every one a single pixel (`n_components == M`) | MEASURED |
| values | exactly `{0, 1}` — a dot field, not a probability surface | MEASURED |
| mean self-kernel (dot within 300 m of another dot) | **0.017** | MEASURED |
| dots within 200 m of the mapped catalogue | **0.0 %** | MEASURED |
| median distance to the mapped catalogue | **1,965 m**; 70 % beyond 1 km | MEASURED |
| live score | 0.2778 | OWNER-REPORTED |

## 3. The arithmetic — this *is* the explanation

The published metric is `DTI = T / (T + 0.2·F + 0.8·(N − T))` with `T = TP_w`, `F = FP_w`,
`N` = total kernel-weighted hidden-truth mass. For **isolated unit dots** every dot contributes its
credit to `T` and the complement to `F`, so `T + F = M − E` where `E` is dot-to-dot overlap
(`E ≈ redun·M`). Hence

```
DTI  =  c·M / ( 0.2·(M − E) + 0.8·N )          c = mean 300 m kernel credit per dot
```

Four consequences, each of which is a design rule:

**(a) `DTI → 5c` as `M → ∞`.** The score is asymptotically **five times the mean per-dot credit**.
Nothing else matters at large mass. `#1` at 0.4133 therefore implies `c ≳ 0.0827`; the top-5 cut-off
0.3333 implies `c ≳ 0.0667`.

**(b) The hidden truth mass is bounded: `N ≤ 13,688` cells.** The 0.2778 file is a *thinning* of the
0.2600 file (44,090 → 37,654 dots). Thinning cannot *add* credit, so
`0.26·(0.2A₁ + 0.8N) ≥ 0.2778·(0.2A₂ + 0.8N)` with `A = M(1 − redun)`, which solves to
**N ≤ 13,688** — MEASURED here, independently of the sibling repository's 10,000–14,100 range.
At the planning value N = 12,000 the champion implies `c = 0.1254` and `T = 4,723`, i.e. **39 %
kernel-weighted recall of the faults that are absent from the USGS/INGENIOUS catalogue.**

**(c) At identical mass, placement quality spans 3.6×.** `GEMSDOE34 h34-scatter` carries the *same*
37,654 dots and scores 0.0778 → implied `c = 0.0344`. The champion at the same mass implies
`c = 0.1254`. Mass is not the lever; **detector quality is the entire game.**

**(d) Isolation is a hard rule, and it is the one thing the registry proves outright.**
Across the 87 score-anchored rasters (`research/registry_measurements.json`):

| class | n | best score | median score |
|---|---|---|---|
| isolated fields (mean self-kernel < 0.05) | 29 | **0.2778** | 0.1839 |
| clustered fields (mean self-kernel ≥ 0.23) | 56 | 0.2477 | 0.1152 |

Every one of the top nine distinct score levels (0.2778 … 0.2600) has mean self-kernel **0.016–0.018**
— no second dot inside the 300 m kernel. Every raster with self-kernel ≥ 0.23 scores ≤ 0.2477.
Clustering burns denominator for no numerator: `0.2·M` is paid on *every* dot, but `T` saturates.

## 4. What each target requires — MODEL, from `research/leaderboard_arithmetic.json`

Mean per-dot credit `c` needed, at planning truth mass N = 12,000:

| target | M = 37,654 | M = 44,090 | M = 60,000 | M = 120,000 |
|---|---|---|---|---|
| 0.2778 (rank 23) | 0.1264 | 0.1161 | 0.1000 | 0.0778 |
| 0.3195 (rank 9) | 0.1454 | 0.1335 | 0.1150 | 0.0895 |
| **0.3333 (top-5)** | **0.1516** | **0.1392** | **0.1200** | **0.0933** |
| 0.3585 (rank 2) | 0.1631 | 0.1498 | 0.1291 | 0.1004 |
| 0.4133 (rank 1) | 0.1880 | 0.1727 | 0.1488 | 0.1157 |

Read the table with the champion's own measured `c = 0.1254` in hand: **at the champion's mass the
group is one 20 % detector improvement away from the top-5 cut-off**, and at 120,000 isolated dots it
needs `c = 0.0933` — *below* what the champion already achieves at 37,654. Both routes are open;
neither is a re-emission of an existing field.

## 5. The single largest unexploited fact this session found

`research/registry_index.json` is the score-anchored registry: **87 distinct group rasters with an
owner-reported score**, harvested from every public `buffedlizard55-lab` repository (73 scanned,
1,459 `.tif` blobs, 166 registry/ledger JSONs fetched, 473 scored rows de-duplicated to 87).

Cross-referencing that registry against the per-dot credit measured on one independent instrument
(`evidence/h62g/h62i.json`, SGMC 1:750k off-catalogue):

| field | dots | mean 300 m credit/dot | ever submitted? |
|---|---|---|---|
| **`gems32-bayesopt-dilation-scarp-d28-20261004`** | 45,000 | **0.29294** | **NO** |
| `gems25-dotted-h19-5-d2-8` (submitted family) | 44,090 | 0.09892 | yes → 0.2600 |
| this session, H62-I | 60,000 | 0.08666 | no |
| isolated-random control | 44,090 | 0.04331 | — |

The group's **highest-credit detector has never been submitted.** At 45,000 dots and `c = 0.29294`
the closed form gives a MODEL value of 0.71 at N = 12,000 — which is why that number must be
discounted hard: instrument B is a geological *compilation*, and a compilation favours scarp-like
geomorphology over genuinely new faults. Even at a 4× discount it clears the top-5 cut-off.

This session did **not** copy it — the standing brief forbids copying a previous submission. It is
recorded as the selector's rank-1 action, with the file's exact repository path and byte size, in
[`../run-card.md`](../run-card.md).

## 6. What this session's own lane measured — two refutations

Screened at M = 44,090 against an **isolated-random control (0.04281)** on instrument B
(`evidence/h62g/exp2.json`):

| field | credit | vs control | verdict |
|---|---|---|---|
| pluvial lake-flat habitat (low slope, low relief, below datum) | 0.00118 | **0.03×** | **REFUTED** |
| Lahontan datum band, 1308–1360 m | 0.02614 | **0.61×** | **REFUTED** |
| 500–2000 m off the catalogue | 0.04688 | 1.10× | no edge |
| > 2 km off the catalogue | 0.03909 | 0.91× | no edge |
| LiDAR `step_max`, hard-core sampled | 0.09255 | 2.16× | real edge |
| LiDAR `cross_max`, hard-core sampled | 0.09524 | 2.22× | real edge |

This is the honest reason four sessions of datum-only lanes have lost: **on this instrument the
shoreline datum band is *below* chance.** Two readings, both recorded: either the datum band is
genuinely not fault-rich, or instrument B — a 1:750 k geological compilation — cannot see
2-metre datum offsets at all and is biased toward scarps it already maps. The two cannot be
separated without the organizer's truth, which they will not share
([thread 11527](https://www.drivendata.org/competitions/306/competition-doe-gems/forum/), staff).

## 7. What this page does **not** claim

It does not claim 0.2778 is reproducible, that any file in this repository is comparable to it, or
that `c` measured on instrument B transfers to the organizer's score. The recall figure in §3(b) is a
*necessary condition* implied by an OWNER-REPORTED score, not a measurement of that artifact's truth.
No file in this repository has ever been scored by the organizer.
