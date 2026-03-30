"""
metric.py
=========
GEPA-compatible metric wrapper for assay extraction evaluation.

This module provides a single function with the signature that GEPA
expects: metric(example, prediction, trace=None) -> float.

Internally, it parses the LLM output and delegates to scorer.score_record.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015
"""

import logging
from typing import Optional

from extract.extractor import parse_extraction_output
from evaluate.scorer import score_record

logger = logging.getLogger(__name__)


def assay_metric(example, prediction, trace=None) -> float:
    """GEPA-compatible metric function for assay extraction.

    Args:
        example: dspy.Example with fields:
            - pmcid (str): PubMed Central ID
            - gt_data (dict): Ground truth in v4 3-category format
        prediction: dspy.Prediction with field:
            - assay_info (str): Raw JSON string from LLM
        trace: Optional trace object (unused; required by GEPA interface).

    Returns:
        Primary F1 score as a float between 0.0 and 1.0.
    """
    pmcid = getattr(example, "pmcid", "unknown")
    gt_data = example.gt_data

    # Parse the LLM's raw output into structured format
    raw_output = prediction.assay_info
    ext_data = parse_extraction_output(raw_output)

    # Score using the v4 evaluation framework
    result = score_record(pmcid=pmcid, gt_data=gt_data, ext_data=ext_data)

    return result.primary_f1
