"""
V4 Baseline Troubleshoot File Organiser
=======================================
Copies GT JSON, extracted JSON, and article XML files into pattern-specific
subfolders under the troubleshoot directory for targeted analysis.

Three failure patterns identified from the v4 baseline run:
  Pattern 1 - Category mismatch IWL->NIOAI (20 records)
  Pattern 2 - Category mismatch IWL->IWOL  (11 records)
  Pattern 3 - Same category IWL->IWL, zero TP (6 records)

Additionally copies golden GT JSON + XML for the 22 evaluable golden
holdout records, excluding any that already appear in Patterns 1-3.

Usage:
  python v4_troubleshoot_organiser.py                  # dry-run
  python v4_troubleshoot_organiser.py --apply           # execute copies

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
"""

import os
import sys
import csv
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Config import (same pattern as other project scripts)
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import cfg


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# v4 baseline output locations
V4_BASELINE_DIR = os.path.join(
    cfg.DRIVE_BASE, "assay", "gt_diagnostic_analysis", "v4_baseline"
)
EXTRACTION_DIR = os.path.join(V4_BASELINE_DIR, "raw_extractions")
RESULTS_CSV = os.path.join(V4_BASELINE_DIR, "v4_baseline_per_record_results.csv")

# Troubleshoot output directory
TROUBLESHOOT_DIR = os.path.join(V4_BASELINE_DIR, "troubleshoot")

# Source directories (from config.py singleton)
GT_DIR = cfg.GROUND_TRUTH_PATH
GOLDEN_GT_DIR = cfg.GOLDEN_GT_PATH
XML_DIR = cfg.XML_PATH

# Pattern subfolder names
PATTERN_FOLDERS = ["Pattern_1", "Pattern_2", "Pattern_3", "golden"]

# Golden holdout PMCIDs (20 evaluable golden records for article extraction)
GOLDEN_HOLDOUT_PMCIDS = [
    "PMC1278947",
    "PMC2694269",
    "PMC2725854",
    "PMC2873750",
    "PMC2874370",
    "PMC2958529",
    "PMC3020606",
    "PMC5074519",
    "PMC5739443",
    "PMC4892500",
    "PMC4932652",
    "PMC7598458",
    "PMC7783345",
    "PMC9641423",
    "PMC9643863",
    "PMC7273606",
    "PMC2409344",
    "PMC4881965",
    "PMC5033494",
    "PMC6667439",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def classify_patterns(csv_path):
    """
    Read the v4 baseline per-record results CSV and classify records
    into the three failure patterns.

    Pattern 1: gt_category=IWL, ext_category=NIOAI
    Pattern 2: gt_category=IWL, ext_category=IWOL
    Pattern 3: gt_category=IWL, ext_category=IWL, tp=0

    Returns:
        dict with keys "Pattern_1", "Pattern_2", "Pattern_3",
        each mapping to a list of dicts with PMCID and metrics.
    """
    patterns = {
        "Pattern_1": [],
        "Pattern_2": [],
        "Pattern_3": [],
    }

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pmcid = row["pmcid"]
            gt_cat = row["gt_category"].strip()
            ext_cat = row["ext_category"].strip()
            tp = int(row["tp"]) if row["tp"] else 0
            fp = int(row["fp"]) if row["fp"] else 0
            fn = int(row["fn"]) if row["fn"] else 0
            f1 = row.get("primary_f1", "0.0")
            gt_items = row.get("gt_item_count", "0")
            ext_items = row.get("ext_item_count", "0")

            record_info = {
                "pmcid": pmcid,
                "gt_category": gt_cat,
                "ext_category": ext_cat,
                "primary_f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "gt_item_count": gt_items,
                "ext_item_count": ext_items,
            }

            if gt_cat == "IWL" and ext_cat == "NIOAI":
                patterns["Pattern_1"].append(record_info)
            elif gt_cat == "IWL" and ext_cat == "IWOL":
                patterns["Pattern_2"].append(record_info)
            elif gt_cat == "IWL" and ext_cat == "IWL" and tp == 0:
                patterns["Pattern_3"].append(record_info)

    return patterns


def find_gt_file(pmcid, gt_dir, golden_gt_dir):
    """
    Locate the GT JSON file for a given PMCID.
    Checks the main GT directory first, then the golden subdirectory.

    Returns:
        Path object if found, None otherwise.
    """
    # Check main GT directory
    main_path = Path(gt_dir) / f"{pmcid}.json"
    if main_path.exists():
        return main_path

    # Check golden GT directory
    golden_path = Path(golden_gt_dir) / f"{pmcid}.json"
    if golden_path.exists():
        return golden_path

    return None


def find_extraction_file(pmcid, ext_dir):
    """
    Locate the extracted JSON file for a given PMCID.

    Returns:
        Path object if found, None otherwise.
    """
    ext_path = Path(ext_dir) / f"{pmcid}_extraction.json"           #changed
    if ext_path.exists():
        return ext_path
    return None


def find_xml_file(pmcid, xml_dir):
    """
    Locate the article XML file for a given PMCID.
    Handles date-appended filenames (e.g. PMC1278947_20260315.xml).

    Returns:
        Path object if found, None otherwise.
    """
    xml_dir_path = Path(xml_dir)                                   #changed

    # Try exact match first                                        #changed
    exact_path = xml_dir_path / f"{pmcid}.xml"                     #changed
    if exact_path.exists():                                        #changed
        return exact_path                                          #changed

    # Try glob pattern for date-appended filenames                 #changed
    matches = sorted(xml_dir_path.glob(f"{pmcid}*.xml"))           #changed
    if matches:                                                    #changed
        return matches[-1]  # most recent if multiple              #changed

    return None


def copy_file(src, dest, dry_run):
    """
    Copy a file from src to dest. In dry-run mode, only log the action.

    Returns:
        True if copy was successful (or would be in dry-run), False otherwise.
    """
    if dry_run:
        logger.info("  [DRY RUN] Would copy: %s -> %s", src, dest)
        return True
    try:
        shutil.copy2(src, dest)
        logger.info("  Copied: %s -> %s", src, dest)
        return True
    except (OSError, shutil.Error) as e:
        logger.error("  FAILED to copy %s: %s", src, e)
        return False


def write_manifest(folder_path, records, include_ext, dry_run):
    """
    Write a manifest CSV summarising the records in this pattern folder.

    Args:
        folder_path:  destination folder for the manifest
        records:      list of dicts with PMCID and metrics
        include_ext:  whether to include extraction file columns
        dry_run:      if True, only log
    """
    manifest_path = Path(folder_path) / "manifest.csv"

    if include_ext:
        headers = [
            "pmcid", "gt_category", "ext_category", "primary_f1",
            "tp", "fp", "fn", "gt_item_count", "ext_item_count",
            "gt_found", "ext_found", "xml_found",
        ]
    else:
        headers = [
            "pmcid", "gt_found", "xml_found",
        ]

    if dry_run:
        logger.info("  [DRY RUN] Would write manifest: %s (%d records)",
                     manifest_path, len(records))
        return

    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

    logger.info("  Wrote manifest: %s (%d records)", manifest_path, len(records))


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def run(dry_run):
    """
    Main execution function.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_label = "DRY RUN" if dry_run else "APPLY"
    logger.info("=" * 70)
    logger.info("V4 Troubleshoot File Organiser [%s] - %s", mode_label, timestamp)
    logger.info("=" * 70)

    # --- 1. Validate source paths ---
    logger.info("Validating source paths...")
    paths_ok = True
    for label, path in [
        ("GT directory", GT_DIR),
        ("Golden GT directory", GOLDEN_GT_DIR),
        ("XML directory", XML_DIR),
        ("Extraction directory", EXTRACTION_DIR),
        ("Results CSV", RESULTS_CSV),
    ]:
        exists = os.path.exists(path)
        status = "OK" if exists else "MISSING"
        logger.info("  %-25s: %s [%s]", label, path, status)
        if not exists:
            paths_ok = False

    if not paths_ok:
        logger.error("One or more source paths are missing. Aborting.")
        sys.exit(1)

    # --- 2. Create output folder structure ---
    logger.info("Creating output folder structure...")
    for folder in PATTERN_FOLDERS:
        folder_path = os.path.join(TROUBLESHOOT_DIR, folder)
        if not dry_run:
            os.makedirs(folder_path, exist_ok=True)
        logger.info("  %s", folder_path)

    # --- 3. Classify records from v4 results CSV ---
    logger.info("Classifying records from v4 baseline results...")
    patterns = classify_patterns(RESULTS_CSV)
    for pattern_name, records in patterns.items():
        logger.info("  %s: %d records", pattern_name, len(records))

    # --- 4. Collect all pattern PMCIDs (for golden exclusion) ---
    all_pattern_pmcids = set()
    for records in patterns.values():
        for rec in records:
            all_pattern_pmcids.add(rec["pmcid"])

    # --- 5. Copy files for Patterns 1-3 ---
    copy_summary = {}

    for pattern_name, records in patterns.items():
        logger.info("-" * 50)
        logger.info("Processing %s (%d records)...", pattern_name, len(records))
        dest = os.path.join(TROUBLESHOOT_DIR, pattern_name)
        copied = 0
        missing_gt = 0
        missing_ext = 0
        missing_xml = 0

        for rec in records:
            pmcid = rec["pmcid"]
            logger.info("  %s:", pmcid)

            # a) GT JSON
            gt_src = find_gt_file(pmcid, GT_DIR, GOLDEN_GT_DIR)
            if gt_src:
                gt_dest = os.path.join(dest, f"{pmcid}_gt.json")
                copy_file(gt_src, gt_dest, dry_run)
                rec["gt_found"] = "yes"
            else:
                logger.warning("    GT not found for %s", pmcid)
                rec["gt_found"] = "no"
                missing_gt += 1

            # b) Extracted JSON
            ext_src = find_extraction_file(pmcid, EXTRACTION_DIR)
            if ext_src:
                ext_dest = os.path.join(dest, f"{pmcid}_ext.json")
                copy_file(ext_src, ext_dest, dry_run)
                rec["ext_found"] = "yes"
            else:
                logger.warning("    Extraction not found for %s", pmcid)
                rec["ext_found"] = "no"
                missing_ext += 1

            # c) Article XML
            xml_src = find_xml_file(pmcid, XML_DIR)
            if xml_src:
                xml_dest = os.path.join(dest, f"{pmcid}.xml")
                copy_file(xml_src, xml_dest, dry_run)
                rec["xml_found"] = "yes"
            else:
                logger.warning("    XML not found for %s", pmcid)
                rec["xml_found"] = "no"
                missing_xml += 1

            copied += 1

        # Write manifest for this pattern
        write_manifest(dest, records, include_ext=True, dry_run=dry_run)

        copy_summary[pattern_name] = {
            "total": len(records),
            "missing_gt": missing_gt,
            "missing_ext": missing_ext,
            "missing_xml": missing_xml,
        }

    # --- 6. Copy files for golden subfolder ---
    logger.info("-" * 50)

    # Exclude golden PMCIDs that already appear in a pattern folder
    golden_in_patterns = [
        p for p in GOLDEN_HOLDOUT_PMCIDS if p in all_pattern_pmcids
    ]
    golden_to_copy = [
        p for p in GOLDEN_HOLDOUT_PMCIDS if p not in all_pattern_pmcids
    ]

    if golden_in_patterns:
        logger.info(
            "Excluding %d golden PMCIDs already in pattern folders: %s",
            len(golden_in_patterns),
            ", ".join(golden_in_patterns),
        )

    logger.info(
        "Processing golden holdout (%d records, %d excluded)...",
        len(golden_to_copy),
        len(golden_in_patterns),
    )

    golden_dest = os.path.join(TROUBLESHOOT_DIR, "golden")
    golden_records = []
    missing_golden_gt = 0
    missing_golden_xml = 0

    for pmcid in golden_to_copy:
        logger.info("  %s:", pmcid)
        rec = {"pmcid": pmcid}

        # a) Golden GT JSON
        golden_gt_src = Path(GOLDEN_GT_DIR) / f"{pmcid}.json"
        if golden_gt_src.exists():
            golden_gt_dest = os.path.join(golden_dest, f"{pmcid}_golden_gt.json")
            copy_file(golden_gt_src, golden_gt_dest, dry_run)
            rec["gt_found"] = "yes"
        else:
            logger.warning("    Golden GT not found for %s", pmcid)
            rec["gt_found"] = "no"
            missing_golden_gt += 1

        # b) Article XML
        xml_src = find_xml_file(pmcid, XML_DIR)
        if xml_src:
            xml_dest = os.path.join(golden_dest, f"{pmcid}.xml")
            copy_file(xml_src, xml_dest, dry_run)
            rec["xml_found"] = "yes"
        else:
            logger.warning("    XML not found for golden: %s", pmcid)
            rec["xml_found"] = "no"
            missing_golden_xml += 1

        golden_records.append(rec)

    # Write golden manifest
    write_manifest(golden_dest, golden_records, include_ext=False, dry_run=dry_run)

    copy_summary["golden"] = {
        "total": len(golden_to_copy),
        "excluded_overlap": len(golden_in_patterns),
        "missing_gt": missing_golden_gt,
        "missing_xml": missing_golden_xml,
    }

    # --- 7. Final summary ---
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    total_files = 0
    for folder, stats in copy_summary.items():
        if folder == "golden":
            file_count = stats["total"] * 2  # gt + xml
            logger.info(
                "  %-12s: %d records (%d excluded), %d files, "
                "missing: %d gt, %d xml",
                folder, stats["total"], stats["excluded_overlap"],
                file_count, stats["missing_gt"], stats["missing_xml"],
            )
        else:
            file_count = stats["total"] * 3  # gt + ext + xml
            logger.info(
                "  %-12s: %d records, %d files, "
                "missing: %d gt, %d ext, %d xml",
                folder, stats["total"], file_count,
                stats["missing_gt"], stats["missing_ext"],
                stats["missing_xml"],
            )
        total_files += file_count

    logger.info("  Total files to copy: %d", total_files)

    if dry_run:
        logger.info("")
        logger.info("DRY RUN complete. No files were copied.")
        logger.info("Run with --apply to execute the copy operations.")

    # --- 8. Write run log ---
    log_data = {
        "timestamp": timestamp,
        "mode": mode_label,
        "patterns": {},
        "golden": {
            "requested": len(GOLDEN_HOLDOUT_PMCIDS),
            "excluded_overlap": golden_in_patterns,
            "copied": len(golden_to_copy),
        },
        "summary": copy_summary,
    }
    for pattern_name, records in patterns.items():
        log_data["patterns"][pattern_name] = {
            "count": len(records),
            "pmcids": [r["pmcid"] for r in records],
        }

    log_path = os.path.join(TROUBLESHOOT_DIR, "organiser_run_log.json")
    if not dry_run:
        os.makedirs(TROUBLESHOOT_DIR, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info("Run log saved: %s", log_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Organise v4 baseline troubleshoot files by failure pattern."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute file copies. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    dry_run_mode = not args.apply
    run(dry_run=dry_run_mode)
