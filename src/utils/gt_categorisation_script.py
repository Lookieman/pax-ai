# =============================================================================
# GT DOCUMENT CATEGORISATION FOR TRAINING SELECTION
# =============================================================================
# Purpose: Identify which documents to use for training vs reserve for multimodal
# Output: 70 documents categorised into:
#   - 60 for training (no granularity mismatch)
#   - 10 reserved for multimodal experiments (granularity mismatch)
# =============================================================================


# -----------------------------------------------------------------------------
# CELL 1: Configuration
# -----------------------------------------------------------------------------

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter

# Paths - update for your environment
GROUND_TRUTH_DIR = Path("/content/drive/MyDrive/AI6129/ground_truth")
XML_DIR = Path("/content/drive/MyDrive/AI6129/xml_files")
OUTPUT_DIR = Path("/content/drive/MyDrive/AI6129/assay/gt_categorisation")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Documents to exclude (golden records - keep separate)
GOLDEN_PMCIDS = set()  # Add your 45 golden PMCIDs here


# -----------------------------------------------------------------------------
# CELL 2: Heuristic Functions for Pre-filtering
# -----------------------------------------------------------------------------

def analyse_isolate_id_pattern(isolate_ids: List[str]) -> Dict[str, Any]:
    """
    Analyse isolate ID patterns to predict granularity issues.
    
    Returns dict with pattern analysis results.
    """
    if not isolate_ids:
        return {"pattern": "none", "risk": "low", "count": 0}
    
    patterns = {
        "lab_sequential": 0,      # ZJSX2020-001, ZJSX2020-002 (likely supplementary)
        "simple_codes": 0,        # S1, S2, S3 (could be either)
        "accession_like": 0,      # SAMN*, MG*, CP* (likely in text)
        "serovar_names": 0,       # Typhimurium, Enteritidis (document-level)
        "descriptive": 0,         # "Case_Patient", "Isolate_A" (likely in text)
        "other": 0
    }
    
    for iso_id in isolate_ids:
        iso_id_lower = iso_id.lower()
        
        # Lab sequential codes (high risk of supplementary)
        if re.match(r'^[a-z]{2,6}[\-_]?\d{4}[\-_]\d{2,3}$', iso_id_lower):
            patterns["lab_sequential"] += 1
        # Simple codes like S1, S2, NC1, NC2
        elif re.match(r'^[a-z]{1,3}\d{1,3}$', iso_id_lower):
            patterns["simple_codes"] += 1
        # Accession numbers
        elif re.match(r'^(samn|samea|mg|cp|nc_|nz_)\d+', iso_id_lower):
            patterns["accession_like"] += 1
        # Serovar names
        elif any(sero in iso_id_lower for sero in ['typhimurium', 'enteritidis', 'infantis', 'heidelberg', 'newport']):
            patterns["serovar_names"] += 1
        # Descriptive IDs
        elif any(desc in iso_id_lower for desc in ['case', 'patient', 'isolate', 'sample', 'strain']):
            patterns["descriptive"] += 1
        else:
            patterns["other"] += 1
    
    # Determine dominant pattern
    dominant = max(patterns, key=patterns.get)
    
    # Assess risk of granularity mismatch
    if patterns["lab_sequential"] > len(isolate_ids) * 0.5:
        risk = "high"  # Likely from supplementary files
    elif patterns["serovar_names"] > len(isolate_ids) * 0.5:
        risk = "medium"  # Document-level, may mismatch
    elif patterns["accession_like"] > len(isolate_ids) * 0.3:
        risk = "low"  # Accessions usually in text
    elif patterns["simple_codes"] > len(isolate_ids) * 0.5:
        risk = "medium"  # Could be either
    else:
        risk = "medium"
    
    return {
        "pattern": dominant,
        "patterns": patterns,
        "risk": risk,
        "count": len(isolate_ids),
        "sample_ids": isolate_ids[:5]
    }


def check_article_for_isolate_ids(article_text: str, isolate_ids: List[str], sample_size: int = 10) -> Dict[str, Any]:
    """
    Check if isolate IDs from GT appear in article text.
    
    Returns dict with match statistics.
    """
    if not isolate_ids or not article_text:
        return {"match_rate": 0, "matched": 0, "total": 0}
    
    # Sample IDs to check (checking all could be slow)
    ids_to_check = isolate_ids[:sample_size] if len(isolate_ids) > sample_size else isolate_ids
    
    article_lower = article_text.lower()
    matched = 0
    matched_ids = []
    unmatched_ids = []
    
    for iso_id in ids_to_check:
        # Check for exact match or close variants
        iso_lower = iso_id.lower()
        
        if iso_lower in article_lower:
            matched += 1
            matched_ids.append(iso_id)
        elif iso_lower.replace('-', '') in article_lower.replace('-', ''):
            matched += 1
            matched_ids.append(iso_id)
        elif iso_lower.replace('_', '') in article_lower.replace('_', ''):
            matched += 1
            matched_ids.append(iso_id)
        else:
            unmatched_ids.append(iso_id)
    
    match_rate = matched / len(ids_to_check) if ids_to_check else 0
    
    return {
        "match_rate": match_rate,
        "matched": matched,
        "total": len(ids_to_check),
        "matched_ids": matched_ids[:3],
        "unmatched_ids": unmatched_ids[:3]
    }


def assess_gt_complexity(gt_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess GT complexity and structure.
    """
    isolate_count = 0
    assay_types = set()
    has_ast_data = False
    has_document_level = False
    
    # Count isolates with linking
    if "isolates_with_linking" in gt_data:
        iwl = gt_data["isolates_with_linking"]
        if isinstance(iwl, dict):
            isolate_count += len(iwl)
            for iso_id, assays in iwl.items():
                if isinstance(assays, dict):
                    assay_types.update(assays.keys())
                    if "ast_data" in assays:
                        has_ast_data = True
        elif isinstance(iwl, list):
            isolate_count += len(iwl)
    
    # Check for document-level data
    if "no_isolates_only_assayinformation" in gt_data:
        nioai = gt_data["no_isolates_only_assayinformation"]
        if nioai and isinstance(nioai, dict) and any(nioai.values()):
            has_document_level = True
    
    return {
        "isolate_count": isolate_count,
        "assay_types": list(assay_types),
        "assay_type_count": len(assay_types),
        "has_ast_data": has_ast_data,
        "has_document_level": has_document_level
    }


# -----------------------------------------------------------------------------
# CELL 3: Main Categorisation Function
# -----------------------------------------------------------------------------

def categorise_document(
    pmcid: str,
    gt_data: Dict[str, Any],
    article_text: str
) -> Dict[str, Any]:
    """
    Categorise a single document based on GT analysis and article matching.
    
    Returns categorisation result with recommendation.
    """
    # Extract isolate IDs
    isolate_ids = []
    if "isolates_with_linking" in gt_data:
        iwl = gt_data["isolates_with_linking"]
        if isinstance(iwl, dict):
            isolate_ids = list(iwl.keys())
        elif isinstance(iwl, list):
            for iso in iwl:
                if isinstance(iso, dict) and "isolate_id" in iso:
                    isolate_ids.append(iso["isolate_id"])
    
    # Run analyses
    id_analysis = analyse_isolate_id_pattern(isolate_ids)
    text_match = check_article_for_isolate_ids(article_text, isolate_ids)
    complexity = assess_gt_complexity(gt_data)
    
    # Determine category
    if text_match["match_rate"] >= 0.7:
        # Most IDs found in text - good for training
        category = "A_TRAINING"
        reason = f"High ID match rate ({text_match['match_rate']:.0%})"
    elif text_match["match_rate"] >= 0.3:
        # Some IDs found - needs review
        category = "B_REVIEW"
        reason = f"Partial ID match ({text_match['match_rate']:.0%})"
    elif id_analysis["risk"] == "high" and complexity["isolate_count"] > 10:
        # Lab sequential codes, many isolates - likely supplementary
        category = "C_MULTIMODAL"
        reason = f"Lab codes pattern, {complexity['isolate_count']} isolates, low text match"
    elif complexity["has_document_level"] and complexity["isolate_count"] == 0:
        # Document-level only - good for training
        category = "A_TRAINING"
        reason = "Document-level GT only"
    else:
        # Needs manual review
        category = "B_REVIEW"
        reason = f"Mixed signals: {id_analysis['risk']} risk, {text_match['match_rate']:.0%} match"
    
    return {
        "pmcid": pmcid,
        "category": category,
        "reason": reason,
        "id_analysis": id_analysis,
        "text_match": text_match,
        "complexity": complexity
    }


# -----------------------------------------------------------------------------
# CELL 4: Batch Categorisation
# -----------------------------------------------------------------------------

def run_categorisation_batch(
    pmcid_list: List[str],
    xml_mapping: Dict[str, str],
    gt_dir: Path,
    output_dir: Path
) -> Dict[str, Any]:
    """
    Run categorisation on a batch of documents.
    """
    results = {
        "A_TRAINING": [],
        "B_REVIEW": [],
        "C_MULTIMODAL": []
    }
    all_results = []
    
    print(f"Categorising {len(pmcid_list)} documents...")
    
    for i, pmcid in enumerate(pmcid_list):
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(pmcid_list)}")
        
        # Load GT
        gt_data = load_ground_truth(pmcid, gt_dir)
        if gt_data is None:
            continue
        
        # Load article text
        if pmcid not in xml_mapping:
            continue
        
        try:
            article_text, _, _ = prepare_article_for_extraction(
                pmcid, xml_mapping[pmcid], max_tokens=50000
            )
        except Exception as e:
            print(f"  [WARNING] Could not load article for {pmcid}: {e}")
            continue
        
        # Categorise
        result = categorise_document(pmcid, gt_data, article_text)
        all_results.append(result)
        results[result["category"]].append(pmcid)
    
    # Summary
    summary = {
        "total_processed": len(all_results),
        "category_counts": {cat: len(pmcids) for cat, pmcids in results.items()},
        "categories": results,
        "details": all_results
    }
    
    # Save results
    output_path = output_dir / "categorisation_results.json"
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("CATEGORISATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total processed: {summary['total_processed']}")
    print(f"\nCategory breakdown:")
    print(f"  A_TRAINING (good for training):     {summary['category_counts']['A_TRAINING']}")
    print(f"  B_REVIEW (needs manual review):     {summary['category_counts']['B_REVIEW']}")
    print(f"  C_MULTIMODAL (reserve for later):   {summary['category_counts']['C_MULTIMODAL']}")
    print(f"\nResults saved to: {output_path}")
    
    return summary


# -----------------------------------------------------------------------------
# CELL 5: Run Categorisation
# -----------------------------------------------------------------------------

# Get all PMCIDs (excluding golden records)
all_pmcids = [p for p in xml_mapping.keys() if p not in GOLDEN_PMCIDS]

print(f"Total documents available: {len(all_pmcids)}")
print(f"Golden records excluded: {len(GOLDEN_PMCIDS)}")

# Run categorisation
categorisation_results = run_categorisation_batch(
    pmcid_list=all_pmcids,
    xml_mapping=xml_mapping,
    gt_dir=GROUND_TRUTH_DIR,
    output_dir=OUTPUT_DIR
)


# -----------------------------------------------------------------------------
# CELL 6: Select Final Training and Multimodal Sets
# -----------------------------------------------------------------------------

def select_final_sets(
    categorisation_results: Dict[str, Any],
    target_training: int = 60,
    target_multimodal: int = 10
) -> Dict[str, List[str]]:
    """
    Select final document sets for training and multimodal experiments.
    """
    categories = categorisation_results["categories"]
    details = {r["pmcid"]: r for r in categorisation_results["details"]}
    
    # Start with Category A for training
    training_candidates = categories["A_TRAINING"].copy()
    
    # Add from Category B if needed (prioritise higher match rates)
    if len(training_candidates) < target_training:
        review_docs = [(pmcid, details[pmcid]["text_match"]["match_rate"]) 
                       for pmcid in categories["B_REVIEW"]]
        review_docs.sort(key=lambda x: x[1], reverse=True)
        
        needed = target_training - len(training_candidates)
        for pmcid, match_rate in review_docs[:needed]:
            if match_rate >= 0.3:  # Only add if reasonable match rate
                training_candidates.append(pmcid)
    
    # Select multimodal candidates from Category C
    multimodal_candidates = categories["C_MULTIMODAL"][:target_multimodal]
    
    # If not enough multimodal, take from B_REVIEW with low match rates
    if len(multimodal_candidates) < target_multimodal:
        review_docs = [(pmcid, details[pmcid]["text_match"]["match_rate"]) 
                       for pmcid in categories["B_REVIEW"]
                       if pmcid not in training_candidates]
        review_docs.sort(key=lambda x: x[1])  # Lowest match rate first
        
        needed = target_multimodal - len(multimodal_candidates)
        for pmcid, match_rate in review_docs[:needed]:
            multimodal_candidates.append(pmcid)
    
    final_sets = {
        "training": training_candidates[:target_training],
        "multimodal_reserved": multimodal_candidates[:target_multimodal],
        "excluded": [p for p in categories["B_REVIEW"] + categories["C_MULTIMODAL"]
                    if p not in training_candidates[:target_training] 
                    and p not in multimodal_candidates[:target_multimodal]]
    }
    
    print(f"\n{'='*60}")
    print("FINAL SET SELECTION")
    print(f"{'='*60}")
    print(f"Training set: {len(final_sets['training'])} documents")
    print(f"Multimodal reserved: {len(final_sets['multimodal_reserved'])} documents")
    print(f"Excluded: {len(final_sets['excluded'])} documents")
    
    return final_sets


# Run selection
final_sets = select_final_sets(
    categorisation_results,
    target_training=60,
    target_multimodal=10
)

# Save final sets
final_sets_path = OUTPUT_DIR / "final_document_sets.json"
with open(final_sets_path, 'w') as f:
    json.dump(final_sets, f, indent=2)

print(f"\nFinal sets saved to: {final_sets_path}")


# -----------------------------------------------------------------------------
# CELL 7: Review Selected Documents
# -----------------------------------------------------------------------------

def review_selected_documents(
    final_sets: Dict[str, List[str]],
    categorisation_results: Dict[str, Any]
):
    """
    Display summary of selected documents for review.
    """
    details = {r["pmcid"]: r for r in categorisation_results["details"]}
    
    print(f"\n{'='*70}")
    print("TRAINING SET SUMMARY")
    print(f"{'='*70}")
    print(f"\n{'PMCID':<15} {'Match%':>8} {'Isolates':>10} {'Pattern':<15} {'Reason'}")
    print("-" * 70)
    
    for pmcid in final_sets["training"][:20]:  # Show first 20
        d = details.get(pmcid, {})
        match_rate = d.get("text_match", {}).get("match_rate", 0)
        isolate_count = d.get("complexity", {}).get("isolate_count", 0)
        pattern = d.get("id_analysis", {}).get("pattern", "?")
        reason = d.get("reason", "?")[:30]
        print(f"{pmcid:<15} {match_rate:>7.0%} {isolate_count:>10} {pattern:<15} {reason}")
    
    if len(final_sets["training"]) > 20:
        print(f"... and {len(final_sets['training']) - 20} more")
    
    print(f"\n{'='*70}")
    print("MULTIMODAL RESERVED SET")
    print(f"{'='*70}")
    print(f"\n{'PMCID':<15} {'Match%':>8} {'Isolates':>10} {'Pattern':<15} {'Reason'}")
    print("-" * 70)
    
    for pmcid in final_sets["multimodal_reserved"]:
        d = details.get(pmcid, {})
        match_rate = d.get("text_match", {}).get("match_rate", 0)
        isolate_count = d.get("complexity", {}).get("isolate_count", 0)
        pattern = d.get("id_analysis", {}).get("pattern", "?")
        reason = d.get("reason", "?")[:30]
        print(f"{pmcid:<15} {match_rate:>7.0%} {isolate_count:>10} {pattern:<15} {reason}")


review_selected_documents(final_sets, categorisation_results)


# -----------------------------------------------------------------------------
# CELL 8: Export Training PMCIDs for GEPA
# -----------------------------------------------------------------------------

# Export just the PMCID list for easy use
training_pmcids = final_sets["training"]
multimodal_pmcids = final_sets["multimodal_reserved"]

print(f"\n{'='*60}")
print("EXPORT FOR GEPA")
print(f"{'='*60}")
print(f"\nTraining PMCIDs ({len(training_pmcids)}):")
print(training_pmcids)

print(f"\nMultimodal Reserved PMCIDs ({len(multimodal_pmcids)}):")
print(multimodal_pmcids)

# Save as simple text file for easy copy
with open(OUTPUT_DIR / "training_pmcids.txt", 'w') as f:
    f.write('\n'.join(training_pmcids))

with open(OUTPUT_DIR / "multimodal_pmcids.txt", 'w') as f:
    f.write('\n'.join(multimodal_pmcids))

print(f"\nPMCID lists saved to {OUTPUT_DIR}")
