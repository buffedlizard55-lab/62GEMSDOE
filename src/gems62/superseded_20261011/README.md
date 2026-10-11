# Historical modules (parallel session, 2026-10-11)

These are the original `gems62.metric` / `gems62.grid` implementations from the earlier 99-dot
`gems62-lahontan-isobase` run of the same assigned lane. The files remain here as a readable
historical reference; they are not the grid IO or writer used by the current submission pipeline.

The canonical public modules are `src/gems62/{metric,grid}.py`. The metric module re-exports the
physical-unit `Components`, `dti_components`, `brute_force_components`, `maximum_useful_distance_m`
and `unit_dot_dti` compatibility functions from this directory because the shared holdout and
root test suite use that API. New callers should import only from `gems62.metric`, not from this
archive. The grid module defines `PIXEL_M` from its measured `GRID["res"]` for shared callers.

The canonical submission path remains `metric.dti_binary/dti_from_components/kernel/marginal_bar`
and `grid.write_submission/check_submission/load_catalogue/sha256`. Legacy helpers such as
`write_float32` and `load_scene` are not part of the active writer contract; the archive is kept
so earlier scripts and provenance are not lost.
