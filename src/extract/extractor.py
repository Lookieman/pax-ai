"""
extractor.py
============
DSPy modules wrapping the v4 extraction signatures, plus robust JSON
parsing for LLM output.

Contains two extractors:
1. AssayExtractor - article text only (DD-2026-015)
2. SupplementaryAssayExtractor - article text + supplementary content (DD-2026-016)

Both produce the same 3-category output format and use the same
parse_extraction_output function for JSON parsing.

Changes from v3:
- parse_extraction_output validates 3-category structure
- Category inference fallback if LLM omits 'category' field
- Empty section type enforcement ({} for dicts, [] for lists)

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015, DD-2026-016
"""

import json
import re
import logging
from typing import Dict, Any

import dspy

from extract.signatures import (
    AssayExtractionSignature,
    SupplementaryAssayExtractionSignature,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"IWL", "IWOL", "NIOAI", "IWL+IWOL"}

EMPTY_RESULT = {
    "category": "NIOAI",
    "isolates_with_linking": {},
    "isolate_without_linking": [],
    "no_isolates_only_assayinformation": {},
}


# ---------------------------------------------------------------------------
# DSPy Module
# ---------------------------------------------------------------------------

class AssayExtractor(dspy.Module):
    """Chain-of-Thought extractor using the v4 AssayExtractionSignature."""

    def __init__(self):
        super().__init__()
        self.predictor = dspy.ChainOfThought(AssayExtractionSignature)

    def forward(self, article_text: str) -> dspy.Prediction:
        """Run extraction on article text.

        Args:
            article_text: Plain text extracted from XML article.

        Returns:
            dspy.Prediction with 'assay_info' field containing raw JSON string.
        """
        return self.predictor(article_text=article_text)


class SupplementaryAssayExtractor(dspy.Module):                                #changed: new class for multimodal extraction
    """Chain-of-Thought extractor for article + supplementary content.

    Takes both article text and supplementary content (text extracted
    from Attachments objects) as inputs.  Produces the same 3-category
    output as AssayExtractor.

    Design Decision: DD-2026-016
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.ChainOfThought(
            SupplementaryAssayExtractionSignature
        )

    def forward(
        self,
        article_text: str,
        supplementary_content: str,
    ) -> dspy.Prediction:
        """Run extraction on article text combined with supplementary content.

        Args:
            article_text: Plain text extracted from XML article.
            supplementary_content: Text representation of supplementary files
                (produced by str(Attachments(...))). May contain extracted
                table data, text from PDFs/DOCX, and descriptions of images.

        Returns:
            dspy.Prediction with 'assay_info' field containing raw JSON string.
        """
        return self.predictor(
            article_text=article_text,
            supplementary_content=supplementary_content,
        )


# ---------------------------------------------------------------------------
# JSON extraction (robust, from v3 with improvements)
# ---------------------------------------------------------------------------

def _extract_json_from_string(raw: str) -> Dict:
    """Extract a JSON object from a raw LLM output string.

    Tries in order:
    1. Direct json.loads
    2. Markdown fence stripping (```json ... ```)
    3. Balanced brace matching
    4. Trailing comma repair

    Args:
        raw: Raw string output from the LLM.

    Returns:
        Parsed dictionary, or empty dict on failure.
    """
    if not raw:
        return {}

    cleaned = raw.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 1b: direct parse with trailing comma repair                   #changed
    repaired_direct = re.sub(r",\s*([}\]])", r"\1", cleaned)               #changed
    try:                                                                     #changed
        return json.loads(repaired_direct)                                   #changed
    except (json.JSONDecodeError, ValueError):                               #changed
        pass                                                                 #changed

    # Attempt 2: strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        fenced = fence_match.group(1).strip()
        try:
            return json.loads(fenced)
        except (json.JSONDecodeError, ValueError):
            pass

        # Attempt 2b: fence content with trailing comma repair              #changed
        repaired_fenced = re.sub(r",\s*([}\]])", r"\1", fenced)            #changed
        try:                                                                 #changed
            return json.loads(repaired_fenced)                               #changed
        except (json.JSONDecodeError, ValueError):                           #changed
            pass                                                             #changed

    # Attempt 3: balanced brace matching
    start = cleaned.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        pass

                    # Attempt 4: trailing comma repair
                    repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
                    try:
                        return json.loads(repaired)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    tail_snippet = raw[-300:] if len(raw) > 300 else raw                      #changed
    logger.warning(                                                              #changed
        "Failed to extract JSON from LLM output (%d chars). Tail: ...%s",       #changed
        len(raw), tail_snippet                                                   #changed
    )                                                                            #changed
    return {}


# ---------------------------------------------------------------------------
# Output validation and normalisation
# ---------------------------------------------------------------------------

def _infer_category(parsed: Dict) -> str:
    """Infer the SFA category from which sections contain data.

    Args:
        parsed: Parsed extraction dictionary.

    Returns:
        Category string: IWL, IWOL, NIOAI, IWL+IWOL, or NIOAI (default).
    """
    has_iwl = False
    has_iwol = False
    has_nioai = False

    iwl = parsed.get("isolates_with_linking", {})
    if isinstance(iwl, dict) and iwl:
        has_iwl = True

    iwol = parsed.get("isolate_without_linking", [])
    if isinstance(iwol, list) and iwol:
        has_iwol = True

    nioai = parsed.get("no_isolates_only_assayinformation", {})
    if isinstance(nioai, dict) and any(nioai.values()):
        has_nioai = True

    if has_iwl and has_iwol:
        return "IWL+IWOL"
    if has_iwl:
        return "IWL"
    if has_iwol:
        return "IWOL"
    if has_nioai:
        return "NIOAI"
    return "NIOAI"


def _coerce_v3_flat_output(parsed: Dict) -> Dict:                             #changed: handle v3-style flat output gracefully
    """Convert v3-style flat {isolate_id: {assay: value}} to v4 structure.

    If the LLM produces a flat dict without 'category' and without the
    three section keys, assume it is v3-style IWL output and wrap it.

    Args:
        parsed: Flat dictionary from LLM.

    Returns:
        v4-structured dictionary.
    """
    section_keys = {
        "category",
        "isolates_with_linking",
        "isolate_without_linking",
        "no_isolates_only_assayinformation",
    }

    # If any v4 section key is present, it is not a v3 flat output
    if section_keys & set(parsed.keys()):
        return parsed

    # Check if it looks like {isolate_id: {field: value}} (v3 flat)
    is_flat = all(
        isinstance(v, dict) for v in parsed.values()
    )
    if not is_flat or not parsed:
        return parsed

    logger.info("Detected v3-style flat output; coercing to v4 structure")

    # Check for NO_ISOLATE_ID key -> NIOAI
    if list(parsed.keys()) == ["NO_ISOLATE_ID"]:
        return {
            "category": "NIOAI",
            "isolates_with_linking": {},
            "isolate_without_linking": [],
            "no_isolates_only_assayinformation": parsed["NO_ISOLATE_ID"],
        }

    # Otherwise assume IWL
    return {
        "category": "IWL",
        "isolates_with_linking": parsed,
        "isolate_without_linking": [],
        "no_isolates_only_assayinformation": {},
    }


def parse_extraction_output(raw: str) -> Dict[str, Any]:
    """Parse LLM output into a validated v4 3-category structure.

    Handles:
    - Standard v4 JSON output
    - v3-style flat output (backward compatibility)
    - Missing 'category' field (inferred from content)
    - Wrong types for empty sections (coerced)

    Args:
        raw: Raw string output from the LLM's assay_info field.

    Returns:
        Dictionary with keys: category, isolates_with_linking,
        isolate_without_linking, no_isolates_only_assayinformation.
    """
    parsed = _extract_json_from_string(raw)

    if not parsed:
        return dict(EMPTY_RESULT)

    # Handle v3 flat output format
    parsed = _coerce_v3_flat_output(parsed)

    # Validate or infer category
    category = parsed.get("category", "")
    if category not in VALID_CATEGORIES:
        category = _infer_category(parsed)
        logger.info("Category inferred as '%s' (LLM did not provide valid category)", category)

    # Enforce correct types for each section
    iwl = parsed.get("isolates_with_linking", {})
    if not isinstance(iwl, dict):
        logger.warning("isolates_with_linking is not a dict; coercing to {}")
        iwl = {}

    iwol = parsed.get("isolate_without_linking", [])
    if not isinstance(iwol, list):
        logger.warning("isolate_without_linking is not a list; coercing to []")
        iwol = []

    nioai = parsed.get("no_isolates_only_assayinformation", {})
    if not isinstance(nioai, dict):
        logger.warning("no_isolates_only_assayinformation is not a dict; coercing to {}")
        nioai = {}

    # Validate category matches populated section
    if category == "IWL" and not iwl:
        logger.warning("Category is IWL but isolates_with_linking is empty")
    if category == "IWOL" and not iwol:
        logger.warning("Category is IWOL but isolate_without_linking is empty")
    if category == "NIOAI" and not any(nioai.values()):
        if not iwl and not iwol:
            logger.warning("Category is NIOAI but no assay data found in any section")

    result = {
        "category": category,
        "isolates_with_linking": iwl,
        "isolate_without_linking": iwol,
        "no_isolates_only_assayinformation": nioai,
    }

    return result
