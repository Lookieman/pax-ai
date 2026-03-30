"""
feedback_metric.py
==================
Two-tier GEPA feedback metric for assay extraction optimisation.

Tier 1: GT comparison using the existing evaluation framework
         (per-field F1, category mismatch, missing/extra items).
Tier 2: XML cross-reference to diagnose *why* items were missed,
         not just *what* was missed.

Returns dspy.Prediction(score=F1, feedback=text) as required by
GEPA's GEPAFeedbackMetric protocol.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-018, Section 3
"""

import json
import re
import logging
from typing import Dict, List, Any

import dspy

from extract.extractor import parse_extraction_output
from evaluate.scorer import score_record

logger = logging.getLogger(__name__)


# ===========================================================================
# Constants
# ===========================================================================

# Recognised assay field names (from signatures.py)
_SCHEMA_FIELDS = {
    "serotype", "mlst", "cgmlst", "ast_data", "amr", "plasmid",
    "virulence_genes", "pfge", "spi", "toxin", "phage_type", "snp",
}

# Antigenic formula pattern: digits, colons, commas, dashes
# e.g. "4,5,12:i:-" or "1,4,[5],12:i:1,2"
_ANTIGENIC_FORMULA_RE = re.compile(
    r"^\d[\d,\[\]]*:\w[\w,\-]*:[\w,\-]*$"
)

# Population-level indicators
_POPULATION_INDICATORS_RE = re.compile(
    r"\d+\.?\d*\s*%|"            # percentages: "45.2%"
    r"\d+/\d+|"                   # fractions: "33/56"
    r"\b(?:proportion|prevalence|frequency)\b",
    re.IGNORECASE,
)


# ===========================================================================
# Main metric function (GEPA-compatible)
# ===========================================================================

def gepa_feedback_metric(
    gold,
    pred,
    trace=None,
    pred_name=None,
    pred_trace=None,
):
    """GEPA feedback metric for assay extraction.

    Implements the GEPAFeedbackMetric protocol:
        - Returns dspy.Prediction(score=float, feedback=str)

    Tier 1: Evaluate extraction against GT using the v4 scorer.
    Tier 2: Cross-reference article XML to diagnose extraction gaps.

    Args:
        gold: DSPy Example with pmcid, article_text, gt_json, gt_category.
        pred: DSPy Prediction with assay_info (raw JSON string).
        trace: Optional execution trace (unused in rule-based metric).
        pred_name: Optional predictor name (for per-predictor feedback).
        pred_trace: Optional predictor trace.

    Returns:
        dspy.Prediction with score (float 0-1) and feedback (str).
    """
    # --- Parse inputs ---
    pmcid = gold.pmcid
    gt_json_str = gold.gt_json
    gt_category = gold.gt_category
    article_text = gold.article_text

    gt_data = json.loads(gt_json_str)
    ext_data = parse_extraction_output(pred.assay_info)

    # --- Tier 1: GT comparison via scorer ---
    result = score_record(
        pmcid=pmcid,
        gt_data=gt_data,
        ext_data=ext_data,
    )

    f1_score = result.primary_f1
    feedback_parts = []

    # 1a. Category mismatch
    if not result.category_correct:
        feedback_parts.append(
            f"CATEGORY MISMATCH: Predicted '{result.ext_category}' "
            f"but ground truth is '{result.gt_category}'. "
            f"Check whether isolate codes are present and whether "
            f"assay data is linked to those codes."
        )

    # 1b. Per-field feedback from field_scores
    for field_name, scores in result.field_scores.items():
        field_tp = scores.get("tp", 0)
        field_fp = scores.get("fp", 0)
        field_fn = scores.get("fn", 0)
        field_f1 = scores.get("f1", 0.0)

        if field_f1 < 1.0:
            parts = []
            if field_fn > 0:
                parts.append(f"missed {field_fn} item(s)")
            if field_fp > 0:
                parts.append(f"{field_fp} extraneous item(s)")
            detail = "; ".join(parts)
            feedback_parts.append(
                f"FIELD '{field_name}' (F1={field_f1:.2f}): {detail}."
            )

    # 1c. False negative samples (from scorer)
    if result.fn_items:
        fn_sample = "; ".join(result.fn_items[:3])
        feedback_parts.append(
            f"MISSED ITEMS (sample): {fn_sample}"
        )

    # 1d. False positive samples (from scorer)
    if result.fp_items:
        fp_sample = "; ".join(result.fp_items[:3])
        feedback_parts.append(
            f"EXTRANEOUS ITEMS (sample): {fp_sample}"
        )

    # --- Tier 2: XML cross-reference ---
    tier2_feedback = _tier2_xml_crossref(
        gt_data=gt_data,
        ext_data=ext_data,
        article_text=article_text,
        gt_category=gt_category,
        result=result,
    )
    feedback_parts.extend(tier2_feedback)

    # --- Loose match feedback (DD-2026-019) ---                               #changed
    loose_recovered = result.loose_tp - result.tp                              #changed
    if loose_recovered > 0:                                                    #changed
        feedback_parts.append(                                                 #changed
            f"FORMAT NOTE: {loose_recovered} item(s) were extracted "          #changed
            f"correctly but in a more verbose format than the ground truth "   #changed
            f"expects. This is not a content error -- the right entity was "   #changed
            f"identified. Consider returning just the core value without "     #changed
            f"additional context (e.g. 'pSD1_197' instead of "                #changed
            f"'pSD1_197 (182,726 bp); contains...')."                         #changed
        )                                                                      #changed

    # --- Compose return ---
    if feedback_parts:
        feedback_text = "\n".join(feedback_parts)
    else:
        feedback_text = "Extraction correct."

    return dspy.Prediction(score=f1_score, feedback=feedback_text)


# ===========================================================================
# Tier 2: XML cross-reference detectors
# ===========================================================================

def _tier2_xml_crossref(
    gt_data: Dict,
    ext_data: Dict,
    article_text: str,
    gt_category: str,
    result: Any,
) -> List[str]:
    """Run Tier 2 XML cross-reference checks.

    Returns a list of feedback strings for any detected patterns.

    Args:
        gt_data: Ground truth dictionary.
        ext_data: Extraction dictionary.
        article_text: Plain text from the article XML.
        gt_category: GT category string.
        result: RecordResult from the scorer.

    Returns:
        List of feedback strings (may be empty).
    """
    feedback = []

    # 2a. Table extraction gap
    table_feedback = _check_table_extraction_gap(gt_data, ext_data, article_text)
    if table_feedback:
        feedback.append(table_feedback)

    # 2b. Linking failure
    linking_feedback = _check_linking_failure(ext_data, gt_category)
    if linking_feedback:
        feedback.append(linking_feedback)

    # 2c. Antigenic formula as serotype
    formula_feedback = _check_antigenic_formula(gt_data, ext_data)
    if formula_feedback:
        feedback.append(formula_feedback)

    # 2d. Population-level scope error
    population_feedback = _check_population_scope(ext_data, gt_category)
    if population_feedback:
        feedback.append(population_feedback)

    # 2e. Extraneous fields
    extraneous_feedback = _check_extraneous_fields(ext_data)
    if extraneous_feedback:
        feedback.append(extraneous_feedback)

    return feedback


# ---------------------------------------------------------------------------
# 2a. Table extraction gap
# ---------------------------------------------------------------------------

def _extract_table_text(article_text: str) -> str:
    """Extract a rough approximation of table content from article text.

    Since the article_text has already been tag-stripped, we look for
    patterns that suggest tabular data: lines with multiple tab/pipe
    separators, or sequences of short whitespace-separated values.

    This is a heuristic — the XML tags are already stripped.

    Args:
        article_text: Plain text from the article.

    Returns:
        Concatenated text that appears to be from tables.
    """
    # The article text is tag-stripped, so we cannot find <table> tags.
    # Instead, return the full text for substring matching.
    # This is sufficient because we only check whether specific isolate
    # IDs appear anywhere in the article text.
    return article_text


def _check_table_extraction_gap(
    gt_data: Dict,
    ext_data: Dict,
    article_text: str,
) -> str:
    """Check if GT isolate codes appear in article text but not in extraction.

    Args:
        gt_data: Ground truth dictionary.
        ext_data: Extraction dictionary.
        article_text: Full article text.

    Returns:
        Feedback string, or empty string if no gap detected.
    """
    # Collect GT isolate IDs
    gt_isolate_ids = set()
    iwl_raw = gt_data.get("isolates_with_linking", [])
    if isinstance(iwl_raw, list):
        for item in iwl_raw:
            if isinstance(item, dict):
                iso_id = str(item.get("isolate_id", "")).strip()
                if iso_id:
                    gt_isolate_ids.add(iso_id)
    elif isinstance(iwl_raw, dict):
        gt_isolate_ids.update(iwl_raw.keys())

    if not gt_isolate_ids:
        return ""

    # Collect extraction isolate IDs
    ext_isolate_ids = set()
    ext_iwl = ext_data.get("isolates_with_linking", {})
    if isinstance(ext_iwl, dict):
        ext_isolate_ids.update(ext_iwl.keys())

    # Find GT IDs missing from extraction
    missing_ids = gt_isolate_ids - ext_isolate_ids
    if not missing_ids:
        return ""

    # Check if missing IDs appear in article text
    ids_in_text = []
    for iso_id in sorted(missing_ids):
        if iso_id in article_text:
            ids_in_text.append(iso_id)

    if not ids_in_text:
        return ""

    sample = ids_in_text[:5]
    return (
        f"TABLE EXTRACTION GAP: {len(ids_in_text)} isolate code(s) "
        f"({', '.join(sample)}) appear in the article text but were "
        f"not extracted. Ensure all table rows are processed for "
        f"isolate identifiers."
    )


# ---------------------------------------------------------------------------
# 2b. Linking failure
# ---------------------------------------------------------------------------

def _check_linking_failure(ext_data: Dict, gt_category: str) -> str:
    """Check if extraction has unlinked data that should be linked.

    Detects: extraction puts isolates in IWOL and assay data in NIOAI,
    but GT expects IWL (meaning both should be linked).

    Args:
        ext_data: Extraction dictionary.
        gt_category: GT category string.

    Returns:
        Feedback string, or empty string if no issue.
    """
    if gt_category not in ("IWL", "IWL+IWOL"):
        return ""

    ext_iwol = ext_data.get("isolate_without_linking", [])
    ext_nioai = ext_data.get("no_isolates_only_assayinformation", {})
    ext_iwl = ext_data.get("isolates_with_linking", {})

    has_unlinked_isolates = isinstance(ext_iwol, list) and len(ext_iwol) > 0
    has_unlinked_assay = isinstance(ext_nioai, dict) and any(ext_nioai.values())
    has_linked = isinstance(ext_iwl, dict) and len(ext_iwl) > 0

    if has_unlinked_isolates and has_unlinked_assay and not has_linked:
        return (
            "LINKING FAILURE: The model extracted both isolate codes "
            "(in isolate_without_linking) and assay data "
            "(in no_isolates_only_assayinformation) but did not link them. "
            "When isolate codes and assay data appear in the same article, "
            "check whether they can be linked per-isolate and placed in "
            "isolates_with_linking."
        )

    if has_unlinked_isolates and not has_linked:
        return (
            "PARTIAL LINKING FAILURE: Isolate codes were placed in "
            "isolate_without_linking but the ground truth expects "
            "isolates_with_linking. Check whether assay data in the "
            "article can be linked to these isolate codes."
        )

    return ""


# ---------------------------------------------------------------------------
# 2c. Antigenic formula as serotype
# ---------------------------------------------------------------------------

def _check_antigenic_formula(gt_data: Dict, ext_data: Dict) -> str:
    """Check if GT serotypes use antigenic formula notation that was missed.

    Antigenic formulae (e.g. '4,5,12:i:-') ARE serotype values but
    models sometimes fail to recognise them as such.

    Args:
        gt_data: Ground truth dictionary.
        ext_data: Extraction dictionary.

    Returns:
        Feedback string, or empty string if no issue.
    """
    # Collect GT serotype values
    gt_serotypes = _collect_field_values(gt_data, "serotype")
    ext_serotypes = _collect_field_values(ext_data, "serotype")

    # Find GT serotypes missing from extraction
    missing = gt_serotypes - ext_serotypes
    if not missing:
        return ""

    # Check if any missing serotypes match antigenic formula pattern
    formula_values = []
    for sero in missing:
        if _ANTIGENIC_FORMULA_RE.match(sero):
            formula_values.append(sero)

    if not formula_values:
        return ""

    sample = formula_values[:3]
    return (
        f"ANTIGENIC FORMULA: Value(s) {sample} use antigenic formula "
        f"notation which IS a serotype/serovar value. Antigenic formulae "
        f"(e.g. '4,5,12:i:-') should be extracted as serotype values."
    )


# ---------------------------------------------------------------------------
# 2d. Population-level scope error
# ---------------------------------------------------------------------------

def _check_population_scope(ext_data: Dict, gt_category: str) -> str:
    """Check if extraction contains population-level data for IWL articles.

    Population-level data (percentages, proportions) should not appear
    in per-isolate fields for IWL-classified articles.

    Args:
        ext_data: Extraction dictionary.
        gt_category: GT category string.

    Returns:
        Feedback string, or empty string if no issue.
    """
    if gt_category not in ("IWL", "IWL+IWOL"):
        return ""

    ext_iwl = ext_data.get("isolates_with_linking", {})
    if not isinstance(ext_iwl, dict):
        return ""

    population_values = []
    for iso_id, assays in ext_iwl.items():
        if not isinstance(assays, dict):
            continue
        for field_name, value in assays.items():
            value_str = str(value)
            if _POPULATION_INDICATORS_RE.search(value_str):
                population_values.append(f"{iso_id}.{field_name}={value_str[:30]}")

    if not population_values:
        return ""

    sample = population_values[:3]
    return (
        f"POPULATION SCOPE: Extracted values contain population-level "
        f"data (percentages or proportions): {sample}. "
        f"For IWL articles, only extract per-isolate data that is "
        f"explicitly linked to a specific isolate code."
    )


# ---------------------------------------------------------------------------
# 2e. Extraneous fields
# ---------------------------------------------------------------------------

def _check_extraneous_fields(ext_data: Dict) -> str:
    """Check if extraction contains fields outside the target schema.

    Args:
        ext_data: Extraction dictionary.

    Returns:
        Feedback string, or empty string if no issue.
    """
    # Skip structural keys
    structural_keys = {
        "category", "isolates_with_linking",
        "isolate_without_linking", "no_isolates_only_assayinformation",
    }

    extraneous = set()

    # Check IWL fields
    ext_iwl = ext_data.get("isolates_with_linking", {})
    if isinstance(ext_iwl, dict):
        for iso_id, assays in ext_iwl.items():
            if isinstance(assays, dict):
                for field_name in assays:
                    normalised = field_name.lower().strip()
                    if normalised not in _SCHEMA_FIELDS:
                        extraneous.add(field_name)

    # Check NIOAI fields
    ext_nioai = ext_data.get("no_isolates_only_assayinformation", {})
    if isinstance(ext_nioai, dict):
        for field_name in ext_nioai:
            normalised = field_name.lower().strip()
            if normalised not in _SCHEMA_FIELDS:
                extraneous.add(field_name)

    if not extraneous:
        return ""

    return (
        f"EXTRANEOUS FIELDS: Extracted field(s) {sorted(extraneous)} "
        f"are not part of the target schema. Only extract: "
        f"{', '.join(sorted(_SCHEMA_FIELDS))}."
    )


# ===========================================================================
# Utility
# ===========================================================================

def _collect_field_values(data: Dict, target_field: str) -> set:
    """Collect all values for a specific field across IWL and NIOAI sections.

    Args:
        data: GT or extraction dictionary.
        target_field: Field name to collect (e.g. 'serotype').

    Returns:
        Set of string values found.
    """
    values = set()

    # From IWL
    iwl = data.get("isolates_with_linking", {})
    if isinstance(iwl, list):
        for item in iwl:
            if isinstance(item, dict):
                val = item.get(target_field)
                if val:
                    values.add(str(val).strip())
    elif isinstance(iwl, dict):
        for iso_id, assays in iwl.items():
            if isinstance(assays, dict):
                val = assays.get(target_field)
                if val:
                    values.add(str(val).strip())

    # From NIOAI
    nioai = data.get("no_isolates_only_assayinformation", {})
    if isinstance(nioai, dict):
        val = nioai.get(target_field)
        if val:
            values.add(str(val).strip())

    return values
