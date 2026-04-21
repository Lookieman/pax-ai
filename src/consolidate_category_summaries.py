"""
consolidate_category_summaries.py

Scans the gt_diagnostic_analysis output folder recursively for all
*category_summary.json files (baseline and GEPA runs), flattens the
nested category metrics, and consolidates them into:
  1. A single JSON file (list of run summaries)
  2. A single CSV file (one row per run, flattened columns)

Usage:
    python consolidate_category_summaries.py
    python consolidate_category_summaries.py --root "D:\\other\\path"
    python consolidate_category_summaries.py --root "D:\\other\\path" --output "D:\\output\\path"

Output files are written to the root directory by default:
    consolidated_category_summaries.json
    consolidated_category_summaries.csv
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime


# ------------------------------------------------------------------ #
# Configuration
# ------------------------------------------------------------------ #

DEFAULT_ROOT = r"C:\proj\pax-ai-working\assay\gt_diagnostic_analysis"
SUMMARY_PATTERN = "category_summary.json"
OUTPUT_PREFIX = "consolidated_category_summaries"


# ------------------------------------------------------------------ #
# Helper functions
# ------------------------------------------------------------------ #

def find_summary_files(root_dir):
    """Walk root_dir recursively and return list of paths matching
    *category_summary.json (case-insensitive on filename)."""

    found_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            filename_lower = filename.lower()
            if filename_lower.endswith(SUMMARY_PATTERN.lower()):
                full_path = os.path.join(dirpath, filename)
                found_files.append(full_path)

    # Sort by folder depth then alphabetically for deterministic order
    found_files.sort(key=lambda p: (p.count(os.sep), p.lower()))

    return found_files


def derive_run_name(file_path, root_dir):
    """Derive a human-readable run name from the file's relative path.

    Example:
        root_dir  = C:\\proj\\...\\gt_diagnostic_analysis
        file_path = C:\\proj\\...\\gt_diagnostic_analysis\\v4_baseline\\v4_category_summary.json
        run_name  = v4_baseline

    If the file is nested deeper (e.g. gepa_logs/productive_a/...):
        run_name  = gepa_logs/productive_a
    """

    rel_path = os.path.relpath(file_path, root_dir)
    # Remove the filename itself; keep only the folder part
    folder_part = os.path.dirname(rel_path)

    if not folder_part or folder_part == ".":
        # File is directly in root_dir
        folder_part = os.path.splitext(os.path.basename(file_path))[0]

    # Normalise path separators to forward slash for readability
    run_name = folder_part.replace(os.sep, "/")

    return run_name


def flatten_dict(nested_dict, parent_key="", separator="_"):
    """Recursively flatten a nested dict into dot/underscore-separated keys.

    Example:
        {"iwl": {"tp": 10, "fp": 2}} --> {"iwl_tp": 10, "iwl_fp": 2}
    """

    flat_items = []

    for key, value in nested_dict.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else str(key)

        if isinstance(value, dict):
            flat_items.extend(
                flatten_dict(value, parent_key=new_key, separator=separator).items()
            )
        elif isinstance(value, list):
            # Store lists as JSON strings so CSV can hold them
            flat_items.append((new_key, json.dumps(value)))
        else:
            flat_items.append((new_key, value))

    return dict(flat_items)


def load_and_flatten(file_path, root_dir):
    """Load a category_summary.json, flatten it, and add metadata columns."""

    run_name = derive_run_name(file_path, root_dir)

    with open(file_path, "r", encoding="utf-8") as fh:
        raw_data = json.load(fh)

    # Flatten the entire JSON structure
    flat_data = flatten_dict(raw_data)

    # Prepend metadata columns
    metadata = {
        "run_name": run_name,
        "source_file": os.path.relpath(file_path, root_dir),
        "file_modified": datetime.fromtimestamp(
            os.path.getmtime(file_path)
        ).strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Metadata first, then flattened metrics
    row = {}
    row.update(metadata)
    row.update(flat_data)

    return row


def collect_all_columns(rows):
    """Return an ordered list of all unique column names across all rows.
    Metadata columns come first, then metric columns sorted alphabetically."""

    metadata_cols = ["run_name", "source_file", "file_modified"]
    metric_cols = set()

    for row in rows:
        for key in row.keys():
            if key not in metadata_cols:
                metric_cols.add(key)

    # Sort metric columns for consistent ordering
    ordered_cols = metadata_cols + sorted(metric_cols)

    return ordered_cols


def write_json_output(rows, output_path):
    """Write consolidated rows to a JSON file."""

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)

    print(f"  JSON written: {output_path}")


def write_csv_output(rows, output_path):
    """Write consolidated rows to a CSV file with all columns."""

    all_columns = collect_all_columns(rows)

    with open(output_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"  CSV  written: {output_path}")


def print_console_summary(rows, summary_files):
    """Print a brief summary table to console."""

    print("\n" + "=" * 72)
    print(f"  Consolidated {len(rows)} category summary file(s)")
    print("=" * 72)

    # Print each run name and its source
    for i, row in enumerate(rows, start=1):
        print(f"  {i}. {row['run_name']}")
        print(f"     Source: {row['source_file']}")
        print(f"     Modified: {row['file_modified']}")

    print("-" * 72)


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Consolidate category_summary.json files from diagnostic output folders."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=DEFAULT_ROOT,
        help=f"Root directory to scan (default: {DEFAULT_ROOT})"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for consolidated files (default: same as root)"
    )

    args = parser.parse_args()
    root_dir = args.root
    output_dir = args.output if args.output else root_dir

    # Validate root exists
    if not os.path.isdir(root_dir):
        print(f"ERROR: Root directory does not exist: {root_dir}")
        sys.exit(1)

    # Create output directory if needed
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"  Created output directory: {output_dir}")

    # Step 1: Find all category_summary.json files
    print(f"\nScanning: {root_dir}")
    summary_files = find_summary_files(root_dir)

    if not summary_files:
        print(f"  No files matching *{SUMMARY_PATTERN} found.")
        sys.exit(0)

    print(f"  Found {len(summary_files)} file(s)")

    # Step 2: Load and flatten each file
    rows = []
    errors = []

    for file_path in summary_files:
        try:
            row = load_and_flatten(file_path, root_dir)
            rows.append(row)
        except (json.JSONDecodeError, OSError) as err:
            error_msg = f"  WARNING: Skipping {file_path} -- {err}"
            print(error_msg)
            errors.append(error_msg)

    if not rows:
        print("  No valid files to consolidate after processing.")
        sys.exit(0)

    # Step 3: Write outputs
    json_path = os.path.join(output_dir, f"{OUTPUT_PREFIX}.json")
    csv_path = os.path.join(output_dir, f"{OUTPUT_PREFIX}.csv")

    write_json_output(rows, json_path)
    write_csv_output(rows, csv_path)

    # Step 4: Console summary
    print_console_summary(rows, summary_files)

    if errors:
        print(f"\n  {len(errors)} file(s) skipped due to errors.")

    print("  Done.\n")


if __name__ == "__main__":
    main()
