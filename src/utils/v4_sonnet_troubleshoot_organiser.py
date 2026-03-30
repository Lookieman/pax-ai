"""
V4 Sonnet Baseline Troubleshoot File Organiser
===============================================
Copies GT JSON, extracted JSON, and article XML files for a specified
list of PMCIDs into a single troubleshoot folder for targeted analysis.

Simplified variant of v4_troubleshoot_organiser.py — no pattern
classification or subfolders. Takes an explicit PMCID list.

Usage:
  python v4_sonnet_troubleshoot_organiser.py                  # dry-run
  python v4_sonnet_troubleshoot_organiser.py --apply           # execute copies

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
# v4 Sonnet baseline output locations
V4_SONNET_DIR = os.path.join(
    cfg.DRIVE_BASE, "assay", "gt_diagnostic_analysis", "v4_baseline_sonnet"
)
EXTRACTION_DIR = os.path.join(V4_SONNET_DIR, "raw_extractions")

# Troubleshoot output directory (flat, no subfolders)
TROUBLESHOOT_DIR = os.path.join(V4_SONNET_DIR, "troubleshoot")

# Source directories (from config.py singleton)
GT_DIR = cfg.GROUND_TRUTH_PATH
GOLDEN_GT_DIR = cfg.GOLDEN_GT_PATH
XML_DIR = cfg.XML_PATH

# PMCIDs to collect
TARGET_PMCIDS = [
    "PMC2873750",
    "PMC3020606",
    "PMC5637494",
    "PMC5739443",
    "PMC5794934",
    "PMC5938507",
    "PMC6307136",
    "PMC6486240",
    "PMC6639624",
    "PMC6667484",
    "PMC6935380",
    "PMC6995202",
    "PMC7098901",
    "PMC7433231",
    "PMC7460271",
    "PMC7587706",
    "PMC7656189",
    "PMC7766374",
    "PMC8253257",
    "PMC8749661",
    "PMC8947133",
    "PMC9049261",
    "PMC9137667",
    "PMC9323645",
    "PMC9409446",
    "PMC9353134",
    "PMC4866840",
    "PMC8698551",
    "PMC9035464",
    "PMC8784875",
    "PMC6307136",
    "PMC9216381",
    "PMC6430326",
    "PMC7581672",
    "PMC6986767",
    "PMC7460271",
    "PMC4939201",
    "PMC5832104",
    "PMC4892500",
    "PMC9146225",
    "PMC4810482",
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
# Helper functions (reused from v4_troubleshoot_organiser.py)
# ---------------------------------------------------------------------------
def find_gt_file(pmcid, gt_dir, golden_gt_dir):
    """
    Locate the GT JSON file for a given PMCID.
    Checks the main GT directory first, then the golden subdirectory.

    Returns:
        Path object if found, None otherwise.
    """
    main_path = Path(gt_dir) / f"{pmcid}.json"
    if main_path.exists():
        return main_path

    golden_path = Path(golden_gt_dir) / f"{pmcid}.json"
    if golden_path.exists():
        return golden_path

    return None


def find_extraction_file(pmcid, ext_dir):
    """
    Locate the extracted JSON file for a given PMCID.
    Tries {PMCID}_extraction.json first, then {PMCID}.json.

    Returns:
        Path object if found, None otherwise.
    """
    ext_dir_path = Path(ext_dir)

    # Try _extraction.json pattern first
    ext_path = ext_dir_path / f"{pmcid}_extraction.json"
    if ext_path.exists():
        return ext_path

    # Fallback to plain .json
    ext_path2 = ext_dir_path / f"{pmcid}.json"
    if ext_path2.exists():
        return ext_path2

    return None


def find_xml_file(pmcid, xml_dir):
    """
    Locate the article XML file for a given PMCID.
    Handles date-appended filenames (e.g. PMC1278947_20260315.xml).

    Returns:
        Path object if found, None otherwise.
    """
    xml_dir_path = Path(xml_dir)

    # Try exact match first
    exact_path = xml_dir_path / f"{pmcid}.xml"
    if exact_path.exists():
        return exact_path

    # Try glob pattern for date-appended filenames
    matches = sorted(xml_dir_path.glob(f"{pmcid}*.xml"))
    if matches:
        return matches[-1]  # most recent if multiple

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
    logger.info(
        "V4 Sonnet Troubleshoot File Organiser [%s] - %s", mode_label, timestamp
    )
    logger.info("=" * 70)
    logger.info("Target PMCIDs: %d", len(TARGET_PMCIDS))

    # --- 1. Validate source paths ---
    logger.info("Validating source paths...")
    paths_ok = True
    for label, path in [
        ("GT directory", GT_DIR),
        ("Golden GT directory", GOLDEN_GT_DIR),
        ("XML directory", XML_DIR),
        ("Extraction directory", EXTRACTION_DIR),
    ]:
        exists = os.path.exists(path)
        status = "OK" if exists else "MISSING"
        logger.info("  %-25s: %s [%s]", label, path, status)
        if not exists:
            paths_ok = False

    if not paths_ok:
        logger.error("One or more source paths are missing. Aborting.")
        sys.exit(1)

    # --- 2. Create output folder ---
    logger.info("Output folder: %s", TROUBLESHOOT_DIR)
    if not dry_run:
        os.makedirs(TROUBLESHOOT_DIR, exist_ok=True)

    # --- 3. Copy files for each PMCID ---
    logger.info("-" * 50)
    logger.info("Processing %d PMCIDs...", len(TARGET_PMCIDS))

    manifest_records = []
    missing_gt = 0
    missing_ext = 0
    missing_xml = 0
    total_copied = 0

    for pmcid in TARGET_PMCIDS:
        logger.info("  %s:", pmcid)
        rec = {"pmcid": pmcid}

        # a) GT JSON
        gt_src = find_gt_file(pmcid, GT_DIR, GOLDEN_GT_DIR)
        if gt_src:
            gt_dest = os.path.join(TROUBLESHOOT_DIR, f"{pmcid}_gt.json")
            copy_file(gt_src, gt_dest, dry_run)
            rec["gt_found"] = "yes"
            rec["gt_source"] = str(gt_src)
            total_copied += 1
        else:
            logger.warning("    GT not found for %s", pmcid)
            rec["gt_found"] = "no"
            rec["gt_source"] = ""
            missing_gt += 1

        # b) Extracted JSON
        ext_src = find_extraction_file(pmcid, EXTRACTION_DIR)
        if ext_src:
            ext_dest = os.path.join(TROUBLESHOOT_DIR, f"{pmcid}_ext.json")
            copy_file(ext_src, ext_dest, dry_run)
            rec["ext_found"] = "yes"
            total_copied += 1
        else:
            logger.warning("    Extraction not found for %s", pmcid)
            rec["ext_found"] = "no"
            missing_ext += 1

        # c) Article XML
        xml_src = find_xml_file(pmcid, XML_DIR)
        if xml_src:
            xml_dest = os.path.join(TROUBLESHOOT_DIR, f"{pmcid}.xml")
            copy_file(xml_src, xml_dest, dry_run)
            rec["xml_found"] = "yes"
            total_copied += 1
        else:
            logger.warning("    XML not found for %s", pmcid)
            rec["xml_found"] = "no"
            missing_xml += 1

        manifest_records.append(rec)

    # --- 4. Write manifest CSV ---
    manifest_path = os.path.join(TROUBLESHOOT_DIR, "manifest.csv")
    headers = ["pmcid", "gt_found", "gt_source", "ext_found", "xml_found"]

    if not dry_run:
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for rec in manifest_records:
                writer.writerow(rec)
        logger.info("Manifest written: %s", manifest_path)
    else:
        logger.info("[DRY RUN] Would write manifest: %s", manifest_path)

    # --- 5. Write run log JSON ---
    log_data = {
        "timestamp": timestamp,
        "mode": mode_label,
        "target_pmcids": TARGET_PMCIDS,
        "total_pmcids": len(TARGET_PMCIDS),
        "files_copied": total_copied,
        "missing": {
            "gt": missing_gt,
            "ext": missing_ext,
            "xml": missing_xml,
        },
        "source_paths": {
            "gt_dir": GT_DIR,
            "golden_gt_dir": GOLDEN_GT_DIR,
            "xml_dir": XML_DIR,
            "extraction_dir": EXTRACTION_DIR,
        },
        "output_dir": TROUBLESHOOT_DIR,
    }

    log_path = os.path.join(TROUBLESHOOT_DIR, "organiser_run_log.json")
    if not dry_run:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info("Run log saved: %s", log_path)

    # --- 6. Summary ---
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info("  PMCIDs processed:  %d", len(TARGET_PMCIDS))
    logger.info("  Files copied:      %d", total_copied)
    logger.info("  Missing GT:        %d", missing_gt)
    logger.info("  Missing extraction:%d", missing_ext)
    logger.info("  Missing XML:       %d", missing_xml)

    if dry_run:
        logger.info("")
        logger.info("DRY RUN complete. No files were copied.")
        logger.info("Run with --apply to execute the copy operations.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect GT, extraction, and XML files for Sonnet baseline troubleshooting.",
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
