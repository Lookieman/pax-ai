#!/usr/bin/env python3
"""
update_gt_new89.py

Updates ground truth JSON files for the new 89 diagnostic set.
Three operations:
  1. Strip 5 metadata fields from all isolate dicts
  2. Normalise Unicode dashes to ASCII hyphen-minus
  3. MANUAL_FIX: Change 7 records where serotype/MLST names were used as isolate IDs

Usage:
  python update_gt_new89.py /path/to/ground_truth              # dry-run (default)
  python update_gt_new89.py /path/to/ground_truth --apply       # apply changes

Referenced by: PMCID Action Register, DD-2026-008
Created: 8 March 2026
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


# ===================================================================
# CONSTANTS
# ===================================================================

METADATA_FIELDS_TO_STRIP = [
    "isolate_country",
    "isolate_date",
    "isolate_source",
    "location",
    "location_offical_name",
]

UNICODE_DASH_MAP = {
    "\u2013": "-",  # en-dash
    "\u2014": "-",  # em-dash
    "\u2012": "-",  # figure dash
}

# All 89 PMCIDs in the new diagnostic set
NEW_89_PMCIDS = [
    "PMC4748464", "PMC4866840", "PMC4939201", "PMC4944992", "PMC4957272",
    "PMC4994947", "PMC5073282", "PMC5075293", "PMC5094244", "PMC5145817",
    "PMC5388333", "PMC5671994", "PMC5797408", "PMC5797457", "PMC5798080",
    "PMC5832104", "PMC5887036", "PMC5985583", "PMC6029346", "PMC6230761",
    "PMC6307136", "PMC6357384", "PMC6378779", "PMC6392897", "PMC6430326",
    "PMC6486240", "PMC6639624", "PMC6667484", "PMC6715874", "PMC6744686",
    "PMC6925778", "PMC6935380", "PMC6952724", "PMC6986767", "PMC7011100",
    "PMC7083181", "PMC7083327", "PMC7098901", "PMC7291093", "PMC7310241",
    "PMC7385254", "PMC7425045", "PMC7460271", "PMC7478631", "PMC7497748",
    "PMC7581672", "PMC7587706", "PMC7603275", "PMC7656189", "PMC7696838",
    "PMC7748489", "PMC7764154", "PMC7766374", "PMC7767027", "PMC7909088",
    "PMC8000398", "PMC8018540", "PMC8021795", "PMC8082823", "PMC8145149",
    "PMC8512087", "PMC8698551", "PMC8784875", "PMC8899097", "PMC8913728",
    "PMC8944838", "PMC8951033", "PMC8953408", "PMC9002014", "PMC9035464",
    "PMC9137667", "PMC9146225", "PMC9148033", "PMC9190773", "PMC9216381",
    "PMC9219668", "PMC9220226", "PMC9221781", "PMC9247517", "PMC9323645",
    "PMC9353134", "PMC9409446", "PMC9431532", "PMC9610186", "PMC9670943",
    "PMC9693821", "PMC9708683", "PMC9739812", "PMC9769515",
]

# 5 single-isolate records: GT uses serotype name as isolate_id
# Fix: rename isolate_id to NO_ISOLATE_ID, ensure serotype field has value
#
# IMPORTANT: verify ensure_value against actual GT files before running.
# The ensure_value is only written if the field is currently empty.
MANUAL_FIX_SINGLE = {
    "PMC4939201": {
        "old_id": "Salmonella enterica subsp. enterica serovar Abony",
        "ensure_field": "serotype",
        "ensure_value": "Salmonella enterica serovar Abony",
    },
    "PMC6392897": {
        "old_id": "S. Potsdam",
        "ensure_field": "serotype",
        "ensure_value": "Salmonella Potsdam",
    },
    "PMC6667484": {
        "old_id": "Salmonella species IIIa (51:Z4,Z23)",
        "ensure_field": "serotype",
        "ensure_value": "IIIa (51:Z4,Z23)",
    },
    "PMC6952724": {
        "old_id": "Salmonella typhimurium",
        "ensure_field": "serotype",
        "ensure_value": "Salmonella typhimurium",
    },
    "PMC9221781": {
        "old_id": "Salmonella species Saintpaul",
        "ensure_field": "serotype",
        "ensure_value": "Saintpaul",
    },
}

# 2 multi-isolate records: GT uses MLST/PFGE types as isolate_ids
# Fix: merge all isolates into no_isolates_only_assayinformation
MANUAL_FIX_MULTI = {
    "PMC7587706": {
        "old_ids": ["ST2039", "PF29"],
        "id_to_field_map": {
            "ST2039": ("mlst", "ST2039"),
            "PF29": ("pfge", "PF29"),
        },
    },
    "PMC9137667": {
        "old_ids": ["ST10", "ST19"],
        "id_to_field_map": {
            "ST10": ("mlst", "ST10"),
            "ST19": ("mlst", "ST19"),
        },
    },
}


# ===================================================================
# OPERATION 1: Strip metadata fields
# ===================================================================

def strip_metadata(isolate_dict):
    """
    Remove the 5 metadata fields from a single isolate dictionary.

    Parameters:
        isolate_dict: dict -- a single isolate record

    Returns:
        int -- count of fields actually removed
    """
    removed_count = 0

    for field in METADATA_FIELDS_TO_STRIP:
        if field in isolate_dict:
            del isolate_dict[field]
            removed_count += 1

    return removed_count


# ===================================================================
# OPERATION 2: Unicode dash normalisation
# ===================================================================

def normalise_dashes(obj):
    """
    Recursively walk any JSON-compatible object and replace
    Unicode dashes with ASCII hyphen-minus in all string values
    and keys.

    Parameters:
        obj: any JSON-compatible type

    Returns:
        normalised copy of the object
    """
    if isinstance(obj, str):
        result = obj
        for unicode_char, replacement in UNICODE_DASH_MAP.items():
            result = result.replace(unicode_char, replacement)
        return result

    elif isinstance(obj, list):
        return [normalise_dashes(item) for item in obj]

    elif isinstance(obj, dict):
        return {
            normalise_dashes(key): normalise_dashes(value)
            for key, value in obj.items()
        }

    else:
        # numbers, booleans, None pass through unchanged
        return obj


# ===================================================================
# OPERATION 3a: MANUAL_FIX for single-isolate records
# ===================================================================

def fix_single_isolate_id(gt_data, fix_config):
    """
    For records where GT has 1 isolate using serotype/MLST as ID:
    - Change isolate_id to NO_ISOLATE_ID
    - Ensure the serotype/MLST value is preserved in the correct
      assay field (only if the field is currently empty)

    Parameters:
        gt_data:    dict -- full GT JSON content
        fix_config: dict -- {old_id, ensure_field, ensure_value}

    Returns:
        tuple of (gt_data, list of change descriptions)
    """
    old_id = fix_config["old_id"]
    ensure_field = fix_config["ensure_field"]
    ensure_value = fix_config["ensure_value"]
    changes = []

    for section_name in ["isolates_with_linking", "isolate_without_linking"]:
        section = gt_data.get(section_name, [])
        if not isinstance(section, list):
            continue

        for isolate in section:
            if not isinstance(isolate, dict):
                continue

            if isolate.get("isolate_id") == old_id:
                # Change the ID
                isolate["isolate_id"] = "NO_ISOLATE_ID"  #changed

                # Ensure assay field has value (only if empty/missing)
                current_value = isolate.get(ensure_field)
                field_is_empty = (
                    current_value is None
                    or current_value == []
                    or current_value == ""
                    or current_value == "null"
                    or (isinstance(current_value, list)
                        and len(current_value) == 0)
                )
                if field_is_empty:
                    isolate[ensure_field] = [ensure_value]  #changed
                    changes.append(
                        f"    Added {ensure_field}=['{ensure_value}'] "
                        f"(field was empty)"
                    )
                else:
                    changes.append(
                        f"    {ensure_field} already has value: "
                        f"{str(current_value)[:80]}"
                    )

                changes.insert(0,
                    f"    isolate_id: '{old_id}' -> 'NO_ISOLATE_ID' "
                    f"(in {section_name})"
                )

    return gt_data, changes


# ===================================================================
# OPERATION 3b: MANUAL_FIX for multi-isolate records
# ===================================================================

def merge_values(existing, new):
    """
    Merge two values of the same assay field.
    Lists: extend with deduplication.
    Dicts: update.
    Scalars: combine into list.

    Parameters:
        existing: current value in merged dict
        new:      value to merge in

    Returns:
        merged value
    """
    if isinstance(existing, list) and isinstance(new, list):
        combined = list(existing)
        for item in new:
            if item not in combined:
                combined.append(item)
        return combined

    elif isinstance(existing, dict) and isinstance(new, dict):
        merged = dict(existing)
        merged.update(new)
        return merged

    else:
        # Wrap scalars into a list
        result = []
        for val in [existing, new]:
            if isinstance(val, list):
                result.extend(val)
            else:
                result.append(val)
        return result


def fix_multi_isolate_ids(gt_data, fix_config):
    """
    For records with multiple isolates ALL using MLST/PFGE as IDs:
    - Merge all isolate assay data into no_isolates_only_assayinformation
    - Ensure MLST/PFGE values are stored as assay fields
    - Remove processed isolates from isolates_with_linking

    Parameters:
        gt_data:    dict -- full GT JSON content
        fix_config: dict -- {old_ids, id_to_field_map}

    Returns:
        tuple of (gt_data, list of change descriptions)
    """
    old_ids = set(fix_config["old_ids"])
    id_to_field_map = fix_config["id_to_field_map"]
    changes = []

    section = gt_data.get("isolates_with_linking", [])
    if not isinstance(section, list):
        return gt_data, ["    WARNING: isolates_with_linking is not a list"]

    # Collect assay data from matching isolates
    merged_assays = {}
    indices_to_remove = []

    for index, isolate in enumerate(section):
        if not isinstance(isolate, dict):
            continue

        iso_id = isolate.get("isolate_id", "")
        if iso_id not in old_ids:
            continue

        indices_to_remove.append(index)

        # Ensure the MLST/PFGE value is stored as an assay field
        if iso_id in id_to_field_map:
            field_name, field_value = id_to_field_map[iso_id]
            current = isolate.get(field_name, [])
            if isinstance(current, list):
                if field_value not in current:
                    current.append(field_value)
                    isolate[field_name] = current  #changed
            else:
                isolate[field_name] = [field_value]  #changed

        # Merge assay fields into combined dict
        for key, value in isolate.items():
            if key == "isolate_id":
                continue
            if key in METADATA_FIELDS_TO_STRIP:
                continue  # already stripped by Operation 1

            # Skip empty values
            is_empty = (
                value is None
                or value == []
                or value == {}
                or value == ""
                or value == "null"
            )
            if is_empty:
                continue

            if key not in merged_assays:
                merged_assays[key] = value
            else:
                merged_assays[key] = merge_values(
                    merged_assays[key], value
                )

    # Remove processed isolates (reverse order to preserve indices)
    for index in sorted(indices_to_remove, reverse=True):
        removed_iso = section[index].get("isolate_id", "?")
        section.pop(index)  #changed
        changes.append(
            f"    Removed isolate '{removed_iso}' "
            f"from isolates_with_linking"
        )

    # Store merged data in no_isolates_only_assayinformation
    if merged_assays:
        gt_data["no_isolates_only_assayinformation"] = merged_assays  #changed
        assay_keys = sorted(merged_assays.keys())
        changes.append(
            f"    Merged {len(indices_to_remove)} isolate(s) into "
            f"no_isolates_only_assayinformation "
            f"(fields: {', '.join(assay_keys)})"
        )

    return gt_data, changes


# ===================================================================
# UTILITY: compute content hash for change detection
# ===================================================================

def content_hash(data):
    """
    Compute a deterministic hash of JSON-serialisable data.
    Used to detect whether operations actually changed anything.
    """
    serialised = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


# ===================================================================
# MAIN
# ===================================================================

def main(gt_folder_path, dry_run=True):
    """
    Main entry point. Processes all 89 GT files.

    Parameters:
        gt_folder_path: str or Path -- folder containing PMCxxxxxxx.json
        dry_run:        bool -- if True, report without writing files
    """
    gt_folder = Path(gt_folder_path)

    if not gt_folder.is_dir():
        print(f"ERROR: '{gt_folder}' is not a valid directory.")
        sys.exit(1)

    # Declare tracking variables
    change_log = []
    files_not_found = []
    files_unchanged = []
    total_metadata_stripped = 0
    total_unicode_fixed = 0
    total_manual_fixes = 0

    mode_label = "DRY RUN" if dry_run else "APPLYING CHANGES"
    print("=" * 70)
    print(f"GT UPDATE SCRIPT - NEW 89 DIAGNOSTIC SET ({mode_label})")
    print("=" * 70)
    print(f"GT folder: {gt_folder}")
    print(f"Records to process: {len(NEW_89_PMCIDS)}")
    print()

    for pmcid in NEW_89_PMCIDS:
        filepath = gt_folder / f"{pmcid}.json"

        if not filepath.exists():
            files_not_found.append(pmcid)
            continue

        # Load GT
        with open(filepath, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        original_hash = content_hash(gt_data)
        changes_for_this_file = []

        # --- Operation 1: Strip metadata fields ---
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

        # --- Operation 2: Unicode dash normalisation ---
        pre_unicode_hash = content_hash(gt_data)
        gt_data = normalise_dashes(gt_data)
        post_unicode_hash = content_hash(gt_data)

        if pre_unicode_hash != post_unicode_hash:
            changes_for_this_file.append("  Unicode dashes normalised")
            total_unicode_fixed += 1

        # --- Operation 3: MANUAL_FIX (only 7 target PMCIDs) ---
        if pmcid in MANUAL_FIX_SINGLE:
            gt_data, fix_changes = fix_single_isolate_id(
                gt_data, MANUAL_FIX_SINGLE[pmcid]
            )
            changes_for_this_file.append(
                "  MANUAL_FIX (single isolate ID):"
            )
            changes_for_this_file.extend(fix_changes)
            total_manual_fixes += 1

        if pmcid in MANUAL_FIX_MULTI:
            gt_data, fix_changes = fix_multi_isolate_ids(
                gt_data, MANUAL_FIX_MULTI[pmcid]
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

    # --- Print summary report ---
    print()
    print("-" * 70)
    print("RESULTS")
    print("-" * 70)
    print(f"Files processed:     {len(NEW_89_PMCIDS)}")
    print(f"Files changed:       {len(change_log)}")
    print(f"Files unchanged:     {len(files_unchanged)}")
    print(f"Files not found:     {len(files_not_found)}")
    print()
    print(f"Metadata stripped:   {total_metadata_stripped} file(s)")
    print(f"Unicode normalised:  {total_unicode_fixed} file(s)")
    print(f"Manual ID fixes:     {total_manual_fixes} file(s)")
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

    # Save change log as JSON for audit trail
    if not dry_run and change_log:
        log_path = gt_folder / "gt_update_changelog_new89.json"
        log_data = {
            "script": "update_gt_new89.py",
            "date": "2026-03-08",
            "mode": "applied",
            "total_processed": len(NEW_89_PMCIDS),
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
        print(f"Change log saved to: {log_path}")

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
            "Update GT files for new 89 diagnostic set. "
            "Strips metadata fields, normalises Unicode dashes, "
            "and fixes 7 records where serotype/MLST names were "
            "used as isolate IDs."
        )
    )
    parser.add_argument(
        "gt_folder",
        help="Path to folder containing PMCxxxxxxx.json ground truth files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply changes to files (default is dry-run)",
    )

    args = parser.parse_args()

    main(
        gt_folder_path=args.gt_folder,
        dry_run=not args.apply,
    )
