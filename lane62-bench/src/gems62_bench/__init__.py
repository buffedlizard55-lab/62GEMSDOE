"""gems62_bench — the 62GEMSDOE lane62-bench datum-offset lane.

Vendored under its own package name so the trunk's ``src/gems62`` (which has its
own, differently-shaped ``grid/metric/validate/uniqueness/lahontan``) is neither
shadowed nor clobbered; see ``lane62-bench/README.md``. (Lahontan shoreline strain gauge).

Shared modules (grid, metric, validate, uniqueness, network, holdout_segmented,
submission_writer, emit) are byte-copied from the family template
`61GEMSDOE/src/gems61/` so that every lane scores with the same instrument.
"""
__all__ = ["grid", "metric", "validate", "uniqueness", "network",
           "holdout_segmented", "submission_writer", "emit", "lahontan", "features"]
