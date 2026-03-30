"""
report.py
=========
Generate output files and console summaries from v4 evaluation results.

Produces:
- v4_per_record_results.csv   (one row per PMCID, sorted by primary F1)
- v4_category_summary.json    (aggregate metrics by GT category)
- v4_results.json             (full results for programmatic consumption)
- Console summary table

All outputs include both strict F1 and loose (containment) F1 metrics
per DD-2026-019. The delta between them quantifies the "formatting tax."

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015, DD-2026-019
"""

import csv
import json
import logging
import statistics
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from collections import Counter

from evaluate.scorer import RecordResult

logger = logging.getLogger(__name__)


# ===========================================================================
# Main entry point
# ===========================================================================

def generate_report(
    results: List[RecordResult],
    output_dir: Path,
    run_label: str = "v4_baseline",
    model_name: str = "",
) -> None:
    """Write all output files and print console summary.

    Args:
        results: List of RecordResult objects from the v4 run.
        output_dir: Directory to write output files into (created if needed).
        run_label: Label for this run (used in filenames and metadata).
        model_name: Model identifier string for metadata.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_per_record_csv(results, output_dir / f"{run_label}_per_record_results.csv")
    write_category_summary(results, output_dir / f"{run_label}_category_summary.json",
                           run_label=run_label, model_name=model_name)
    write_full_results(results, output_dir / f"{run_label}_results.json",
                       run_label=run_label, model_name=model_name)
    print_summary(results, run_label=run_label)

    logger.info("Report generated in %s", output_dir)


# ===========================================================================
# Per-record CSV
# ===========================================================================

def write_per_record_csv(
    results: List[RecordResult],
    filepath: Path,
) -> None:
    """Write one row per PMCID, sorted by primary F1 ascending.

    Args:
        results: List of RecordResult objects.
        filepath: Output CSV file path.
    """
    headers = [
        "pmcid", "gt_category", "ext_category", "category_correct",
        "tp", "fp", "fn", "precision", "recall", "primary_f1",
        "loose_tp", "loose_fp", "loose_fn", "loose_f1",                        #changed_290326
        "gt_item_count", "ext_item_count", "error_message",
    ]

    sorted_results = sorted(results, key=lambda r: r.primary_f1)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        for r in sorted_results:
            row = {
                "pmcid": r.pmcid,
                "gt_category": r.gt_category,
                "ext_category": r.ext_category,
                "category_correct": r.category_correct,
                "tp": r.tp,
                "fp": r.fp,
                "fn": r.fn,
                "precision": f"{r.precision:.4f}",
                "recall": f"{r.recall:.4f}",
                "primary_f1": f"{r.primary_f1:.4f}",
                "loose_tp": r.loose_tp,                                        #changed_290326
                "loose_fp": r.loose_fp,                                        #changed_290326
                "loose_fn": r.loose_fn,                                        #changed_290326
                "loose_f1": f"{r.loose_f1:.4f}",                              #changed_290326
                "gt_item_count": r.gt_item_count,
                "ext_item_count": r.ext_item_count,
                "error_message": r.error_message,
            }
            writer.writerow(row)

    logger.info("Per-record CSV written: %s (%d rows)", filepath, len(results))


# ===========================================================================
# Category summary JSON
# ===========================================================================

def write_category_summary(
    results: List[RecordResult],
    filepath: Path,
    run_label: str = "",
    model_name: str = "",
) -> None:
    """Write aggregate metrics grouped by GT category.

    Args:
        results: List of RecordResult objects.
        filepath: Output JSON file path.
        run_label: Label for metadata.
        model_name: Model identifier for metadata.
    """
    summary = {
        "metadata": {
            "run_label": run_label,
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "total_records": len(results),
        },
        "overall": _compute_aggregate(results),
        "by_category": {},
        "classification_accuracy": _compute_classification_accuracy(results),
    }

    # Group by GT category
    by_category = {}
    for r in results:
        cat = r.gt_category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)

    for cat in sorted(by_category.keys()):
        summary["by_category"][cat] = _compute_aggregate(by_category[cat])

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info("Category summary written: %s", filepath)


def _compute_aggregate(results: List[RecordResult]) -> Dict[str, Any]:
    """Compute aggregate statistics for a set of results.

    Args:
        results: List of RecordResult objects.

    Returns:
        Dictionary with count, mean/median/min/max F1, total TP/FP/FN,
        and micro-averaged metrics.
    """
    if not results:
        return {"count": 0}

    f1_scores = [r.primary_f1 for r in results]
    loose_f1_scores = [r.loose_f1 for r in results]                            #changed_290326
    total_tp = sum(r.tp for r in results)
    total_fp = sum(r.fp for r in results)
    total_fn = sum(r.fn for r in results)

    # Loose totals (DD-2026-019)                                               #changed_290326
    total_loose_tp = sum(r.loose_tp for r in results)                          #changed_290326
    total_loose_fp = sum(r.loose_fp for r in results)                          #changed_290326
    total_loose_fn = sum(r.loose_fn for r in results)                          #changed_290326

    # Micro-averaged precision/recall/F1
    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    # Loose micro-averaged (DD-2026-019)                                       #changed_290326
    loose_micro_p = total_loose_tp / (total_loose_tp + total_loose_fp) if (total_loose_tp + total_loose_fp) > 0 else 0.0  #changed_290326
    loose_micro_r = total_loose_tp / (total_loose_tp + total_loose_fn) if (total_loose_tp + total_loose_fn) > 0 else 0.0  #changed_290326
    loose_micro_f1 = (2 * loose_micro_p * loose_micro_r) / (loose_micro_p + loose_micro_r) if (loose_micro_p + loose_micro_r) > 0 else 0.0  #changed_290326

    aggregate = {
        "count": len(results),
        "mean_f1": round(statistics.mean(f1_scores), 4),
        "median_f1": round(statistics.median(f1_scores), 4),
        "min_f1": round(min(f1_scores), 4),
        "max_f1": round(max(f1_scores), 4),
        "stdev_f1": round(statistics.stdev(f1_scores), 4) if len(f1_scores) > 1 else 0.0,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        # Loose metrics (DD-2026-019)                                          #changed_290326
        "loose_mean_f1": round(statistics.mean(loose_f1_scores), 4),           #changed_290326
        "loose_median_f1": round(statistics.median(loose_f1_scores), 4),       #changed_290326
        "total_loose_tp": total_loose_tp,                                      #changed_290326
        "total_loose_fp": total_loose_fp,                                      #changed_290326
        "total_loose_fn": total_loose_fn,                                      #changed_290326
        "loose_micro_f1": round(loose_micro_f1, 4),                            #changed_290326
    }

    return aggregate


def _compute_classification_accuracy(results: List[RecordResult]) -> Dict[str, Any]:
    """Compute category classification accuracy.

    Args:
        results: List of RecordResult objects.

    Returns:
        Dictionary with overall accuracy and per-category confusion counts.
    """
    if not results:
        return {"accuracy": 0.0}

    correct = sum(1 for r in results if r.category_correct)
    total = len(results)

    # Confusion breakdown
    confusion = Counter()
    for r in results:
        confusion[f"{r.gt_category}->{r.ext_category}"] += 1

    return {
        "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "confusion": dict(confusion.most_common()),
    }


# ===========================================================================
# Full results JSON
# ===========================================================================

def write_full_results(
    results: List[RecordResult],
    filepath: Path,
    run_label: str = "",
    model_name: str = "",
) -> None:
    """Write complete per-record results for programmatic consumption.

    Args:
        results: List of RecordResult objects.
        filepath: Output JSON file path.
        run_label: Label for metadata.
        model_name: Model identifier for metadata.
    """
    output = {
        "metadata": {
            "run_label": run_label,
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "total_records": len(results),
        },
        "records": [r.to_dict() for r in results],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Full results written: %s", filepath)


# ===========================================================================
# Console summary
# ===========================================================================

def print_summary(
    results: List[RecordResult],
    run_label: str = "",
) -> None:
    """Print a concise summary table to the console.

    Args:
        results: List of RecordResult objects.
        run_label: Label for the header.
    """
    if not results:
        print("No results to summarise.")
        return

    print(f"\n{'=' * 70}")
    print(f"  {run_label.upper()} SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total records evaluated: {len(results)}")

    # Overall metrics
    overall = _compute_aggregate(results)
    print(f"\n  --- Overall Metrics ---")
    print(f"  Mean F1 (macro):  {overall['mean_f1']:.4f}   Loose: {overall['loose_mean_f1']:.4f}   Delta: {overall['loose_mean_f1'] - overall['mean_f1']:+.4f}")  #changed_290326
    print(f"  Median F1:        {overall['median_f1']:.4f}   Loose: {overall['loose_median_f1']:.4f}")  #changed_290326
    print(f"  Stdev F1:         {overall['stdev_f1']:.4f}")
    print(f"  Micro F1:         {overall['micro_f1']:.4f}   Loose: {overall['loose_micro_f1']:.4f}   Delta: {overall['loose_micro_f1'] - overall['micro_f1']:+.4f}")  #changed_290326
    print(f"  Micro Precision:  {overall['micro_precision']:.4f}")
    print(f"  Micro Recall:     {overall['micro_recall']:.4f}")
    print(f"  Total TP/FP/FN:   {overall['total_tp']}/{overall['total_fp']}/{overall['total_fn']}")
    print(f"  Loose TP/FP/FN:   {overall['total_loose_tp']}/{overall['total_loose_fp']}/{overall['total_loose_fn']}")  #changed_290326

    # Per-category breakdown
    by_category = {}
    for r in results:
        cat = r.gt_category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)

    print(f"\n  --- Per-Category Breakdown ---")
    print(f"  {'Category':<12} {'Count':>6} {'Mean F1':>9} {'Loose F1':>9} {'Delta':>7} {'Micro F1':>10} {'TP':>6} {'FP':>6} {'FN':>6}")  #changed_290326
    print(f"  {'-' * 78}")                                                     #changed_290326

    for cat in sorted(by_category.keys()):
        cat_results = by_category[cat]
        cat_agg = _compute_aggregate(cat_results)
        delta = cat_agg['loose_mean_f1'] - cat_agg['mean_f1']                 #changed_290326
        print(
            f"  {cat:<12} {cat_agg['count']:>6} "
            f"{cat_agg['mean_f1']:>9.4f} {cat_agg['loose_mean_f1']:>9.4f} "   #changed_290326
            f"{delta:>+7.4f} "                                                 #changed_290326
            f"{cat_agg['micro_f1']:>10.4f} "
            f"{cat_agg['total_tp']:>6} {cat_agg['total_fp']:>6} {cat_agg['total_fn']:>6}"
        )

    # Classification accuracy
    cls_acc = _compute_classification_accuracy(results)
    print(f"\n  --- Category Classification ---")
    print(f"  Accuracy: {cls_acc['accuracy']:.4f} ({cls_acc['correct']}/{cls_acc['total']})")

    if cls_acc.get("confusion"):
        print(f"  Confusion (top misclassifications):")
        for pair, count in list(cls_acc["confusion"].items())[:10]:
            gt_cat, ext_cat = pair.split("->")
            marker = " " if gt_cat == ext_cat else " *"
            print(f"    {pair}: {count}{marker}")

    # Bottom 5 records (worst F1)
    sorted_by_f1 = sorted(results, key=lambda r: r.primary_f1)
    print(f"\n  --- Lowest F1 Records (bottom 5) ---")
    print(f"  {'PMCID':<15} {'Cat':>5} {'F1':>7} {'Loose':>7} {'TP':>5} {'FP':>5} {'FN':>5}")  #changed_290326
    print(f"  {'-' * 55}")                                                     #changed_290326
    for r in sorted_by_f1[:5]:
        print(
            f"  {r.pmcid:<15} {r.gt_category:>5} {r.primary_f1:>7.4f} "
            f"{r.loose_f1:>7.4f} "                                            #changed_290326
            f"{r.tp:>5} {r.fp:>5} {r.fn:>5}"
        )

    # Records with extraction errors
    error_records = [r for r in results if r.error_message]
    if error_records:
        print(f"\n  --- Extraction Errors ({len(error_records)}) ---")
        for r in error_records[:10]:
            print(f"    {r.pmcid}: {r.error_message[:80]}")

    print(f"\n{'=' * 70}")
