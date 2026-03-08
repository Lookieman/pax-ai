"""
Isolate Granularity Diagnostic Analysis
========================================
AI6129 Pathogen Tracking Project

Purpose: Analyse isolate identifier conventions in ground truth vs LLM extraction
         to determine if PMC6035434 pattern (serovar vs strain code mismatch) is
         systematic or an outlier.

Author: Luqman
Date: January 2026
Version: 1.0

Usage:
    This script is designed to be run in Google Colab with DSPy configured.
    Copy cells into a Jupyter notebook or run as a Python script.
"""

# =============================================================================
# SECTION 1: IMPORTS AND CONFIGURATION
# =============================================================================

import dspy
import json
import csv
import os
import glob
from typing import Optional, Literal
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


# =============================================================================
# SECTION 2: DATA CLASSES FOR STRUCTURED OUTPUT
# =============================================================================

class IdentifierType(str, Enum):
    """Classification of isolate identifier granularity."""
    SEROVAR = "SEROVAR"           # Species/serovar level (e.g., 'S. Typhimurium')
    STRAIN_CODE = "STRAIN_CODE"   # Laboratory strain (e.g., 'STM-1', 'SE-2024-001')
    SAMPLE_ID = "SAMPLE_ID"       # Sample/clinical isolate (e.g., 'Patient_001')
    ACCESSION = "ACCESSION"       # GenBank accession used as identifier
    AMBIGUOUS = "AMBIGUOUS"       # Cannot clearly determine type


class SourceSection(str, Enum):
    """Section of the article where identifier was found."""
    TITLE = "TITLE"
    ABSTRACT = "ABSTRACT"
    METHODS = "METHODS"
    RESULTS = "RESULTS"
    TABLES = "TABLES"
    SUPPLEMENTARY = "SUPPLEMENTARY"
    OTHER = "OTHER"


@dataclass
class ASTResult:
    """Antimicrobial susceptibility test result."""
    antibiotic: str
    result: str  # S, I, R, or UNKNOWN
    mic_value: Optional[str] = None


@dataclass
class AssayData:
    """Assay information for an isolate."""
    serotype: Optional[str] = None
    mlst: Optional[str] = None
    cgmlst: Optional[str] = None
    ast_results: Optional[list] = None  # List of ASTResult dicts
    amr_genes: Optional[list] = None
    plasmids: Optional[list] = None
    virulence_factors: Optional[list] = None
    spi_markers: Optional[list] = None


@dataclass
class IsolateEntry:
    """A single isolate entry extracted from an article."""
    identifier_as_written: str
    identifier_type: str
    normalised_identifier: str
    identifier_reasoning: str
    source_context: str
    source_section: str
    has_strain_level_detail: bool
    associated_strain_codes: list
    assay_data: dict


@dataclass 
class DiagnosticResult:
    """Complete diagnostic extraction result for an article."""
    pmcid: str
    extraction_timestamp: str
    isolate_entries: list  # List of IsolateEntry dicts
    article_has_serovar_mentions: bool
    article_has_strain_codes: bool
    serovar_to_strain_mapping: dict
    extraction_notes: str


# =============================================================================
# SECTION 3: DSPY SIGNATURES
# =============================================================================

class DiagnosticIsolateExtractionSignature(dspy.Signature):
    """
    Extract isolate identifiers from a biomedical article with detailed 
    classification of identifier type and granularity.
    
    PURPOSE: Diagnostic analysis to understand isolate naming conventions
    in articles and identify serovar vs strain code patterns.
    
    IDENTIFIER TYPE CLASSIFICATION:
    - SEROVAR: Species or serovar level identifiers
      Examples: "S. Typhimurium", "Enteritidis", "Salmonella enterica serovar Newport"
      
    - STRAIN_CODE: Laboratory strain designations or isolate codes
      Examples: "STM-1", "SE-2024-001", "ATCC 14028", "LT2"
      
    - SAMPLE_ID: Sample or clinical isolate identifiers
      Examples: "Patient_001", "Food_Sample_A", "Clinical isolate C1"
      
    - ACCESSION: GenBank/database accession numbers used as the primary identifier
      Examples: "CP001234", "SAMN12345678"
      
    - AMBIGUOUS: Cannot clearly determine the identifier type
    
    IMPORTANT ANALYSIS STEPS:
    1. Identify ALL entities that could serve as isolate identifiers
    2. Determine the granularity level of each identifier
    3. Check if serovar-level identifiers have associated strain codes
    4. Record the exact text context where each identifier appears
    5. Map relationships between serovars and their strain codes
    
    OUTPUT FORMAT:
    Return a JSON object with the structure shown in the output field description.
    """
    
    article_text: str = dspy.InputField(
        desc="Full text of the PMC XML article"
    )
    
    pmcid: str = dspy.InputField(
        desc="The PMC identifier for this article (e.g., PMC6035434)"
    )
    
    diagnostic_output: str = dspy.OutputField(
        desc="""JSON object with the following structure:
        {
            "isolate_entries": [
                {
                    "identifier_as_written": "exact text from article",
                    "identifier_type": "SEROVAR|STRAIN_CODE|SAMPLE_ID|ACCESSION|AMBIGUOUS",
                    "normalised_identifier": "standardised form for matching",
                    "identifier_reasoning": "brief explanation of type classification",
                    "source_context": "the sentence where identifier was found (max 200 chars)",
                    "source_section": "TITLE|ABSTRACT|METHODS|RESULTS|TABLES|SUPPLEMENTARY|OTHER",
                    "has_strain_level_detail": true/false,
                    "associated_strain_codes": ["strain1", "strain2"] or [],
                    "assay_data": {
                        "serotype": "value or null",
                        "mlst": "value or null",
                        "amr_genes": ["gene1", "gene2"] or null,
                        "ast_results": [{"antibiotic": "AMP", "result": "R", "mic_value": ">32"}] or null,
                        "plasmids": ["IncF", "IncI1"] or null,
                        "virulence_factors": ["invA", "sopB"] or null,
                        "spi_markers": ["SPI-1", "SPI-2"] or null
                    }
                }
            ],
            "article_has_serovar_mentions": true/false,
            "article_has_strain_codes": true/false,
            "serovar_to_strain_mapping": {
                "Typhimurium": ["STM-1", "STM-2"],
                "Enteritidis": ["SE-1"]
            },
            "extraction_notes": "Any observations about identifier conventions in this article"
        }
        """
    )


# =============================================================================
# SECTION 4: DIAGNOSTIC EXTRACTOR MODULE
# =============================================================================

class DiagnosticIsolateExtractor(dspy.Module):
    """
    DSPy module for diagnostic isolate extraction with Chain-of-Thought reasoning.
    """
    
    def __init__(self):
        super().__init__()
        self.extractor = dspy.ChainOfThought(DiagnosticIsolateExtractionSignature)
    
    def forward(self, article_text: str, pmcid: str) -> dspy.Prediction:
        """
        Extract isolate identifiers with diagnostic information.
        
        Args:
            article_text: Full text of the article
            pmcid: PMC identifier
            
        Returns:
            DSPy Prediction with diagnostic_output field
        """
        result = self.extractor(article_text=article_text, pmcid=pmcid)
        return result


# =============================================================================
# SECTION 5: RESULT PARSING AND VALIDATION
# =============================================================================

def parse_diagnostic_output(raw_output: str, pmcid: str) -> Optional[DiagnosticResult]:
    """
    Parse the raw JSON output from the LLM into a structured DiagnosticResult.
    
    Args:
        raw_output: Raw JSON string from LLM
        pmcid: PMC identifier for error reporting
        
    Returns:
        DiagnosticResult object or None if parsing fails
    """
    # Attempt to extract JSON from the output
    json_str = raw_output.strip()
    
    # Handle case where LLM wraps JSON in markdown code blocks
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    json_str = json_str.strip()
    
    # Try to find JSON object using balanced brace matching
    start_idx = json_str.find("{")
    if start_idx == -1:
        print(f"[ERROR] No JSON object found in output for {pmcid}")
        return None
    
    # Find matching closing brace
    brace_count = 0
    end_idx = start_idx
    
    for i, char in enumerate(json_str[start_idx:], start=start_idx):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break
    
    json_str = json_str[start_idx:end_idx + 1]
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed for {pmcid}: {e}")
        return None
    
    # Construct DiagnosticResult
    try:
        result = DiagnosticResult(
            pmcid=pmcid,
            extraction_timestamp=datetime.now().isoformat(),
            isolate_entries=data.get("isolate_entries", []),
            article_has_serovar_mentions=data.get("article_has_serovar_mentions", False),
            article_has_strain_codes=data.get("article_has_strain_codes", False),
            serovar_to_strain_mapping=data.get("serovar_to_strain_mapping", {}),
            extraction_notes=data.get("extraction_notes", "")
        )
        return result
    except Exception as e:
        print(f"[ERROR] Failed to construct DiagnosticResult for {pmcid}: {e}")
        return None


# =============================================================================
# SECTION 6: COMPARISON AND ANALYSIS FUNCTIONS
# =============================================================================

def normalise_identifier(identifier: str) -> str:
    """
    Normalise an identifier for comparison purposes.
    
    Rules:
    - Convert to lowercase
    - Remove common prefixes (S., Salmonella, serovar)
    - Strip whitespace
    - Remove punctuation variations
    """
    normalised = identifier.lower().strip()
    
    # Remove common prefixes
    prefixes_to_remove = [
        "salmonella enterica serovar ",
        "salmonella enterica subsp. enterica serovar ",
        "s. enterica serovar ",
        "s. enterica ",
        "salmonella ",
        "s. ",
        "serovar "
    ]
    
    for prefix in prefixes_to_remove:
        if normalised.startswith(prefix):
            normalised = normalised[len(prefix):]
            break
    
    # Remove common suffixes
    suffixes_to_remove = [" strain", " isolate"]
    for suffix in suffixes_to_remove:
        if normalised.endswith(suffix):
            normalised = normalised[:-len(suffix)]
    
    return normalised.strip()


def compare_identifiers(gt_identifier: str, ext_identifier: str) -> dict:
    """
    Compare ground truth and extracted identifiers with multiple matching strategies.
    
    Returns:
        dict with match results under different strategies
    """
    gt_norm = normalise_identifier(gt_identifier)
    ext_norm = normalise_identifier(ext_identifier)
    
    return {
        "exact_match": gt_identifier == ext_identifier,
        "case_insensitive_match": gt_identifier.lower() == ext_identifier.lower(),
        "normalised_match": gt_norm == ext_norm,
        "gt_contains_ext": ext_norm in gt_norm,
        "ext_contains_gt": gt_norm in ext_norm,
        "gt_normalised": gt_norm,
        "ext_normalised": ext_norm
    }


def classify_mismatch(gt_identifier: str, ext_identifier: str, 
                      ext_identifier_type: str, 
                      article_has_both: bool) -> str:
    """
    Classify the reason for a mismatch between GT and extracted identifiers.
    
    Returns:
        Mismatch category string
    """
    gt_norm = normalise_identifier(gt_identifier)
    ext_norm = normalise_identifier(ext_identifier)
    
    # Check for granularity mismatch (serovar vs strain)
    if article_has_both:
        gt_looks_like_serovar = len(gt_norm.split()) <= 2 and not any(
            char.isdigit() for char in gt_norm
        )
        ext_looks_like_strain = any(char.isdigit() for char in ext_norm) or "-" in ext_norm
        
        if gt_looks_like_serovar and ext_looks_like_strain:
            return "GT_SEROVAR_EXT_STRAIN"
        
        ext_looks_like_serovar = len(ext_norm.split()) <= 2 and not any(
            char.isdigit() for char in ext_norm
        )
        gt_looks_like_strain = any(char.isdigit() for char in gt_norm) or "-" in gt_norm
        
        if gt_looks_like_strain and ext_looks_like_serovar:
            return "GT_STRAIN_EXT_SEROVAR"
    
    # Check for format differences
    if gt_norm == ext_norm:
        return "FORMAT_DIFFERENCE"
    
    # Check for partial match (one contains the other)
    if gt_norm in ext_norm or ext_norm in gt_norm:
        return "PARTIAL_MATCH"
    
    # Check for extraction error
    return "EXTRACTION_ERROR"


# =============================================================================
# SECTION 7: CSV GENERATION FUNCTIONS
# =============================================================================

def generate_discrepancy_csv(
    diagnostic_results: list,
    ground_truth: dict,
    output_path: str
) -> None:
    """
    Generate the detailed discrepancy analysis CSV.
    
    Args:
        diagnostic_results: List of DiagnosticResult objects
        ground_truth: Dictionary mapping PMCID to GT data
        output_path: Path to write CSV file
    """
    fieldnames = [
        # Document identification
        "pmcid", "stratum", "split",
        # Ground truth isolate info
        "gt_isolate_id", "gt_isolate_count",
        # Extracted isolate info
        "ext_isolate_id", "ext_identifier_type", "ext_normalised_id",
        "ext_has_strain_detail", "ext_associated_strains",
        "ext_source_section", "ext_source_context", "ext_reasoning",
        # Matching analysis
        "isolate_exact_match", "isolate_normalised_match", "isolate_lenient_match",
        "match_failure_reason",
        # Assay comparison
        "gt_serotype", "ext_serotype", "serotype_match",
        "gt_mlst", "ext_mlst", "mlst_match",
        "gt_amr_genes", "ext_amr_genes", "amr_genes_match",
        # Scores
        "isolate_precision", "isolate_recall", "isolate_f1",
        # Review flags
        "requires_review", "review_priority", "review_notes"
    ]
    
    rows = []
    
    for diag_result in diagnostic_results:
        pmcid = diag_result.pmcid
        gt_data = ground_truth.get(pmcid, {})
        gt_isolates = gt_data.get("isolates", [])
        
        # Get metadata
        stratum = gt_data.get("stratum", "unknown")
        split = gt_data.get("split", "unknown")
        
        # Process each extracted isolate
        for ext_entry in diag_result.isolate_entries:
            ext_id = ext_entry.get("identifier_as_written", "")
            ext_norm = ext_entry.get("normalised_identifier", "")
            ext_type = ext_entry.get("identifier_type", "UNKNOWN")
            
            # Find best matching GT isolate
            best_gt_match = None
            best_match_score = 0
            
            for gt_isolate in gt_isolates:
                gt_id = gt_isolate.get("isolate_id", "")
                comparison = compare_identifiers(gt_id, ext_id)
                
                # Score the match
                score = 0
                if comparison["exact_match"]:
                    score = 3
                elif comparison["normalised_match"]:
                    score = 2
                elif comparison["gt_contains_ext"] or comparison["ext_contains_gt"]:
                    score = 1
                
                if score > best_match_score:
                    best_match_score = score
                    best_gt_match = gt_isolate
            
            # Determine match status
            article_has_both = (diag_result.article_has_serovar_mentions and 
                               diag_result.article_has_strain_codes)
            
            if best_gt_match:
                gt_id = best_gt_match.get("isolate_id", "")
                comparison = compare_identifiers(gt_id, ext_id)
                
                match_failure_reason = ""
                if not comparison["exact_match"]:
                    match_failure_reason = classify_mismatch(
                        gt_id, ext_id, ext_type, article_has_both
                    )
            else:
                gt_id = ""
                comparison = {
                    "exact_match": False,
                    "normalised_match": False,
                    "gt_contains_ext": False,
                    "ext_contains_gt": False
                }
                match_failure_reason = "GT_MISSING"
            
            # Build row
            row = {
                "pmcid": pmcid,
                "stratum": stratum,
                "split": split,
                "gt_isolate_id": gt_id,
                "gt_isolate_count": len(gt_isolates),
                "ext_isolate_id": ext_id,
                "ext_identifier_type": ext_type,
                "ext_normalised_id": ext_norm,
                "ext_has_strain_detail": ext_entry.get("has_strain_level_detail", False),
                "ext_associated_strains": ";".join(ext_entry.get("associated_strain_codes", [])),
                "ext_source_section": ext_entry.get("source_section", ""),
                "ext_source_context": ext_entry.get("source_context", "")[:200],
                "ext_reasoning": ext_entry.get("identifier_reasoning", ""),
                "isolate_exact_match": comparison["exact_match"],
                "isolate_normalised_match": comparison.get("normalised_match", False),
                "isolate_lenient_match": comparison.get("gt_contains_ext", False) or 
                                         comparison.get("ext_contains_gt", False),
                "match_failure_reason": match_failure_reason,
                "gt_serotype": best_gt_match.get("Serotype", "") if best_gt_match else "",
                "ext_serotype": ext_entry.get("assay_data", {}).get("serotype", ""),
                "serotype_match": False,  # To be computed
                "gt_mlst": best_gt_match.get("MLST", "") if best_gt_match else "",
                "ext_mlst": ext_entry.get("assay_data", {}).get("mlst", ""),
                "mlst_match": False,  # To be computed
                "gt_amr_genes": ";".join(best_gt_match.get("AMR", [])) if best_gt_match else "",
                "ext_amr_genes": ";".join(ext_entry.get("assay_data", {}).get("amr_genes", []) or []),
                "amr_genes_match": False,  # To be computed
                "isolate_precision": 0.0,
                "isolate_recall": 0.0,
                "isolate_f1": 0.0,
                "requires_review": not comparison["exact_match"],
                "review_priority": "HIGH" if match_failure_reason in 
                                   ["GT_SEROVAR_EXT_STRAIN", "GT_STRAIN_EXT_SEROVAR"] else "MEDIUM",
                "review_notes": ""
            }
            
            rows.append(row)
    
    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[INFO] Wrote {len(rows)} rows to {output_path}")


def generate_document_summary_csv(
    diagnostic_results: list,
    ground_truth: dict,
    output_path: str
) -> None:
    """
    Generate the document-level summary CSV.
    """
    fieldnames = [
        "pmcid", "stratum", "split",
        "gt_isolate_count", "ext_isolate_count",
        "matched_isolate_count", "normalised_match_count", "lenient_match_count",
        "doc_isolate_precision", "doc_isolate_recall",
        "doc_isolate_f1_strict", "doc_isolate_f1_lenient",
        "has_serovar_only_gt", "has_strain_code_gt", "has_mixed_granularity_gt",
        "has_serovar_only_ext", "has_strain_code_ext", "has_mixed_granularity_ext",
        "granularity_mismatch", "pmc6035434_pattern",
        "requires_review", "review_category"
    ]
    
    rows = []
    
    for diag_result in diagnostic_results:
        pmcid = diag_result.pmcid
        gt_data = ground_truth.get(pmcid, {})
        gt_isolates = gt_data.get("isolates", [])
        
        # Count extraction types
        ext_types = [e.get("identifier_type", "") for e in diag_result.isolate_entries]
        ext_serovar_count = ext_types.count("SEROVAR")
        ext_strain_count = ext_types.count("STRAIN_CODE")
        
        # Determine GT convention (heuristic)
        gt_has_strain = False
        gt_has_serovar = False
        for iso in gt_isolates:
            iso_id = iso.get("isolate_id", "")
            if any(char.isdigit() for char in iso_id) or "-" in iso_id:
                gt_has_strain = True
            else:
                gt_has_serovar = True
        
        # Check for PMC6035434 pattern
        # Pattern: Article has strain codes, GT uses serovar, extraction uses strain codes
        pmc6035434_pattern = (
            diag_result.article_has_strain_codes and
            gt_has_serovar and not gt_has_strain and
            ext_strain_count > 0
        )
        
        # Calculate match counts
        matched_count = 0
        normalised_count = 0
        lenient_count = 0
        
        for ext_entry in diag_result.isolate_entries:
            ext_id = ext_entry.get("identifier_as_written", "")
            for gt_iso in gt_isolates:
                gt_id = gt_iso.get("isolate_id", "")
                comp = compare_identifiers(gt_id, ext_id)
                if comp["exact_match"]:
                    matched_count += 1
                    break
                elif comp["normalised_match"]:
                    normalised_count += 1
                    break
                elif comp["gt_contains_ext"] or comp["ext_contains_gt"]:
                    lenient_count += 1
                    break
        
        # Calculate metrics
        gt_count = len(gt_isolates)
        ext_count = len(diag_result.isolate_entries)
        
        precision_strict = matched_count / ext_count if ext_count > 0 else 0
        recall_strict = matched_count / gt_count if gt_count > 0 else 0
        f1_strict = (2 * precision_strict * recall_strict / 
                    (precision_strict + recall_strict)) if (precision_strict + recall_strict) > 0 else 0
        
        total_lenient = matched_count + normalised_count + lenient_count
        precision_lenient = total_lenient / ext_count if ext_count > 0 else 0
        recall_lenient = total_lenient / gt_count if gt_count > 0 else 0
        f1_lenient = (2 * precision_lenient * recall_lenient / 
                     (precision_lenient + recall_lenient)) if (precision_lenient + recall_lenient) > 0 else 0
        
        # Determine review category
        review_category = "OK"
        if pmc6035434_pattern:
            review_category = "GRANULARITY"
        elif matched_count < ext_count:
            review_category = "EXTRACTION_ERROR"
        elif gt_count > ext_count:
            review_category = "GT_GAP"
        
        row = {
            "pmcid": pmcid,
            "stratum": gt_data.get("stratum", "unknown"),
            "split": gt_data.get("split", "unknown"),
            "gt_isolate_count": gt_count,
            "ext_isolate_count": ext_count,
            "matched_isolate_count": matched_count,
            "normalised_match_count": normalised_count,
            "lenient_match_count": lenient_count,
            "doc_isolate_precision": round(precision_strict, 4),
            "doc_isolate_recall": round(recall_strict, 4),
            "doc_isolate_f1_strict": round(f1_strict, 4),
            "doc_isolate_f1_lenient": round(f1_lenient, 4),
            "has_serovar_only_gt": gt_has_serovar and not gt_has_strain,
            "has_strain_code_gt": gt_has_strain and not gt_has_serovar,
            "has_mixed_granularity_gt": gt_has_serovar and gt_has_strain,
            "has_serovar_only_ext": ext_serovar_count > 0 and ext_strain_count == 0,
            "has_strain_code_ext": ext_strain_count > 0 and ext_serovar_count == 0,
            "has_mixed_granularity_ext": ext_serovar_count > 0 and ext_strain_count > 0,
            "granularity_mismatch": (gt_has_serovar != (ext_serovar_count > 0)) or 
                                    (gt_has_strain != (ext_strain_count > 0)),
            "pmc6035434_pattern": pmc6035434_pattern,
            "requires_review": pmc6035434_pattern or f1_strict < 0.5,
            "review_category": review_category
        }
        
        rows.append(row)
    
    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[INFO] Wrote {len(rows)} document summaries to {output_path}")


def generate_granularity_analysis_csv(
    diagnostic_results: list,
    ground_truth: dict,
    output_path: str
) -> None:
    """
    Generate the focused granularity analysis CSV.
    """
    fieldnames = [
        "pmcid", "split",
        "article_has_serovar_mentions", "article_has_strain_codes",
        "article_strain_codes_list", "article_serovars_list",
        "serovar_to_strain_mapping",
        "gt_convention", "gt_identifiers_list",
        "ext_convention", "ext_identifiers_list",
        "convention_match", "mismatch_type", "is_pmc6035434_pattern"
    ]
    
    rows = []
    
    for diag_result in diagnostic_results:
        pmcid = diag_result.pmcid
        gt_data = ground_truth.get(pmcid, {})
        gt_isolates = gt_data.get("isolates", [])
        
        # Extract lists
        ext_serovars = []
        ext_strains = []
        for entry in diag_result.isolate_entries:
            id_type = entry.get("identifier_type", "")
            id_val = entry.get("identifier_as_written", "")
            if id_type == "SEROVAR":
                ext_serovars.append(id_val)
            elif id_type == "STRAIN_CODE":
                ext_strains.append(id_val)
        
        # Determine conventions
        gt_ids = [iso.get("isolate_id", "") for iso in gt_isolates]
        gt_has_strain = any(any(c.isdigit() for c in id) or "-" in id for id in gt_ids)
        gt_has_serovar = any(not any(c.isdigit() for c in id) and "-" not in id for id in gt_ids)
        
        if gt_has_serovar and gt_has_strain:
            gt_convention = "MIXED"
        elif gt_has_strain:
            gt_convention = "STRAIN_ONLY"
        elif gt_has_serovar:
            gt_convention = "SEROVAR_ONLY"
        else:
            gt_convention = "UNKNOWN"
        
        if ext_serovars and ext_strains:
            ext_convention = "MIXED"
        elif ext_strains:
            ext_convention = "STRAIN_ONLY"
        elif ext_serovars:
            ext_convention = "SEROVAR_ONLY"
        else:
            ext_convention = "UNKNOWN"
        
        # Determine mismatch type
        convention_match = gt_convention == ext_convention
        mismatch_type = "N/A"
        if not convention_match:
            if gt_convention == "SEROVAR_ONLY" and ext_convention == "STRAIN_ONLY":
                mismatch_type = "GT_SEROVAR_EXT_STRAIN"
            elif gt_convention == "STRAIN_ONLY" and ext_convention == "SEROVAR_ONLY":
                mismatch_type = "GT_STRAIN_EXT_SEROVAR"
            else:
                mismatch_type = "BOTH_MIXED_DIFFERENT"
        
        # Check PMC6035434 pattern
        is_pattern = (
            diag_result.article_has_strain_codes and
            gt_convention == "SEROVAR_ONLY" and
            ext_convention in ["STRAIN_ONLY", "MIXED"]
        )
        
        row = {
            "pmcid": pmcid,
            "split": gt_data.get("split", "unknown"),
            "article_has_serovar_mentions": diag_result.article_has_serovar_mentions,
            "article_has_strain_codes": diag_result.article_has_strain_codes,
            "article_strain_codes_list": ";".join(ext_strains[:10]),  # Limit to first 10
            "article_serovars_list": ";".join(ext_serovars[:10]),
            "serovar_to_strain_mapping": json.dumps(diag_result.serovar_to_strain_mapping),
            "gt_convention": gt_convention,
            "gt_identifiers_list": ";".join(gt_ids[:10]),
            "ext_convention": ext_convention,
            "ext_identifiers_list": ";".join(
                [e.get("identifier_as_written", "") for e in diag_result.isolate_entries[:10]]
            ),
            "convention_match": convention_match,
            "mismatch_type": mismatch_type,
            "is_pmc6035434_pattern": is_pattern
        }
        
        rows.append(row)
    
    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[INFO] Wrote {len(rows)} granularity analyses to {output_path}")


# =============================================================================
# SECTION 8: MAIN EXECUTION PIPELINE
# =============================================================================

def load_ground_truth(gt_source: str, splits_path: str = None) -> dict:
    """
    Load ground truth data from either:
    1. A directory of individual PMC JSON files + splits metadata file
    2. A single consolidated JSON file (legacy format)
    
    Args:
        gt_source: Either a directory path containing PMCxxxxxxx.json files,
                   or a path to a consolidated JSON file
        splits_path: Optional path to the stratified splits JSON file
                     (e.g., assay_tadp_gepa_optimised_splits.json)
    
    Returns:
        Dictionary mapping PMCID to ground truth data with structure:
        {
            "PMC1234567": {
                "stratum": "medium",
                "split": "validation",
                "isolates": [
                    {"isolate_id": "...", "Serotype": "...", "MLST": "...", ...}
                ]
            }
        }
    """
    ground_truth = {}
    
    # Check if gt_source is a directory or file
    if os.path.isdir(gt_source):
        # Load from directory of individual JSON files
        print(f"[INFO] Loading GT from directory: {gt_source}")
        
        # Load splits metadata if provided
        splits_metadata = {}
        if splits_path and os.path.exists(splits_path):
            with open(splits_path, "r", encoding="utf-8") as f:
                splits_data = json.load(f)
            
            # Build reverse lookup: PMCID -> split name
            for split_name in ["holdout_set", "validation_set", "training_10", "training_20", "training_30"]:
                if split_name in splits_data:
                    for pmcid in splits_data[split_name]:
                        splits_metadata[pmcid] = split_name.replace("_set", "").replace("training_", "train_")
            
            # Also check training_pool
            if "training_pool" in splits_data:
                for pmcid in splits_data["training_pool"]:
                    if pmcid not in splits_metadata:
                        splits_metadata[pmcid] = "training_pool"
            
            print(f"[INFO] Loaded splits metadata for {len(splits_metadata)} documents")
        
        # Load individual JSON files
        json_files = glob.glob(os.path.join(gt_source, "PMC*.json"))
        print(f"[INFO] Found {len(json_files)} PMC JSON files")
        
        for json_path in json_files:
            filename = os.path.basename(json_path)
            pmcid = filename.replace(".json", "")
            
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Extract isolates from the individual GT file format
                isolates = []
                
                # Primary isolate source: isolates_with_linking
                if "isolates_with_linking" in data:
                    for iso in data["isolates_with_linking"]:
                        isolates.append({
                            "isolate_id": iso.get("isolate_id", ""),
                            "Serotype": iso.get("serotype", []),
                            "MLST": iso.get("mlst", []),
                            "AST_Data": iso.get("ast_data", []),
                            "AMR": iso.get("amr", []),
                            "SPI": iso.get("spi", []),
                            "Plasmid": iso.get("plasmid", []),
                            "SNP": iso.get("snp", []),
                            "Virulence_Genes": iso.get("virulence_genes", []),
                            "isolate_source": iso.get("isolate_source", ""),
                            "isolate_country": iso.get("isolate_country", "")
                        })
                
                # Secondary: isolate_without_linking (isolates without assay data)
                if "isolate_without_linking" in data:
                    for iso_id in data["isolate_without_linking"]:
                        if isinstance(iso_id, str):
                            isolates.append({"isolate_id": iso_id})
                        elif isinstance(iso_id, dict):
                            isolates.append({
                                "isolate_id": iso_id.get("isolate_id", ""),
                                **iso_id
                            })
                
                # Determine stratum based on isolate count
                isolate_count = len(isolates)
                if isolate_count == 0:
                    stratum = "zero"
                elif isolate_count <= 5:
                    stratum = "low"
                elif isolate_count <= 20:
                    stratum = "medium"
                else:
                    stratum = "high"
                
                # Get split from metadata
                split = splits_metadata.get(pmcid, "unknown")
                
                ground_truth[pmcid] = {
                    "stratum": stratum,
                    "split": split,
                    "isolates": isolates,
                    "title": data.get("title", ""),
                    "accessions": data.get("merge_accession_number", [])
                }
                
            except Exception as e:
                print(f"[WARNING] Failed to load {json_path}: {e}")
                continue
        
        print(f"[INFO] Loaded ground truth for {len(ground_truth)} documents")
    
    else:
        # Load from single consolidated JSON file (legacy format)
        print(f"[INFO] Loading GT from consolidated file: {gt_source}")
        with open(gt_source, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)
    
    return ground_truth


def load_article_text(pmcid: str, xml_dir: str) -> Optional[str]:
    """
    Load article text from XML file.
    
    Args:
        pmcid: PMC identifier
        xml_dir: Directory containing XML files
        
    Returns:
        Article text or None if not found
    """
    # Try different filename patterns
    patterns = [
        f"{pmcid}.xml",
        f"{pmcid}_*.xml",
        f"*{pmcid}*.xml"
    ]
    
    for pattern in patterns:
        import glob
        matches = glob.glob(os.path.join(xml_dir, pattern))
        if matches:
            with open(matches[0], "r", encoding="utf-8") as f:
                return f.read()
    
    print(f"[WARNING] No XML file found for {pmcid}")
    return None


def run_diagnostic_pipeline(
    ground_truth_path: str,
    xml_directory: str,
    output_directory: str,
    splits_path: str = None,
    pmcid_list: Optional[list] = None,
    max_documents: Optional[int] = None
) -> tuple:
    """
    Run the full diagnostic pipeline.
    
    Args:
        ground_truth_path: Path to ground truth - either:
                          - Directory containing PMCxxxxxxx.json files, OR
                          - Single consolidated JSON file
        xml_directory: Directory containing article XML files
        output_directory: Directory to write output CSVs
        splits_path: Optional path to stratified splits JSON file
                    (e.g., assay_tadp_gepa_optimised_splits.json)
        pmcid_list: Optional list of specific PMCIDs to process
        max_documents: Optional limit on number of documents to process
        
    Returns:
        Tuple of (diagnostic_results: list, ground_truth: dict)
    """
    # Load ground truth
    print("[INFO] Loading ground truth...")
    ground_truth = load_ground_truth(ground_truth_path, splits_path)
    print(f"[INFO] Loaded {len(ground_truth)} documents from ground truth")
    
    # Determine documents to process
    if pmcid_list:
        pmcids = pmcid_list
    else:
        pmcids = list(ground_truth.keys())
    
    if max_documents:
        pmcids = pmcids[:max_documents]
    
    print(f"[INFO] Processing {len(pmcids)} documents")
    
    # Initialise extractor
    extractor = DiagnosticIsolateExtractor()
    
    # Process documents
    diagnostic_results = []
    
    for i, pmcid in enumerate(pmcids):
        print(f"[INFO] Processing {i+1}/{len(pmcids)}: {pmcid}")
        
        # Load article
        article_text = load_article_text(pmcid, xml_directory)
        if not article_text:
            continue
        
        # Run extraction
        try:
            prediction = extractor(article_text=article_text, pmcid=pmcid)
            raw_output = prediction.diagnostic_output
            
            # Parse result
            result = parse_diagnostic_output(raw_output, pmcid)
            if result:
                diagnostic_results.append(result)
                print(f"[INFO] Extracted {len(result.isolate_entries)} isolates from {pmcid}")
            else:
                print(f"[WARNING] Failed to parse output for {pmcid}")
                
        except Exception as e:
            print(f"[ERROR] Extraction failed for {pmcid}: {e}")
            continue
    
    # Generate output CSVs
    os.makedirs(output_directory, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    generate_discrepancy_csv(
        diagnostic_results,
        ground_truth,
        os.path.join(output_directory, f"discrepancy_analysis_{timestamp}.csv")
    )
    
    generate_document_summary_csv(
        diagnostic_results,
        ground_truth,
        os.path.join(output_directory, f"document_summary_{timestamp}.csv")
    )
    
    generate_granularity_analysis_csv(
        diagnostic_results,
        ground_truth,
        os.path.join(output_directory, f"granularity_analysis_{timestamp}.csv")
    )
    
    # Save raw results as JSON
    raw_results_path = os.path.join(output_directory, f"diagnostic_results_{timestamp}.json")
    with open(raw_results_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in diagnostic_results], f, indent=2)
    print(f"[INFO] Saved raw results to {raw_results_path}")
    
    return diagnostic_results, ground_truth


def print_pattern_summary(diagnostic_results: list, ground_truth: dict) -> None:
    """
    Print a summary of the PMC6035434 pattern analysis.
    """
    total_docs = len(diagnostic_results)
    pattern_count = 0
    pattern_pmcids = []
    
    for result in diagnostic_results:
        pmcid = result.pmcid
        gt_data = ground_truth.get(pmcid, {})
        gt_isolates = gt_data.get("isolates", [])
        
        # Check GT convention
        gt_ids = [iso.get("isolate_id", "") for iso in gt_isolates]
        gt_has_strain = any(any(c.isdigit() for c in id) or "-" in id for id in gt_ids)
        gt_has_serovar = any(not any(c.isdigit() for c in id) and "-" not in id for id in gt_ids)
        gt_serovar_only = gt_has_serovar and not gt_has_strain
        
        # Check extraction
        ext_types = [e.get("identifier_type", "") for e in result.isolate_entries]
        ext_has_strain = "STRAIN_CODE" in ext_types
        
        # Check pattern
        if (result.article_has_strain_codes and gt_serovar_only and ext_has_strain):
            pattern_count += 1
            pattern_pmcids.append(pmcid)
    
    print("\n" + "=" * 60)
    print("PMC6035434 PATTERN ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total documents analysed: {total_docs}")
    print(f"Documents matching pattern: {pattern_count}")
    print(f"Pattern percentage: {100 * pattern_count / total_docs:.1f}%")
    print()
    
    if pattern_count > 0:
        print("Documents with PMC6035434 pattern:")
        for pmcid in pattern_pmcids:
            print(f"  - {pmcid}")
    
    print()
    if pattern_count / total_docs > 0.10:
        print("RECOMMENDATION: Pattern is SYSTEMATIC (>10%)")
        print("  -> Update DSPy signature to prefer serovar-level when both exist")
    elif pattern_count / total_docs < 0.05:
        print("RECOMMENDATION: Pattern is OUTLIER (<5%)")
        print("  -> Update individual GT entries to use strain codes")
    else:
        print("RECOMMENDATION: Pattern is BORDERLINE (5-10%)")
        print("  -> Manual review of individual cases recommended")
    print("=" * 60)


# =============================================================================
# SECTION 9: COLAB NOTEBOOK CELLS
# =============================================================================

COLAB_SETUP_CELL = '''
# =============================================================================
# CELL 1: Setup and Installation
# =============================================================================
# Run this cell first to install required packages

!pip install dspy-ai --quiet
!pip install anthropic --quiet

import os
from google.colab import drive

# Mount Google Drive
drive.mount('/content/drive')

# Set your paths
PROJECT_DIR = "/content/drive/MyDrive/AI6129"  # Adjust to your project directory
GT_PATH = os.path.join(PROJECT_DIR, "ground_truth/assay_ground_truth.json")
XML_DIR = os.path.join(PROJECT_DIR, "xml")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "diagnostic_output")

print(f"Project directory: {PROJECT_DIR}")
print(f"Ground truth path: {GT_PATH}")
print(f"XML directory: {XML_DIR}")
print(f"Output directory: {OUTPUT_DIR}")
'''

COLAB_CONFIG_CELL = '''
# =============================================================================
# CELL 2: Configure DSPy with Claude
# =============================================================================

import dspy

# Configure the LLM
# Option 1: Using Anthropic directly
lm = dspy.LM(
    model="anthropic/claude-3-5-haiku-20241022",
    api_key=os.environ.get("ANTHROPIC_API_KEY"),  # Set in Colab secrets
    max_tokens=16384
)

# Option 2: Using Google AI Studio (if available in Colab)
# lm = dspy.LM(model="gemini/gemini-1.5-flash")

dspy.configure(lm=lm)

print("DSPy configured successfully")
'''

COLAB_RUN_CELL = '''
# =============================================================================
# CELL 3: Run Diagnostic Pipeline
# =============================================================================

# Import the diagnostic module (copy the full script to a .py file or paste above)
# from isolate_granularity_diagnostic import run_diagnostic_pipeline, print_pattern_summary, load_ground_truth

# Run on a subset first to test
results = run_diagnostic_pipeline(
    ground_truth_path=GT_PATH,
    xml_directory=XML_DIR,
    output_directory=OUTPUT_DIR,
    max_documents=10  # Start with 10 documents for testing
)

# Load ground truth for summary
ground_truth = load_ground_truth(GT_PATH)

# Print pattern summary
print_pattern_summary(results, ground_truth)
'''

COLAB_FULL_RUN_CELL = '''
# =============================================================================
# CELL 4: Full Pipeline Run (after testing)
# =============================================================================

# Run on all documents
results = run_diagnostic_pipeline(
    ground_truth_path=GT_PATH,
    xml_directory=XML_DIR,
    output_directory=OUTPUT_DIR,
    max_documents=None  # Process all documents
)

# Print final summary
print_pattern_summary(results, ground_truth)
'''


# =============================================================================
# SECTION 10: ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("Isolate Granularity Diagnostic Analysis")
    print("=" * 40)
    print()
    print("This script is designed to be run in Google Colab.")
    print("Copy the COLAB_*_CELL strings into notebook cells.")
    print()
    print("Alternatively, run from command line:")
    print("  python isolate_granularity_diagnostic.py --gt PATH --xml DIR --out DIR")
    print()
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt", help="Path to ground truth (directory of PMC*.json files or consolidated JSON)")
    parser.add_argument("--splits", help="Path to stratified splits JSON file (optional)")
    parser.add_argument("--xml", help="Directory containing XML files")
    parser.add_argument("--out", help="Output directory for CSVs")
    parser.add_argument("--max", type=int, help="Maximum documents to process")
    
    args = parser.parse_args()
    
    if args.gt and args.xml and args.out:
        results = run_diagnostic_pipeline(
            ground_truth_path=args.gt,
            xml_directory=args.xml,
            output_directory=args.out,
            splits_path=args.splits,
            max_documents=args.max
        )
        
        ground_truth = load_ground_truth(args.gt, args.splits)
        print_pattern_summary(results, ground_truth)
