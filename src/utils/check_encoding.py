"""
check_encoding.py
=================
Scan ground truth JSON files for problematic Unicode characters
that may cause encoding issues or invisible character warnings
in editors like VSCode.

Usage:
    python check_encoding.py
    python check_encoding.py --apply   # Auto-fix common issues

Scans both GROUND_TRUTH_PATH and GOLDEN_GT_PATH directories.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   29 March 2026
"""

import json
import re
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — update these paths to match your local setup
# ---------------------------------------------------------------------------

GROUND_TRUTH_PATH = Path(r"G:\My Drive\AI6129\ground_truth")
GOLDEN_GT_PATH = Path(r"G:\My Drive\AI6129\ground_truth\golden")

# PMCIDs in the golden GT set
GOLDEN_PMCIDS = [
    "PMC1278947", "PMC2694269", "PMC2725854", "PMC2873750", "PMC2874370",
    "PMC2958529", "PMC3020606", "PMC5074519", "PMC5739443", "PMC4892500",
    "PMC4932652", "PMC7598458", "PMC7783345", "PMC9641423", "PMC9643863",
    "PMC7273606", "PMC2409344", "PMC4881965", "PMC5033494", "PMC6667439",
]

# Characters that are problematic (invisible, encoding-breaking, or confusing)
PROBLEMATIC_CHARS = {
    '\xa0':   ('NBSP',              ' '),       # Non-breaking space -> space
    '\u200b': ('ZWSP',              ''),        # Zero-width space -> remove
    '\u200c': ('ZWNJ',             ''),        # Zero-width non-joiner
    '\u200d': ('ZWJ',              ''),        # Zero-width joiner
    '\u200e': ('LRM',              ''),        # Left-to-right mark
    '\u200f': ('RLM',              ''),        # Right-to-left mark
    '\u202a': ('LRE',              ''),        # Left-to-right embedding
    '\u202b': ('RLE',              ''),        # Right-to-left embedding
    '\u202c': ('PDF',              ''),        # Pop directional formatting
    '\u202d': ('LRO',              ''),        # Left-to-right override
    '\u202e': ('RLO',              ''),        # Right-to-left override
    '\u2060': ('WJ',               ''),        # Word joiner
    '\ufeff': ('BOM',              ''),        # Byte order mark
    '\u00ad': ('SHY',              ''),        # Soft hyphen
    '\u2028': ('LINE SEP',         '\n'),      # Line separator
    '\u2029': ('PARA SEP',         '\n'),      # Paragraph separator
}

# Characters that should be normalised but are not invisible
NORMALISE_CHARS = {
    '\u2019': ('RIGHT QUOTE',      "'"),       # Right single quote -> apostrophe
    '\u2018': ('LEFT QUOTE',       "'"),       # Left single quote -> apostrophe
    '\u201c': ('LEFT DQUOTE',      '"'),       # Left double quote
    '\u201d': ('RIGHT DQUOTE',     '"'),       # Right double quote
    '\u2010': ('HYPHEN',           '-'),       # Unicode hyphen -> ASCII
    '\u2011': ('NB HYPHEN',        '-'),       # Non-breaking hyphen
    '\u2012': ('FIGURE DASH',      '-'),       # Figure dash
    '\u2013': ('EN DASH',          '-'),       # En dash
    '\u2014': ('EM DASH',          '-'),       # Em dash
    '\u2212': ('MINUS SIGN',       '-'),       # Math minus -> ASCII hyphen
    '\u2020': ('DAGGER',           ''),        # Dagger -> remove
    '\u2122': ('TM',               '(TM)'),    # Trademark
    '\u00d7': ('MULTIPLY',         'x'),       # Multiplication sign
}


def scan_file(filepath, apply_fixes=False):
    """Scan a single GT JSON file for encoding issues.

    Args:
        filepath: Path to the JSON file.
        apply_fixes: If True, write corrected file back.

    Returns:
        Dictionary with scan results.
    """
    results = {
        'file': str(filepath),
        'pmcid': filepath.stem,                                              #changed: no _gt suffix to strip
        'problematic': {},       # char -> count
        'normalisable': {},      # char -> count
        'total_issues': 0,
        'fixed': False,
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError as e:
        results['error'] = f"UnicodeDecodeError: {e}"
        return results

    # Scan for problematic characters
    for char, (name, replacement) in PROBLEMATIC_CHARS.items():
        count = content.count(char)
        if count > 0:
            results['problematic'][name] = count
            results['total_issues'] += count

    # Scan for normalisable characters
    for char, (name, replacement) in NORMALISE_CHARS.items():
        count = content.count(char)
        if count > 0:
            results['normalisable'][name] = count
            results['total_issues'] += count

    # Apply fixes if requested
    if apply_fixes and results['total_issues'] > 0:
        # Build combined replacement map                                     #changed
        all_replacements = {}                                                #changed
        all_replacements.update(PROBLEMATIC_CHARS)                           #changed
        all_replacements.update(NORMALISE_CHARS)                             #changed

        # Parse JSON, fix string values, re-serialise                        #changed
        # This avoids breaking JSON structure when replacing quotes          #changed
        try:                                                                 #changed
            # Repair trailing commas before parsing                          #changed
            repaired = re.sub(r",\s*([}\]])", r"\1", content)               #changed
            data = json.loads(repaired)                                      #changed
            _fix_strings_recursive(data, all_replacements)                   #changed
            fixed_content = json.dumps(                                      #changed
                data, indent=2, ensure_ascii=False                           #changed
            )                                                                #changed
            with open(filepath, 'w', encoding='utf-8') as f:                #changed
                f.write(fixed_content)                                       #changed
            results['fixed'] = True                                          #changed
        except json.JSONDecodeError as e:                                    #changed
            results['fix_error'] = f"Cannot parse original JSON: {e}"        #changed
        except Exception as e:                                               #changed
            results['fix_error'] = f"Fix failed: {e}"                        #changed

    return results


def _fix_strings_recursive(obj, replacements):                               #changed
    """Walk a parsed JSON object and apply character replacements            #changed
    to all string values in-place.                                           #changed

    Args:                                                                    #changed
        obj: Parsed JSON (dict, list, or primitive).                         #changed
        replacements: Dict of {char: (name, replacement)}.                   #changed
    """                                                                      #changed
    if isinstance(obj, dict):                                                #changed
        for key in list(obj.keys()):                                         #changed
            val = obj[key]                                                   #changed
            if isinstance(val, str):                                         #changed
                for char, (name, repl) in replacements.items():              #changed
                    val = val.replace(char, repl)                            #changed
                obj[key] = val                                               #changed
            else:                                                            #changed
                _fix_strings_recursive(val, replacements)                    #changed
    elif isinstance(obj, list):                                              #changed
        for i, item in enumerate(obj):                                       #changed
            if isinstance(item, str):                                        #changed
                for char, (name, repl) in replacements.items():              #changed
                    item = item.replace(char, repl)                          #changed
                obj[i] = item                                                #changed
            else:                                                            #changed
                _fix_strings_recursive(item, replacements)                   #changed


def scan_directory(dirpath, apply_fixes=False):
    """Scan all GT JSON files in a directory.

    Args:
        dirpath: Path to directory containing PMC*.json files.
        apply_fixes: If True, write corrected files back.

    Returns:
        List of scan result dictionaries.
    """
    all_results = []
    gt_files = sorted(dirpath.glob("PMC*.json"))

    if not gt_files:
        print(f"  [!] No PMC*.json files found in {dirpath}")
        return all_results

    for filepath in gt_files:
        result = scan_file(filepath, apply_fixes)
        all_results.append(result)

    return all_results


def print_report(results, label):
    """Print a formatted report of scan results."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    clean_count = 0
    issue_count = 0

    for r in results:
        if r.get('error'):
            print(f"\n  [ERROR] {r['pmcid']}: {r['error']}")
            issue_count += 1
            continue

        if r['total_issues'] == 0:
            clean_count += 1
            continue

        issue_count += 1
        fixed_tag = " [FIXED]" if r.get('fixed') else ""
        print(f"\n  {r['pmcid']}: {r['total_issues']} issues{fixed_tag}")

        if r['problematic']:
            for name, count in sorted(r['problematic'].items(), key=lambda x: -x[1]):
                print(f"    [INVISIBLE] {name}: {count}")

        if r['normalisable']:
            for name, count in sorted(r['normalisable'].items(), key=lambda x: -x[1]):
                print(f"    [NORMALISE] {name}: {count}")

        if r.get('fix_error'):
            print(f"    [FIX FAILED] {r['fix_error']}")

    print(f"\n  --- Summary ---")
    print(f"  Clean files: {clean_count}")
    print(f"  Files with issues: {issue_count}")
    print(f"  Total files scanned: {len(results)}")


def main():
    apply_fixes = "--apply" in sys.argv

    if apply_fixes:
        print("Running in FIX mode: problematic characters will be replaced.")
        print("JSON validity will be verified before writing.")
    else:
        print("Running in SCAN mode (read-only). Use --apply to fix issues.")

    # Scan GOLDEN_GT_PATH
    golden_results = []                                                      #changed
    if GOLDEN_GT_PATH.exists():
        golden_results = scan_directory(GOLDEN_GT_PATH, apply_fixes)
        print_report(golden_results, f"GOLDEN GT ({GOLDEN_GT_PATH})")
    else:
        print(f"\n  [!] Golden GT path not found: {GOLDEN_GT_PATH}")

    # Scan GROUND_TRUTH_PATH (excluding golden subdirectory)
    all_gt = []                                                              #changed
    if GROUND_TRUTH_PATH.exists():
        all_gt = scan_directory(GROUND_TRUTH_PATH, apply_fixes)
        print_report(all_gt, f"GROUND TRUTH ({GROUND_TRUTH_PATH})")
    else:
        print(f"\n  [!] Ground truth path not found: {GROUND_TRUTH_PATH}")

    # Overall summary
    total_files = len(golden_results) + len(all_gt)                          #changed

    print(f"\n{'='*70}")
    print(f"  Total files across both directories: {total_files}")
    if apply_fixes:
        print(f"  Mode: FIX (applied corrections)")
    else:
        print(f"  Mode: SCAN (read-only)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
