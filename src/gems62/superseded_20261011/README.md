# Superseded modules (parallel session, 2026-10-11)

These are the `gems62.metric` / `gems62.grid` implementations from `main` (the earlier 99-dot
`gems62-lahontan-isobase` run of the same assigned lane). They are **not imported by anything** in
this branch's pipeline, and they are kept only so that no work is lost in the merge.

The canonical modules at `src/gems62/{metric,grid}.py` are the ones used by the lane and the
delivered artifact: `metric.dti_binary/dti_from_components/kernel/marginal_bar` and
`grid.write_submission/check_submission/load_catalogue/sha256`.

If you need to re-run the earlier scripts (`lane_check_surface.py`, `make_site.py`,
`make_figures.py`, `make_readme.py`) that were written against the earlier API, either restore
these two files over the canonical ones or adapt their imports --- the two APIs are not
compatible (`dti`/`dti_components`/`write_float32`/`load_scene` versus
`dti_binary`/`dti_from_components`/`write_submission`/`check_submission`).
