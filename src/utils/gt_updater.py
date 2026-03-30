#!/usr/bin/env python3
"""
gt_updater.py

Generalised ground truth updater. Applies the same operations as
update_gt_new89.py but against an arbitrary list of PMCIDs supplied
via a text file.

Operations:
  1. Strip 5 metadata fields from all isolate dicts     (always)
  2. Normalise Unicode dashes to ASCII hyphen-minus      (always)
  3. NO_ISOLATE_ID / multi-isolate merge fix             (only when --fix-ids supplied)

Usage:
  python gt_updater.py pmcids.txt                                # dry-run, clean ops only
  python gt_updater.py pmcids.txt --apply                        # apply clean ops
  python gt_updater.py pmcids.txt --fix-ids fixes.json           # dry-run, clean + ID fix
  python gt_updater.py pmcids.txt --fix-ids fixes.json --apply   # apply all
  python gt_updater.py pmcids.txt --gt-folder /other/path        # override GT folder

PMCID text file format (one per line, # comments and blanks ignored):
  PMC1234567
  PMC2345678
  # this line is skipped

Fix definitions JSON format (--fix-ids):
  {
    "single": {
      "PMC1234567": {
        "old_id": "Salmonella enterica serovar X",
        "ensure_field": "serotype",
        "ensure_value": "Salmonella X"
      }
    },
    "multi": {
      "PMC2345678": {
        "old_ids": ["ST100", "ST200"],
        "id_to_field_map": {
          "ST100": ["mlst", "ST100"],
          "ST200": ["mlst", "ST200"]
        }
      }
    }
  }

Referenced by: PMCID Action Register
Created: 15 March 2026
"""

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is on the import path so config and sibling modules are found
# ---------------------------------------------------------------------------
_SRC_DIR = str(Path(__file__).resolve().parent.parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from config import cfg

# ---------------------------------------------------------------------------
# Reuse core functions and constants from update_gt_new89
# ---------------------------------------------------------------------------
from utils.update_gt_new89 import (
    strip_metadata,
    normalise_dashes,
    content_hash,
    fix_single_isolate_id,
    fix_multi_isolate_ids,
    METADATA_FIELDS_TO_STRIP,
)


# ===================================================================
# PMCID LIST LOADER
# ===================================================================

def load_pmcid_list(filepath):
    """
    Read a text file containing one PMCID per line.

    Blank lines and lines starting with # are ignored.
    Leading/trailing whitespace is stripped.

    Parameters:
        filepath: str or Path -- path to the PMCID list file

    Returns:
        list of str -- PMCID strings
    """
    filepath = Path(filepath)

    if not filepath.is_file():
        print(f"ERROR: PMCID list file not found: {filepath}")
        sys.exit(1)

    pmcids = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()

            # Skip blanks and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Basic validation: should start with PMC followed by digits
            if not stripped.startswith("PMC"):
                print(
                    f"WARNING: Line {line_num} does not look like a PMCID: "
                    f"'{stripped}' -- skipping"
                )
                continue

            pmcids.append(stripped)

    if not pmcids:
        print(f"ERROR: No valid PMCIDs found in {filepath}")
        sys.exit(1)

    return pmcids


# ===================================================================
# FIX DEFINITIONS LOADER
# ===================================================================

def load_fix_definitions(filepath, pmcid_list):
    """
    Load and validate NO_ISOLATE_ID fix definitions from a JSON file.

    Parameters:
        filepath:   str or Path -- path to the fix definitions JSON
        pmcid_list: list of str -- PMCIDs that will be processed

    Returns:
        tuple of (single_fixes dict, multi_fixes dict)
    """
    filepath = Path(filepath)

    if not filepath.is_file():
        print(f"ERROR: Fix definitions file not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    single_fixes = raw.get("single", {})
    multi_fixes = raw.get("multi", {})

    # --- Validate single fix entries ---
    required_single_keys = {"old_id", "ensure_field", "ensure_value"}

    for pmcid, fix_def in single_fixes.items():
        missing = required_single_keys - set(fix_def.keys())
        if missing:
            print(
                f"ERROR: Single fix for {pmcid} is missing keys: "
                f"{', '.join(sorted(missing))}"
            )
            sys.exit(1)

    # --- Validate multi fix entries ---
    required_multi_keys = {"old_ids", "id_to_field_map"}

    for pmcid, fix_def in multi_fixes.items():
        missing = required_multi_keys - set(fix_def.keys())
        if missing:
            print(
                f"ERROR: Multi fix for {pmcid} is missing keys: "
                f"{', '.join(sorted(missing))}"
            )
            sys.exit(1)

    # --- Warn about fix definitions for PMCIDs not in the input list ---
    pmcid_set = set(pmcid_list)
    all_fix_pmcids = set(single_fixes.keys()) | set(multi_fixes.keys())
    orphaned = all_fix_pmcids - pmcid_set

    for pmcid in sorted(orphaned):
        print(
            f"WARNING: Fix definition for {pmcid} will be ignored "
            f"(not in PMCID list)"
        )

    return single_fixes, multi_fixes


# ===================================================================
# GT FILE FINDER
# ===================================================================

def find_gt_file(pmcid, search_paths):                              #changed
    """                                                              #changed
    Search a list of directories for PMCIDxxxxx.json.               #changed
                                                                     #changed
    Returns the first Path that exists, or None if not found in any #changed
    of the supplied directories.                                     #changed
                                                                     #changed
    Parameters:                                                      #changed
        pmcid:        str        -- e.g. "PMC1234567"                #changed
        search_paths: list[Path] -- ordered list of directories      #changed
                                                                     #changed
    Returns:                                                         #changed
        Path or None                                                 #changed
    """                                                              #changed
    filename = f"{pmcid}.json"                                       #changed
    for folder in search_paths:                                      #changed
        candidate = folder / filename                                #changed
        if candidate.exists():                                       #changed
            return candidate                                         #changed
    return None                                                      #changed


# ===================================================================
# MAIN
# ===================================================================

def main(pmcid_file, search_paths, fix_ids_file, dry_run):         #changed
    """
    Main entry point. Processes all PMCIDs from the supplied list.

    Parameters:
        pmcid_file:   str or Path  -- text file with one PMCID per line
        search_paths: list[Path]   -- ordered directories to search   #changed
                                      for PMCIDxxxxx.json files        #changed
        fix_ids_file: str, Path, or None -- optional fix definitions JSON
        dry_run:      bool -- if True, report without writing files
    """
    # --- Load PMCID list ---
    pmcid_list = load_pmcid_list(pmcid_file)

    # --- Validate all search paths ---                               #changed
    for folder in search_paths:                                      #changed
        if not folder.is_dir():                                      #changed
            print(f"ERROR: search path is not a valid directory: {folder}") #changed
            sys.exit(1)                                              #changed

    # --- Load fix definitions (if supplied) ---
    single_fixes = {}
    multi_fixes = {}

    if fix_ids_file is not None:
        single_fixes, multi_fixes = load_fix_definitions(
            fix_ids_file, pmcid_list
        )

    # --- Declare tracking variables ---
    change_log = []
    files_not_found = []
    files_unchanged = []
    total_metadata_stripped = 0
    total_unicode_fixed = 0
    total_manual_fixes = 0

    # --- Banner ---
    mode_label = "DRY RUN" if dry_run else "APPLYING CHANGES"
    fix_label = fix_ids_file if fix_ids_file else "none"

    print("=" * 70)
    print(f"GT UPDATER ({mode_label})")
    print("=" * 70)
    print(f"  PMCID list:      {pmcid_file}")
    for i, sp in enumerate(search_paths):                            #changed
        label = "Search path" if i > 0 else "Search path (1)"       #changed
        print(f"  {label:17s}: {sp}")                               #changed
    print(f"  Fix definitions: {fix_label}")
    print(f"  Records:         {len(pmcid_list)}")
    print()

    # --- Process each PMCID ---
    for pmcid in pmcid_list:
        filepath = find_gt_file(pmcid, search_paths)                #changed

        if filepath is None:                                         #changed
            files_not_found.append(pmcid)
            continue

        # Load GT
        with open(filepath, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        original_hash = content_hash(gt_data)
        changes_for_this_file = []

        # --- Operation 1: Strip metadata fields (always) ---
        file_stripped = 0

        for section_name in ["isolates_with_linking",
                             "isolate_without_linking"]:
            section = gt_data.get(section_name, [])
            if isinstance(section, list):
                for isolate in section:
                    if isinstance(isolate, dict):
                        file_stripped += strip_metadata(isolate)

        # Also strip from no_isolates_only_assayinformation if dict
        nioai = gt_data.get("no_isolates_only_assayinformation")
        if isinstance(nioai, dict):
            file_stripped += strip_metadata(nioai)

        if file_stripped > 0:
            changes_for_this_file.append(
                f"  Stripped {file_stripped} metadata field(s)"
            )
            total_metadata_stripped += 1

        # --- Operation 2: Unicode dash normalisation (always) ---
        pre_unicode_hash = content_hash(gt_data)
        gt_data = normalise_dashes(gt_data)
        post_unicode_hash = content_hash(gt_data)

        if pre_unicode_hash != post_unicode_hash:
            changes_for_this_file.append("  Unicode dashes normalised")
            total_unicode_fixed += 1

        # --- Operation 3: NO_ISOLATE_ID fix (only if --fix-ids) ---
        if pmcid in single_fixes:
            gt_data, fix_changes = fix_single_isolate_id(
                gt_data, single_fixes[pmcid]
            )
            changes_for_this_file.append(
                "  MANUAL_FIX (single isolate ID):"
            )
            changes_for_this_file.extend(fix_changes)
            total_manual_fixes += 1

        if pmcid in multi_fixes:
            gt_data, fix_changes = fix_multi_isolate_ids(
                gt_data, multi_fixes[pmcid]
            )
            changes_for_this_file.append(
                "  MANUAL_FIX (multi-isolate merge):"
            )
            changes_for_this_file.extend(fix_changes)
            total_manual_fixes += 1

        # --- Write or report ---
        new_hash = content_hash(gt_data)

        if new_hash != original_hash:
            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(gt_data, f, indent=2, ensure_ascii=False)
                    f.write("\n")  # trailing newline

            change_log.append({
                "pmcid": pmcid,
                "changes": changes_for_this_file,
                "written": not dry_run,
            })
        else:
            files_unchanged.append(pmcid)

    # --- Summary report ---
    print()
    print("-" * 70)
    print("RESULTS")
    print("-" * 70)
    print(f"  Files processed:     {len(pmcid_list)}")
    print(f"  Files changed:       {len(change_log)}")
    print(f"  Files unchanged:     {len(files_unchanged)}")
    print(f"  Files not found:     {len(files_not_found)}")
    print()
    print(f"  Metadata stripped:   {total_metadata_stripped} file(s)")
    print(f"  Unicode normalised:  {total_unicode_fixed} file(s)")
    print(f"  Manual ID fixes:     {total_manual_fixes} file(s)")
    print()

    # Per-file detail
    if change_log:
        print("-" * 70)
        print("PER-FILE CHANGES")
        print("-" * 70)
        for entry in change_log:
            status = "WRITTEN" if entry["written"] else "DRY RUN"
            print(f"\n{entry['pmcid']} [{status}]:")
            for change in entry["changes"]:
                print(f"  {change}")

    # Files not found
    if files_not_found:
        print()
        print("-" * 70)
        print(f"WARNING: {len(files_not_found)} file(s) not found:")
        print("-" * 70)
        for pmcid in files_not_found:
            print(f"  {pmcid}.json")

    # --- Audit trail ---
    if not dry_run and change_log:
        log_path = search_paths[0] / "gt_update_changelog.json"  #changed
        log_data = {
            "script": "gt_updater.py",
            "source_file": str(pmcid_file),
            "fix_definitions": str(fix_ids_file) if fix_ids_file else None,
            "mode": "applied",
            "total_processed": len(pmcid_list),
            "total_changed": len(change_log),
            "total_not_found": len(files_not_found),
            "not_found": files_not_found,
            "metadata_stripped_count": total_metadata_stripped,
            "unicode_normalised_count": total_unicode_fixed,
            "manual_fix_count": total_manual_fixes,
            "changes": change_log,
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print()
        print(f"  Change log saved to: {log_path}")

    print()
    print("=" * 70)
    if dry_run:
        print("DRY RUN COMPLETE. No files were modified.")
        print("Re-run with --apply to write changes.")
    else:
        print("CHANGES APPLIED SUCCESSFULLY.")
    print("=" * 70)

    return change_log


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generalised GT updater. Strips metadata fields, normalises "
            "Unicode dashes, and optionally fixes isolate IDs using "
            "definitions from an external JSON file."
        )
    )
    parser.add_argument(
        "pmcid_file",
        help="Path to text file containing PMCIDs (one per line)",
    )
    parser.add_argument(
        "--gt-folder",
        default=None,
        help=(                                                        #changed
            "Override: search only this folder instead of the default "  #changed
            "three-path search (GROUND_TRUTH_PATH, GOLDEN_GT_PATH, "     #changed
            "SUPP_GOLDEN_GT_PATH)."                                       #changed
        ),                                                            #changed
    )
    parser.add_argument(
        "--fix-ids",
        default=None,
        metavar="FILE",
        help=(
            "Path to JSON file with NO_ISOLATE_ID fix definitions. "
            "If omitted, only metadata stripping and Unicode normalisation "
            "are performed."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply changes to files (default is dry-run)",
    )

    args = parser.parse_args()

    # Build ordered search path list                              #changed
    if args.gt_folder is not None:                                   #changed
        search_paths = [Path(args.gt_folder)]                        #changed
    else:                                                            #changed
        search_paths = [                                             #changed
            Path(cfg.GROUND_TRUTH_PATH),                             #changed
            Path(cfg.GOLDEN_GT_PATH),                                #changed
            Path(cfg.SUPP_GOLDEN_GT_PATH),                           #changed
        ]                                                            #changed

    main(
        pmcid_file=args.pmcid_file,
        search_paths=search_paths,                                   #changed
        fix_ids_file=args.fix_ids,
        dry_run=not args.apply,
    )
