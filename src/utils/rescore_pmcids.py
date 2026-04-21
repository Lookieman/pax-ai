"""
rescore_pmcids.py
=================
Re-score specific PMCIDs against updated ground truth files without
re-running LLM inference. Reads existing raw extractions from a
previous holdout run, re-evaluates them against the current GT,
replaces the affected records in the results, and regenerates
the report.

Use when GT files have been corrected but the LLM extraction output
has not changed.

Usage:
    # Re-score 3 PMCIDs across one holdout run
    python rescore_pmcids.py --results path/to/gepa_holdout_results.json --pmcids PMC7478631 PMC4881965 PMC9610186

    # Re-score across multiple holdout runs at once
    python rescore_pmcids.py --results-dir C:/proj/pax-ai-working/assay/gt_diagnostic_analysis --pmcids PMC7478631 PMC4881965 PMC9610186

    # Dry run: show what would change without writing
    python rescore_pmcids.py --results path/to/results.json --pmcids PMC7478631 --dry-run

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import cfg                                                         # noqa: E402
from extract.extractor import parse_extraction_output                          # noqa: E402
from evaluate.scorer import score_record, RecordResult                         # noqa: E402
from evaluate.report import generate_report                                    # noqa: E402

logger = logging.getLogger(__name__)


# ===========================================================================
# GT Loading (direct file read, no dependency on article_loader)
# ===========================================================================

def _load_gt_json(pmcid: str, gt_dir: Path) -> dict:                          #changed
    """Load a GT JSON file from a directory. Returns None if not found."""      #changed
    filepath = gt_dir / f"{pmcid}.json"                                        #changed
    if not filepath.exists():                                                  #changed
        return None                                                            #changed
    with open(filepath, "r", encoding="utf-8") as f:                           #changed
        return json.load(f)                                                    #changed


# ===========================================================================
# Argument parsing
# ===========================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Re-score specific PMCIDs against updated GT (no LLM calls)."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--results",
        type=Path,
        default=None,
        help="Path to a single holdout results JSON file.",
    )
    input_group.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Directory containing multiple holdout run subdirectories. "
             "Scans for *_results.json in each subdirectory.",
    )

    parser.add_argument(
        "--pmcids",
        nargs="+",
        required=True,
        help="PMCIDs to re-score (space-separated).",
    )
    parser.add_argument(
        "--gt-dir",
        type=Path,
        default=None,
        help="Override GT directory (default: from config).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files.",
    )

    return parser.parse_args()


# ===========================================================================
# Core logic
# ===========================================================================

def dict_to_record_result(d: dict) -> RecordResult:
    """Reconstruct a RecordResult from a serialised dictionary."""
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
    r.loose_tp = d.get("loose_tp", r.tp)
    r.loose_fp = d.get("loose_fp", r.fp)
    r.loose_fn = d.get("loose_fn", r.fn)
    r.loose_f1 = d.get("loose_f1", r.primary_f1)
    r.field_scores = d.get("field_scores", {})
    r.tp_items = d.get("tp_items", [])
    r.fp_items = d.get("fp_items", [])
    r.fn_items = d.get("fn_items", [])
    r.gt_item_count = d.get("gt_item_count", 0)
    r.ext_item_count = d.get("ext_item_count", 0)
    r.error_message = d.get("error_message", "")
    return r


def rescore_single_run(
    results_path: Path,
    target_pmcids: set,
    gt_dir_main: Path,
    gt_dir_golden: Path,
    dry_run: bool = False,
) -> dict:
    """Re-score target PMCIDs in a single results file.

    Args:
        results_path: Path to the *_results.json file.
        target_pmcids: Set of PMCIDs to re-score.
        gt_dir_main: Primary GT directory.
        gt_dir_golden: Golden GT directory.
        dry_run: If True, do not write files.

    Returns:
        Summary dict with counts and F1 changes.
    """
    # Load existing results
    with open(results_path, "r", encoding="utf-8") as f:
        results_data = json.load(f)

    all_records = results_data.get("records", [])
    run_label = results_data.get("metadata", {}).get("run_label", "unknown")
    model_name = results_data.get("metadata", {}).get("model", "")

    # Find the raw_extractions directory (sibling of results file)
    run_dir = results_path.parent
    raw_dir = run_dir / "raw_extractions"

    rescored = 0
    not_found = []
    no_raw = []
    changes = []

    for i, record_dict in enumerate(all_records):
        pmcid = record_dict.get("pmcid", "")
        if pmcid not in target_pmcids:
            continue

        # Load updated GT (golden first, then main)                          #changed
        gt_data = _load_gt_json(pmcid, gt_dir_golden)                          #changed
        if gt_data is None:                                                    #changed
            gt_data = _load_gt_json(pmcid, gt_dir_main)                        #changed
        if gt_data is None:
            not_found.append(pmcid)
            continue

        # Load existing raw extraction
        raw_path = raw_dir / f"{pmcid}_extraction.json"
        if not raw_path.exists():
            no_raw.append(pmcid)
            continue

        with open(raw_path, "r", encoding="utf-8") as f:
            raw_record = json.load(f)

        ext_data = raw_record.get("parsed_output", {})
        if not ext_data:
            raw_output = raw_record.get("raw_output", "")
            ext_data = parse_extraction_output(raw_output)

        # Re-score
        old_f1 = record_dict.get("primary_f1", 0.0)
        old_loose = record_dict.get("loose_f1", old_f1)

        new_result = score_record(
            pmcid=pmcid,
            gt_data=gt_data,
            ext_data=ext_data,
        )

        # Record the change
        changes.append({
            "pmcid": pmcid,
            "old_f1": round(old_f1, 4),
            "new_f1": round(new_result.primary_f1, 4),
            "delta_f1": round(new_result.primary_f1 - old_f1, 4),
            "old_loose_f1": round(old_loose, 4),
            "new_loose_f1": round(new_result.loose_f1, 4),
            "old_tp_fp_fn": (
                record_dict.get("tp", 0),
                record_dict.get("fp", 0),
                record_dict.get("fn", 0),
            ),
            "new_tp_fp_fn": (new_result.tp, new_result.fp, new_result.fn),
        })

        # Replace in the records list
        all_records[i] = new_result.to_dict()
        rescored += 1

    # Print changes
    print(f"\n  {'=' * 60}")
    print(f"  {run_label}")
    print(f"  {'=' * 60}")
    print(f"  Results file: {results_path}")
    print(f"  Raw extractions: {raw_dir}")
    print(f"  Rescored: {rescored} / {len(target_pmcids)}")

    if not_found:
        print(f"  GT not found: {not_found}")
    if no_raw:
        print(f"  Raw extraction not found: {no_raw}")

    for c in changes:
        direction = "+" if c["delta_f1"] >= 0 else ""
        print(
            f"  {c['pmcid']}: F1 {c['old_f1']:.4f} -> {c['new_f1']:.4f} "
            f"({direction}{c['delta_f1']:.4f})  "
            f"Loose {c['old_loose_f1']:.4f} -> {c['new_loose_f1']:.4f}  "
            f"TP/FP/FN {c['old_tp_fp_fn']} -> {c['new_tp_fp_fn']}"
        )

    if dry_run:
        print(f"  [DRY RUN] No files written.")
        return {"run_label": run_label, "rescored": rescored, "changes": changes}

    # Rebuild RecordResult objects for report generation
    all_record_results = [dict_to_record_result(d) for d in all_records]

    # Regenerate report
    generate_report(
        results=all_record_results,
        output_dir=run_dir,
        run_label=run_label,
        model_name=model_name,
    )

    print(f"  Report regenerated in {run_dir}")

    return {"run_label": run_label, "rescored": rescored, "changes": changes}


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Re-score PMCIDs and regenerate reports."""

    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=cfg.LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    target_pmcids = set(args.pmcids)
    print(f"\nRe-scoring {len(target_pmcids)} PMCIDs: {sorted(target_pmcids)}")

    # Resolve GT directories
    gt_dir_main = Path(args.gt_dir) if args.gt_dir else Path(cfg.GROUND_TRUTH_PATH)
    gt_dir_golden = Path(cfg.GOLDEN_GT_PATH)
    print(f"GT main:   {gt_dir_main}")
    print(f"GT golden: {gt_dir_golden}")

    # Collect results files
    results_files = []

    if args.results:
        results_files.append(args.results)
    elif args.results_dir:
        # Scan subdirectories for *_results.json
        for subdir in sorted(args.results_dir.iterdir()):
            if not subdir.is_dir():
                continue
            for f in subdir.glob("*_results.json"):
                # Skip category_summary files
                if "category_summary" in f.name:
                    continue
                if "per_record" in f.name:
                    continue
                results_files.append(f)

    if not results_files:
        print("No results files found.")
        return

    print(f"\nFound {len(results_files)} results file(s):")
    for rf in results_files:
        print(f"  {rf}")

    # Process each results file
    all_summaries = []
    for results_path in results_files:
        if not results_path.exists():
            print(f"\n  SKIPPED (not found): {results_path}")
            continue

        summary = rescore_single_run(
            results_path=results_path,
            target_pmcids=target_pmcids,
            gt_dir_main=gt_dir_main,
            gt_dir_golden=gt_dir_golden,
            dry_run=args.dry_run,
        )
        all_summaries.append(summary)

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"  RESCORE COMPLETE")
    print(f"{'=' * 60}")
    total_rescored = sum(s["rescored"] for s in all_summaries)
    print(f"  Runs processed: {len(all_summaries)}")
    print(f"  Total records rescored: {total_rescored}")
    if args.dry_run:
        print(f"  [DRY RUN] No files were modified.")
    print(f"{'=' * 60}\n")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
