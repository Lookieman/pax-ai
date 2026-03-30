"""
optimise - GEPA prompt optimisation for assay extraction.

Modules:
    data_loader      - Load split JSON, build DSPy Examples
    feedback_metric  - Two-tier GEPA feedback (GT comparison + XML cross-reference)
    run_gepa         - CLI entry point for GEPA optimisation
    run_holdout      - Holdout inference with optimised programme

Part of the v4 modular codebase (DD-2026-015).
GEPA main run design (DD-2026-018).

NOTE: This package was originally named 'gepa/' but was renamed to
'optimise/' to avoid a namespace collision with the pip-installed
'gepa' package that DSPy imports internally.
"""
