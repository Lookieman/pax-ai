"""
filter_holdout.py
=================
Filter a v4 baseline results JSON to the holdout subset defined in
the GEPA splits file, and produce a holdout-specific summary.

This avoids re-running extraction on the holdout — the baseline already
contains results for all 148/149 records including the 31 holdout PMCIDs.

Usage:
    python filter_holdout.py --results path/to/v4_baseline_sonnet_results.json
    python filter_holdout.py --results path/to/results.json --splits path/to/splits.json
    python filter_holdout.py --results path/to/results.json --output-label v4_baseline_sonnet_holdout

Output:
    <output_dir>/<label>_per_record_results.csv
    <output_dir>/<label>_category_summary.json
    <output_dir>/<label>_results.json
    Console summary

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-018
"""

import sys
import json
import argparse
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution: ensure src/ is on sys.path
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import cfg                                                         # noqa: E402
from evaluate.scorer import RecordResult                                       # noqa: E402
from evaluate.report import generate_report                                    # noqa: E402

logger = logging.getLogger(__name__)


# ===========================================================================
# Argument parsing
# ===========================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Filter baseline results to holdout subset (DD-2026-018)."
    )

    parser.add_argument(
        "--results",
        type=Path,
        required=True,
        help="Path to the full baseline results JSON (e.g. v4_baseline_sonnet_results.json).",
    )
    parser.add_argument(
        "--splits",
        type=Path,
        default=None,
        help="Path to splits JSON (default: from config GEPA_SPLITS_FILE).",
    )
    parser.add_argument(
        "--output-label",
        type=str,
        default=None,
        help="Output label (default: <original_label>_holdout).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same directory as results file).",
    )

    return parser.parse_args()


# ===========================================================================
# RecordResult reconstruction
# ===========================================================================

def dict_to_record_result(d: dict) -> RecordResult:
    """Reconstruct a RecordResult from a serialised dictionary.

    Handles both the full field set (with loose metrics) and legacy
    results without loose fields.

    Args:
        d: Dictionary from the results JSON.

    Returns:
        RecordResult instance.
    """
    r = RecordResult()

    r.pmcid = d.get("pmcid", "")
    r.gt_category = d.get("gt_category", "")
    r.ext_category = d.get("ext_category", "")
    r.category_correct = d.get("category_correct", False)

    r.tp = d.get("tp", 0)
    r.fp = d.get("fp", 0)
    r.fn = d.get("fn", 0)

    r.precision = d.get("precision", 0.0)
    r.recall = d.get("recall", 0.0)
    r.primary_f1 = d.get("primary_f1", 0.0)

    # Loose metrics (DD-2026-019) — default to strict if absent               #changed
    r.loose_tp = d.get("loose_tp", r.tp)                                       #changed
    r.loose_fp = d.get("loose_fp", r.fp)                                       #changed
    r.loose_fn = d.get("loose_fn", r.fn)                                       #changed
    r.loose_f1 = d.get("loose_f1", r.primary_f1)                              #changed

    r.field_scores = d.get("field_scores", {})
    r.tp_items = d.get("tp_items", [])
    r.fp_items = d.get("fp_items", [])
    r.fn_items = d.get("fn_items", [])
    r.gt_item_count = d.get("gt_item_count", 0)
    r.ext_item_count = d.get("ext_item_count", 0)
    r.error_message = d.get("error_message", "")

    return r


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Filter baseline results to holdout and generate holdout-specific report."""

    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=cfg.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # --- Load results ---
    if not args.results.exists():
        logger.error("Results file not found: %s", args.results)
        return

    with open(args.results, "r", encoding="utf-8") as f:
        results_data = json.load(f)

    all_records = results_data.get("records", [])
    original_label = results_data.get("metadata", {}).get("run_label", "baseline")
    original_model = results_data.get("metadata", {}).get("model", "")

    logger.info("Loaded %d records from %s", len(all_records), args.results)

    # --- Load splits ---
    splits_filepath = args.splits or Path(cfg.GEPA_SPLITS_FILE)

    if not splits_filepath.exists():
        logger.error("Splits file not found: %s", splits_filepath)
        return

    with open(splits_filepath, "r", encoding="utf-8") as f:
        splits = json.load(f)

    holdout_golden = splits["holdout_test_set"]["golden"]
    holdout_supp = splits["holdout_test_set"]["supplement"]
    holdout_pmcids = set(holdout_golden + holdout_supp)

    logger.info(
        "Holdout set: %d PMCIDs (%d golden + %d supplement)",
        len(holdout_pmcids), len(holdout_golden), len(holdout_supp),
    )

    # --- Filter ---
    holdout_dicts = [r for r in all_records if r.get("pmcid") in holdout_pmcids]
    found_pmcids = {r.get("pmcid") for r in holdout_dicts}
    missing = holdout_pmcids - found_pmcids

    if missing:
        logger.warning(
            "%d holdout PMCIDs not found in results: %s",
            len(missing), sorted(missing)[:10],
        )

    logger.info(
        "Filtered: %d holdout records from %d total",
        len(holdout_dicts), len(all_records),
    )

    # --- Reconstruct RecordResult objects ---
    holdout_results = [dict_to_record_result(d) for d in holdout_dicts]

    # --- Output ---
    output_label = args.output_label or f"{original_label}_holdout"
    output_dir = args.output_dir or args.results.parent

    # --- Pre-filter summary ---
    print(f"\n{'=' * 60}")
    print(f"  HOLDOUT FILTER")
    print(f"{'=' * 60}")
    print(f"  Source:           {args.results}")
    print(f"  Total records:    {len(all_records)}")
    print(f"  Holdout PMCIDs:   {len(holdout_pmcids)}")
    print(f"  Matched:          {len(holdout_results)}")
    print(f"  Missing:          {len(missing)}")
    print(f"  Output label:     {output_label}")
    print(f"  Output dir:       {output_dir}")
    print(f"{'=' * 60}\n")

    # --- Generate report using the existing report module ---
    generate_report(
        results=holdout_results,
        output_dir=output_dir,
        run_label=output_label,
        model_name=original_model,
    )

    logger.info("Holdout filter complete. Output: %s", output_dir)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
