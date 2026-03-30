"""
scorer.py
=========
Category-specific scoring for v4 assay extraction evaluation.

Replaces the monolithic v3 compare_and_score with three category-specific
scorers (IWL, IWOL, NIOAI).  The UP metric from v3 is dropped; only
standard TP/FP/FN/F1 are computed.

The GT category determines which scorer is used (ground truth is
authoritative for evaluation mode).

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Any

from evaluate.normalise import (
    flatten_by_category,
    normalise_field,
    normalise_value,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Result data structure
# ===========================================================================

@dataclass
class RecordResult:
    """Evaluation result for a single PMCID."""

    pmcid: str = ""
    gt_category: str = ""
    ext_category: str = ""
    category_correct: bool = False

    # Counts
    tp: int = 0
    fp: int = 0
    fn: int = 0

    # Metrics
    precision: float = 0.0
    recall: float = 0.0
    primary_f1: float = 0.0

    # Loose (containment) metrics (DD-2026-019)                                #changed
    loose_tp: int = 0                                                          #changed
    loose_fp: int = 0                                                          #changed
    loose_fn: int = 0                                                          #changed
    loose_f1: float = 0.0                                                      #changed

    # Per-field breakdown: {field_name: {tp, fp, fn, f1}}
    field_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Debug samples (first N items for inspection)
    tp_items: List[str] = field(default_factory=list)
    fp_items: List[str] = field(default_factory=list)
    fn_items: List[str] = field(default_factory=list)

    # Metadata
    gt_item_count: int = 0
    ext_item_count: int = 0
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return asdict(self)


# ===========================================================================
# Main scoring entry point
# ===========================================================================

def score_record(
    pmcid: str,
    gt_data: Dict,
    ext_data: Dict,
    max_samples: int = 5,
) -> RecordResult:
    """Score a single extraction against its ground truth.

    The GT category is authoritative: it determines which scoring function
    is used.  If the extraction classified into a different category, that
    is recorded as a classification error but the GT-category scorer is
    still applied to whatever data the extraction produced.

    Args:
        pmcid: PubMed Central ID for this record.
        gt_data: Ground truth dict (v4 3-category structure).
        ext_data: Extraction dict (v4 3-category structure).
        max_samples: Maximum number of sample items to store per category.

    Returns:
        RecordResult with all metrics populated.
    """
    result = RecordResult(pmcid=pmcid)

    # Flatten both sides
    gt_flat = flatten_by_category(gt_data)
    ext_flat = flatten_by_category(ext_data)

    result.gt_category = gt_flat["category"]
    result.ext_category = ext_flat["category"]
    result.category_correct = (result.gt_category == result.ext_category)

    # Count items
    result.gt_item_count = _count_items(gt_flat)
    result.ext_item_count = _count_items(ext_flat)

    # Dispatch to category-specific scorer based on GT category
    if result.gt_category in ("IWL", "IWL+IWOL"):
        _score_iwl(gt_flat, ext_flat, result, max_samples)
    elif result.gt_category == "IWOL":
        _score_iwol(gt_flat, ext_flat, result, max_samples)
    elif result.gt_category == "NIOAI":
        _score_nioai(gt_flat, ext_flat, result, max_samples)
    elif result.gt_category == "EMPTY":
        # Empty GT: any extraction is FP
        result.fp = result.ext_item_count
        result.loose_fp = result.ext_item_count                                #changed
        logger.warning("PMCID %s has EMPTY GT category", pmcid)
    else:
        logger.warning("Unknown GT category '%s' for %s", result.gt_category, pmcid)

    # Compute F1
    _compute_f1(result)

    # Compute per-field breakdown
    _compute_field_scores(gt_flat, ext_flat, result)

    return result


# ===========================================================================
# Loose (containment) matching (DD-2026-019)
# ===========================================================================

def _is_loose_match(gt_norm: str, ext_norm: str) -> bool:                      #changed
    """Check if GT value is contained within extraction value (token-level).   #changed
                                                                               #changed
    Returns True if all tokens of the shorter value appear in the              #changed
    longer value's token set. Prevents false matches like 'st1' in 'st10'.    #changed
                                                                               #changed
    Args:                                                                      #changed
        gt_norm: Normalised ground truth value.                                #changed
        ext_norm: Normalised extraction value.                                 #changed
                                                                               #changed
    Returns:                                                                   #changed
        True if token-level containment is satisfied.                          #changed
    """                                                                        #changed
    gt_tokens = set(gt_norm.split())                                           #changed
    ext_tokens = set(ext_norm.split())                                         #changed
                                                                               #changed
    if not gt_tokens or not ext_tokens:                                        #changed
        return False                                                           #changed
                                                                               #changed
    # All tokens of the shorter must appear in the longer                      #changed
    shorter = gt_tokens if len(gt_tokens) <= len(ext_tokens) else ext_tokens   #changed
    longer = gt_tokens if len(gt_tokens) > len(ext_tokens) else ext_tokens     #changed
                                                                               #changed
    return shorter.issubset(longer)                                            #changed


def _loose_recover(                                                            #changed
    strict_fp_items: list,                                                     #changed
    strict_fn_items: list,                                                     #changed
    ext_items_by_key: dict,                                                    #changed
    gt_items_by_key: dict,                                                     #changed
) -> int:                                                                      #changed
    """Run a second pass on strict FP/FN pairs to find containment matches.    #changed
                                                                               #changed
    For each strict FP, check if it loose-matches any strict FN on the         #changed
    same normalised field. If so, count as a loose TP recovery.                #changed
                                                                               #changed
    Args:                                                                      #changed
        strict_fp_items: List of FP key strings ('iso_id|field=value').        #changed
        strict_fn_items: List of FN key strings ('iso_id|field=value').        #changed
        ext_items_by_key: Dict mapping ext key -> (norm_field, orig, norm_val).#changed
        gt_items_by_key: Dict mapping gt key -> (norm_field, orig, norm_val).  #changed
                                                                               #changed
    Returns:                                                                   #changed
        Number of recovered matches (loose TP).                                #changed
    """                                                                        #changed
    recovered = 0                                                              #changed
    fn_used = set()                                                            #changed
                                                                               #changed
    for fp_str in strict_fp_items:                                             #changed
        # Parse key from 'iso_id|field=value...' format                        #changed
        fp_key = fp_str.split("=")[0].strip()                                  #changed
        if fp_key not in ext_items_by_key:                                     #changed
            continue                                                           #changed
        fp_field, fp_orig, fp_norm = ext_items_by_key[fp_key]                  #changed
                                                                               #changed
        for fn_str in strict_fn_items:                                         #changed
            fn_key = fn_str.split("=")[0].strip()                              #changed
            if fn_key in fn_used:                                              #changed
                continue                                                       #changed
            if fn_key not in gt_items_by_key:                                  #changed
                continue                                                       #changed
            fn_field, fn_orig, fn_norm = gt_items_by_key[fn_key]               #changed
                                                                               #changed
            # Must be the same field type                                      #changed
            if fp_field != fn_field:                                           #changed
                continue                                                       #changed
                                                                               #changed
            if _is_loose_match(fn_norm, fp_norm):                              #changed
                recovered += 1                                                 #changed
                fn_used.add(fn_key)                                            #changed
                break                                                          #changed
                                                                               #changed
    return recovered                                                           #changed


# ===========================================================================
# Category-specific scorers
# ===========================================================================

def _score_iwl(
    gt_flat: Dict,
    ext_flat: Dict,
    result: RecordResult,
    max_samples: int,
) -> None:
    """Score IWL (Isolates With Linking) records.

    Matching logic:
    1. Exact match: same isolate ID + same field + same normalised value.
    2. Lenient match: different isolate ID but same field + same normalised
       value (handles ID format mismatches between GT and extraction).

    Modifies result in place.
    """
    gt_iwl = gt_flat["iwl_flat"]
    ext_iwl = ext_flat["iwl_flat"]

    # Build normalised GT items: key -> (orig_value, norm_value)
    gt_items = {}
    for iso_id, fields in gt_iwl.items():
        for norm_field, (orig_value, norm_value) in fields.items():
            key = f"{iso_id}|{norm_field}"
            gt_items[key] = (norm_field, orig_value, norm_value)

    # Build normalised extraction items
    ext_items = {}
    for iso_id, fields in ext_iwl.items():
        for norm_field, (orig_value, norm_value) in fields.items():
            key = f"{iso_id}|{norm_field}"
            ext_items[key] = (norm_field, orig_value, norm_value)

    # Build value-based lookup for lenient matching
    gt_by_field_value = {}
    for key, (norm_field, orig_value, norm_value) in gt_items.items():
        fv_key = f"{norm_field}|{norm_value}"
        if fv_key not in gt_by_field_value:
            gt_by_field_value[fv_key] = key

    matched_gt = set()
    tp_items = []
    fp_items = []

    # Match extractions against GT
    for ext_key, (norm_field, orig_value, norm_value) in ext_items.items():
        # Attempt 1: exact key match (same isolate ID + same field)
        if ext_key in gt_items:
            gt_nf, gt_ov, gt_nv = gt_items[ext_key]
            if gt_nv == norm_value:
                tp_items.append(f"{ext_key}={str(orig_value)[:50]}")
                matched_gt.add(ext_key)
                continue

        # Attempt 2: lenient match (different ID, same field+value)
        fv_key = f"{norm_field}|{norm_value}"
        if fv_key in gt_by_field_value:
            gt_key = gt_by_field_value[fv_key]
            if gt_key not in matched_gt:
                tp_items.append(
                    f"{ext_key}={str(orig_value)[:50]} "
                    f"(value-matched to {gt_key})"
                )
                matched_gt.add(gt_key)
                continue

        # No match -> FP
        fp_items.append(f"{ext_key}={str(orig_value)[:50]}")

    # FN: unmatched GT items
    fn_items = []
    for gt_key, (norm_field, orig_value, norm_value) in gt_items.items():
        if gt_key not in matched_gt:
            fn_items.append(f"{gt_key}={str(orig_value)[:50]}")

    result.tp = len(tp_items)
    result.fp = len(fp_items)
    result.fn = len(fn_items)
    result.tp_items = tp_items[:max_samples]
    result.fp_items = fp_items[:max_samples]
    result.fn_items = fn_items[:max_samples]

    # --- Loose matching pass (DD-2026-019) ---                                #changed
    loose_recovered = _loose_recover(                                          #changed
        strict_fp_items=fp_items,                                              #changed
        strict_fn_items=fn_items,                                              #changed
        ext_items_by_key=ext_items,                                            #changed
        gt_items_by_key=gt_items,                                              #changed
    )                                                                          #changed
    result.loose_tp = result.tp + loose_recovered                              #changed
    result.loose_fp = result.fp - loose_recovered                              #changed
    result.loose_fn = result.fn - loose_recovered                              #changed


def _score_iwol(
    gt_flat: Dict,
    ext_flat: Dict,
    result: RecordResult,
    max_samples: int,
) -> None:
    """Score IWOL (Isolates Without Linking) records.

    Compares isolate ID sets using case-insensitive matching.

    Modifies result in place.
    """
    gt_ids = {s.lower().strip() for s in gt_flat["iwol_ids"]}
    ext_ids = {s.lower().strip() for s in ext_flat["iwol_ids"]}

    tp_set = gt_ids & ext_ids
    fp_set = ext_ids - gt_ids
    fn_set = gt_ids - ext_ids

    result.tp = len(tp_set)
    result.fp = len(fp_set)
    result.fn = len(fn_set)
    result.tp_items = sorted(tp_set)[:max_samples]
    result.fp_items = sorted(fp_set)[:max_samples]
    result.fn_items = sorted(fn_set)[:max_samples]

    # IWOL: loose = strict (no containment on ID sets) (DD-2026-019)           #changed
    result.loose_tp = result.tp                                                #changed
    result.loose_fp = result.fp                                                #changed
    result.loose_fn = result.fn                                                #changed


def _score_nioai(
    gt_flat: Dict,
    ext_flat: Dict,
    result: RecordResult,
    max_samples: int,
) -> None:
    """Score NIOAI (No Isolates, Only Assay Information) records.

    Compares assay fields directly without an isolate ID layer.

    Modifies result in place.
    """
    gt_nioai = gt_flat["nioai_flat"]
    ext_nioai = ext_flat["nioai_flat"]

    # Build keyed dicts for loose recovery (DD-2026-019)                       #changed
    gt_keyed = {}                                                              #changed
    for nf, (orig_value, norm_value) in gt_nioai.items():                      #changed
        gt_keyed[nf] = (nf, orig_value, norm_value)                            #changed
                                                                               #changed
    ext_keyed = {}                                                             #changed
    for nf, (orig_value, norm_value) in ext_nioai.items():                     #changed
        ext_keyed[nf] = (nf, orig_value, norm_value)                           #changed

    matched_gt_fields = set()
    tp_items = []
    fp_items = []

    for nf, (orig_value, norm_value) in ext_nioai.items():
        if nf in gt_nioai:
            gt_ov, gt_nv = gt_nioai[nf]
            if gt_nv == norm_value:
                tp_items.append(f"{nf}={str(orig_value)[:50]}")
                matched_gt_fields.add(nf)
                continue
        # No match -> FP
        fp_items.append(f"{nf}={str(orig_value)[:50]}")

    # FN: unmatched GT fields
    fn_items = []
    for nf, (orig_value, norm_value) in gt_nioai.items():
        if nf not in matched_gt_fields:
            fn_items.append(f"{nf}={str(orig_value)[:50]}")

    result.tp = len(tp_items)
    result.fp = len(fp_items)
    result.fn = len(fn_items)
    result.tp_items = tp_items[:max_samples]
    result.fp_items = fp_items[:max_samples]
    result.fn_items = fn_items[:max_samples]

    # --- Loose matching pass (DD-2026-019) ---                                #changed
    loose_recovered = _loose_recover(                                          #changed
        strict_fp_items=fp_items,                                              #changed
        strict_fn_items=fn_items,                                              #changed
        ext_items_by_key=ext_keyed,                                            #changed
        gt_items_by_key=gt_keyed,                                              #changed
    )                                                                          #changed
    result.loose_tp = result.tp + loose_recovered                              #changed
    result.loose_fp = result.fp - loose_recovered                              #changed
    result.loose_fn = result.fn - loose_recovered                              #changed


# ===========================================================================
# F1 computation
# ===========================================================================

def _compute_f1(result: RecordResult) -> None:
    """Compute precision, recall, and F1 from TP/FP/FN counts.

    Also computes loose F1 from loose_tp/fp/fn (DD-2026-019).

    Modifies result in place.
    """
    tp = result.tp
    fp = result.fp
    fn = result.fn

    result.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    result.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    p = result.precision
    r = result.recall
    result.primary_f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

    # Loose F1 (DD-2026-019)                                                  #changed
    ltp = result.loose_tp                                                      #changed
    lfp = result.loose_fp                                                      #changed
    lfn = result.loose_fn                                                      #changed
    lp = ltp / (ltp + lfp) if (ltp + lfp) > 0 else 0.0                       #changed
    lr = ltp / (ltp + lfn) if (ltp + lfn) > 0 else 0.0                       #changed
    result.loose_f1 = (2 * lp * lr) / (lp + lr) if (lp + lr) > 0 else 0.0    #changed


# ===========================================================================
# Per-field breakdown
# ===========================================================================

def _compute_field_scores(
    gt_flat: Dict, ext_flat: Dict, result: RecordResult
) -> None:
    """Compute per-field TP/FP/FN/F1 for detailed analysis.

    Only applies to IWL and NIOAI categories (IWOL has no field-level data).
    Modifies result in place.
    """
    gt_category = gt_flat["category"]

    if gt_category in ("IWL", "IWL+IWOL"):
        gt_fields = _collect_fields_from_iwl(gt_flat["iwl_flat"])
        ext_fields = _collect_fields_from_iwl(ext_flat["iwl_flat"])
    elif gt_category == "NIOAI":
        gt_fields = {nf for nf in gt_flat["nioai_flat"]}
        ext_fields = {nf for nf in ext_flat["nioai_flat"]}
    else:
        return

    all_fields = gt_fields | ext_fields
    field_scores = {}

    for fld in sorted(all_fields):
        # Count items for this field across all isolates
        fld_tp = 0
        fld_fp = 0
        fld_fn = 0

        if gt_category in ("IWL", "IWL+IWOL"):
            fld_tp, fld_fp, fld_fn = _field_counts_iwl(
                gt_flat["iwl_flat"], ext_flat["iwl_flat"], fld
            )
        elif gt_category == "NIOAI":
            fld_tp, fld_fp, fld_fn = _field_counts_nioai(
                gt_flat["nioai_flat"], ext_flat["nioai_flat"], fld
            )

        fld_p = fld_tp / (fld_tp + fld_fp) if (fld_tp + fld_fp) > 0 else 0.0
        fld_r = fld_tp / (fld_tp + fld_fn) if (fld_tp + fld_fn) > 0 else 0.0
        fld_f1 = (2 * fld_p * fld_r) / (fld_p + fld_r) if (fld_p + fld_r) > 0 else 0.0

        field_scores[fld] = {
            "tp": fld_tp, "fp": fld_fp, "fn": fld_fn, "f1": round(fld_f1, 4)
        }

    result.field_scores = field_scores


def _collect_fields_from_iwl(iwl_flat: Dict) -> set:
    """Collect all unique normalised field names from IWL data."""
    fields = set()
    for iso_id, iso_fields in iwl_flat.items():
        for nf in iso_fields:
            fields.add(nf)
    return fields


def _field_counts_iwl(
    gt_iwl: Dict, ext_iwl: Dict, target_field: str
) -> Tuple[int, int, int]:
    """Count TP/FP/FN for a specific field across all isolates in IWL."""
    # Collect GT values for this field
    gt_values = {}
    for iso_id, fields in gt_iwl.items():
        if target_field in fields:
            orig_value, norm_value = fields[target_field]
            gt_values[f"{iso_id}|{target_field}"] = norm_value

    # Collect extraction values for this field
    ext_values = {}
    for iso_id, fields in ext_iwl.items():
        if target_field in fields:
            orig_value, norm_value = fields[target_field]
            ext_values[f"{iso_id}|{target_field}"] = norm_value

    # Build value-based GT lookup for lenient matching
    gt_by_value = {}
    for key, nv in gt_values.items():
        if nv not in gt_by_value:
            gt_by_value[nv] = key

    matched_gt = set()
    tp = 0
    fp = 0

    for ext_key, ext_nv in ext_values.items():
        # Exact key match
        if ext_key in gt_values and gt_values[ext_key] == ext_nv:
            tp += 1
            matched_gt.add(ext_key)
            continue

        # Lenient value match
        if ext_nv in gt_by_value:
            gt_key = gt_by_value[ext_nv]
            if gt_key not in matched_gt:
                tp += 1
                matched_gt.add(gt_key)
                continue

        fp += 1

    fn = len(gt_values) - len(matched_gt)
    return tp, fp, fn


def _field_counts_nioai(
    gt_nioai: Dict, ext_nioai: Dict, target_field: str
) -> Tuple[int, int, int]:
    """Count TP/FP/FN for a specific field in NIOAI."""
    gt_has = target_field in gt_nioai
    ext_has = target_field in ext_nioai

    if gt_has and ext_has:
        gt_nv = gt_nioai[target_field][1]
        ext_nv = ext_nioai[target_field][1]
        if gt_nv == ext_nv:
            return 1, 0, 0
        else:
            return 0, 1, 1
    elif gt_has and not ext_has:
        return 0, 0, 1
    elif not gt_has and ext_has:
        return 0, 1, 0
    else:
        return 0, 0, 0


# ===========================================================================
# Utility
# ===========================================================================

def _count_items(flat: Dict) -> int:
    """Count total items in a flattened category structure."""
    count = 0
    for iso_id, fields in flat.get("iwl_flat", {}).items():
        count += len(fields)
    count += len(flat.get("iwol_ids", []))
    count += len(flat.get("nioai_flat", {}))
    return count
