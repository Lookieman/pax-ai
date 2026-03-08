"""
Update Validation Splits - DD-2026-005
======================================

Purpose: Remove problematic documents from validation set and replace with
         suitable candidates from holdout set.

Documents to Remove:
1. PMC6035434 - Outlier granularity pattern (serovar GT, strain codes in article)
2. PMC4824889 - Zero extraction (isolates in figures/supplementary, not in XML)

Replacements:
1. PMC7587706 - Replaces PMC6035434 (Q4, TADP=59, IWL - closest match)
2. PMC7083327 - Replaces PMC4824889 (Q1, TADP=0, IWOL - exact match)

Author: Luqman
Date: February 2026
Decision ID: DD-2026-005
"""

import json
import os
from datetime import datetime
from copy import deepcopy


def update_splits(input_path: str, output_path: str) -> dict:
    """
    Update the splits file by swapping validation and holdout documents.
    
    Args:
        input_path: Path to original splits JSON file
        output_path: Path to write updated splits JSON file
        
    Returns:
        Summary of changes made
    """
    # Load original splits
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Create deep copy to avoid modifying original
    updated = deepcopy(data)
    
    # Define swaps: (remove_from_validation, add_to_validation)
    swaps = [
        {
            'remove': 'PMC6035434',
            'add': 'PMC7587706',
            'reason': 'Outlier granularity pattern - GT uses serovar, article has strain codes, LLM extracts strain codes',
            'match_criteria': 'Q4, TADP=59 (vs 58), IWL category'
        },
        {
            'remove': 'PMC4824889',
            'add': 'PMC7083327',
            'reason': 'Zero extraction - isolates in figures/supplementary, not accessible in XML text',
            'match_criteria': 'Q1, TADP=0, IWOL category - exact match'
        }
    ]
    
    # Track changes
    changes = []
    
    for swap in swaps:
        remove_pmcid = swap['remove']
        add_pmcid = swap['add']
        
        # Validate documents exist in expected sets
        if remove_pmcid not in updated['validation_set']:
            print(f"[WARNING] {remove_pmcid} not found in validation_set")
            continue
            
        if add_pmcid not in updated['holdout_set']:
            print(f"[WARNING] {add_pmcid} not found in holdout_set")
            continue
        
        # Perform swap
        updated['validation_set'].remove(remove_pmcid)
        updated['validation_set'].append(add_pmcid)
        
        updated['holdout_set'].remove(add_pmcid)
        updated['holdout_set'].append(remove_pmcid)
        
        change_record = {
            'action': 'swap',
            'removed_from_validation': remove_pmcid,
            'added_to_validation': add_pmcid,
            'reason': swap['reason'],
            'match_criteria': swap['match_criteria']
        }
        changes.append(change_record)
        
        print(f"[INFO] Swapped: {remove_pmcid} (validation) <-> {add_pmcid} (holdout)")
    
    # Update metadata
    updated['metadata']['updated_at'] = datetime.now().isoformat()
    updated['metadata']['update_reason'] = 'DD-2026-005: Remove problematic validation documents'
    updated['metadata']['changes'] = changes
    
    # Preserve original metadata
    if 'original_created_at' not in updated['metadata']:
        updated['metadata']['original_created_at'] = updated['metadata'].get('created_at', 'unknown')
    
    # Validate counts haven't changed
    assert len(updated['validation_set']) == len(data['validation_set']), \
        "Validation set size changed unexpectedly"
    assert len(updated['holdout_set']) == len(data['holdout_set']), \
        "Holdout set size changed unexpectedly"
    
    # Write updated splits
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(updated, f, indent=2)
    
    print(f"\n[INFO] Updated splits written to: {output_path}")
    
    return {
        'changes': changes,
        'validation_set_size': len(updated['validation_set']),
        'holdout_set_size': len(updated['holdout_set']),
        'output_path': output_path
    }


def verify_update(original_path: str, updated_path: str) -> None:
    """
    Verify the update was applied correctly.
    """
    with open(original_path, 'r') as f:
        original = json.load(f)
    
    with open(updated_path, 'r') as f:
        updated = json.load(f)
    
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    
    # Check validation set
    print("\n--- VALIDATION SET ---")
    print(f"Original size: {len(original['validation_set'])}")
    print(f"Updated size:  {len(updated['validation_set'])}")
    
    removed = set(original['validation_set']) - set(updated['validation_set'])
    added = set(updated['validation_set']) - set(original['validation_set'])
    
    print(f"Removed from validation: {removed}")
    print(f"Added to validation:     {added}")
    
    # Check holdout set
    print("\n--- HOLDOUT SET ---")
    print(f"Original size: {len(original['holdout_set'])}")
    print(f"Updated size:  {len(updated['holdout_set'])}")
    
    removed_holdout = set(original['holdout_set']) - set(updated['holdout_set'])
    added_holdout = set(updated['holdout_set']) - set(original['holdout_set'])
    
    print(f"Removed from holdout: {removed_holdout}")
    print(f"Added to holdout:     {added_holdout}")
    
    # Verify swaps are symmetric
    print("\n--- SWAP VERIFICATION ---")
    if removed == added_holdout and added == removed_holdout:
        print("[OK] Swaps are symmetric - validation removals match holdout additions")
    else:
        print("[ERROR] Swaps are NOT symmetric!")
    
    # Check document details preserved
    print("\n--- DOCUMENT DETAILS ---")
    for pmcid in list(removed) + list(added):
        if pmcid in updated.get('document_details', {}):
            details = updated['document_details'][pmcid]
            print(f"  {pmcid}: TADP={details.get('tadp')}, Q={details.get('quartile')}, Cat={details.get('category')}")
    
    # Show metadata
    print("\n--- METADATA ---")
    print(f"Updated at: {updated['metadata'].get('updated_at', 'N/A')}")
    print(f"Reason: {updated['metadata'].get('update_reason', 'N/A')}")


def print_decision_document() -> str:
    """
    Generate the design decision document text.
    """
    dd_text = """
================================================================================
DESIGN DECISION: DD-2026-005
================================================================================

Title: Validation Set Refinement - Remove Problematic Documents

Date: February 2026
Author: Luqman
Status: Approved

--------------------------------------------------------------------------------
PROBLEM STATEMENT
--------------------------------------------------------------------------------

Diagnostic analysis of the validation set (35 documents) identified two 
documents that should be excluded from evaluation:

1. PMC6035434 - Exhibits the "PMC6035434 pattern" (only 1 of 35 = 2.9%)
   - GT uses serovar-level identifiers (S. Saintpaul, S. Typhimurium, etc.)
   - Article contains strain codes (DP-23, DP-24, etc.)
   - LLM correctly extracts strain codes
   - This creates unfair evaluation penalty

2. PMC4824889 - Zero extraction issue
   - GT contains 31 strain codes (P3174, P3210, P3388, etc.)
   - These identifiers appear in figures/supplementary files
   - XML text does not contain these identifiers
   - LLM cannot extract what it cannot see

--------------------------------------------------------------------------------
DECISION
--------------------------------------------------------------------------------

Remove both documents from validation_set and replace with matching documents
from holdout_set to maintain validation set size and distribution.

Replacements selected based on:
- Same quartile (complexity tier)
- Similar TADP (Total Assay Data Points)
- Same category (IWL, IWOL, etc.)

| Remove       | Replace With | Quartile | TADP      | Category |
|--------------|--------------|----------|-----------|----------|
| PMC6035434   | PMC7587706   | Q4       | 58 -> 59  | IWL      |
| PMC4824889   | PMC7083327   | Q1       | 0 -> 0    | IWOL     |

--------------------------------------------------------------------------------
RATIONALE
--------------------------------------------------------------------------------

1. PMC6035434 Pattern is an OUTLIER (2.9%), not systematic
   - No need to update DSPy signature
   - Let GEPA learn GT convention from training data
   - Removing outlier prevents GEPA from learning wrong pattern

2. PMC4824889 represents a MULTIMODAL case
   - Text-based extraction cannot access figure/supplementary data
   - Unfair to evaluate text-only pipeline against multimodal GT
   - Can be used later for multimodal extraction testing (DD-2025-001)

3. Validation set integrity maintained
   - Size remains 35 documents
   - Quartile distribution preserved
   - Category distribution preserved

--------------------------------------------------------------------------------
IMPACT
--------------------------------------------------------------------------------

- Validation set: 35 documents (unchanged)
- Holdout set: 45 documents (unchanged)
- Training pool: 147 documents (unchanged)

Removed documents moved to holdout for potential future use.

--------------------------------------------------------------------------------
ALTERNATIVES CONSIDERED
--------------------------------------------------------------------------------

| Alternative                        | Decision | Reason                      |
|------------------------------------|----------|------------------------------|
| Update GT for PMC6035434           | Rejected | Would change GT convention   |
| Update signature to prefer serovar | Rejected | Let GEPA decide             |
| Keep documents with lenient eval   | Rejected | Still unfair for strict F1  |
| Exclude without replacement        | Rejected | Reduces validation size     |

--------------------------------------------------------------------------------
RELATED DECISIONS
--------------------------------------------------------------------------------

- DD-2025-003: GEPA-Optimised Data Stratification
- DD-2025-001: Multimodal Extraction Design (PMC4824889 candidate)
- DD-2026-004: GEPA Stage 0 Pilot Implementation

================================================================================
"""
    return dd_text


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update validation splits by swapping problematic documents"
    )
    parser.add_argument(
        "--input", 
        required=True,
        help="Path to original splits JSON file"
    )
    parser.add_argument(
        "--output",
        help="Path for updated splits JSON (default: adds '_updated' suffix)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify an existing update, don't modify"
    )
    parser.add_argument(
        "--print-dd",
        action="store_true",
        help="Print the design decision document"
    )
    
    args = parser.parse_args()
    
    if args.print_dd:
        print(print_decision_document())
        exit(0)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(args.input)
        output_path = f"{base}_updated{ext}"
    
    if args.verify_only:
        verify_update(args.input, output_path)
    else:
        # Perform update
        summary = update_splits(args.input, output_path)
        
        # Verify
        verify_update(args.input, output_path)
        
        # Print decision document
        print(print_decision_document())
