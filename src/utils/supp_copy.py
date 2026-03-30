"""
supp_copy.py
============
Copies supplementary files for PMCIDs flagged as "supp" in the cleanup
manifest CSV from cfg.SUPPLEMENTARY_PATH to cfg.ATTACHMENTS_PATH.

Source      : cfg.SUPPLEMENTARY_PATH
Destination : cfg.ATTACHMENTS_PATH
Filter      : manifest rows where action == "supp"

Discovery strategy (per PMCID, in order):
  1. Sub-folder named exactly after the PMCID
     e.g. SUPPLEMENTARY_PATH/PMC1234567/  -> copied as a folder
  2. Flat files whose name starts with the PMCID
     e.g. SUPPLEMENTARY_PATH/PMC1234567_S1.pdf -> copied individually

Files are COPIED, not moved.  The source is never modified.
Existing files at the destination are skipped (no overwrite).

Manifest CSV format (same file used by gt_cleanup.py):
  pmcid,action
  PMC1234567,archive
  PMC2345678,supp       <-- only these rows are processed
  PMC3456789,excluded

Usage:
  python supp_copy.py                           # dry-run
  python supp_copy.py --apply                   # execute copies
  python supp_copy.py --manifest path/to/other.csv --apply

Author : Luqman (AI6129 Pathogen Tracking Project)
Date   : March 2026
"""

import argparse
import csv
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root and import cfg
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent                       #changed
sys.path.insert(0, str(_SCRIPT_DIR))                                #changed
sys.path.insert(0, str(_SCRIPT_DIR.parent))                         #changed
from config import cfg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_ACTION  = frozenset({"supp", "golden_supp"})          #changed
MANIFEST_NAME  = "gt_cleanup_manifest.csv"
CHANGELOG_NAME = "supp_copy_changelog.json"


# ===========================================================================
# Logging setup
# ===========================================================================

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("supp_copy")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.stream = open(sys.stdout.fileno(), mode='w',             #changed
                          encoding='utf-8', buffering=1)             #changed
    formatter = logging.Formatter(cfg.LOG_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = _setup_logging()


# ===========================================================================
# Manifest loading
# ===========================================================================

def load_supp_pmcids(manifest_path: Path) -> list[str]:
    """
    Read the manifest CSV and return only the PMCIDs whose action is "supp".

    Invalid rows (missing columns, empty PMCID) are skipped with a warning.
    """
    pmcids      = []
    rejected    = 0
    line_number = 0

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    with open(manifest_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None or not {"pmcid", "action"}.issubset(
            set(reader.fieldnames)
        ):
            logger.error(
                "Manifest must have columns 'pmcid' and 'action'. "
                "Found: %s", reader.fieldnames
            )
            sys.exit(1)

        for row in reader:
            line_number += 1
            pmcid  = row.get("pmcid", "").strip()
            action = row.get("action", "").strip().lower()

            if not pmcid:
                logger.warning("Line %d: empty pmcid — skipping", line_number)
                rejected += 1
                continue

            if action in TARGET_ACTION:                       #changed
                pmcids.append(pmcid)

    logger.info(
        "Manifest loaded: %d supp PMCID(s) identified, %d row(s) skipped",
        len(pmcids), rejected,
    )
    return pmcids


# ===========================================================================
# Source file discovery
# ===========================================================================

def _search_dir(pmcid: str, search_root: Path, seen_paths: set) -> list[dict]:  #changed
    """                                                                          #changed
    Search a single directory for a PMCID folder or PMCID-prefixed flat files. #changed
    Mutates seen_paths to prevent duplicates across multiple search roots.      #changed
    """                                                                          #changed
    found = []                                                                   #changed

    candidate_folder = search_root / pmcid                                       #changed
    if candidate_folder.is_dir() and candidate_folder not in seen_paths:        #changed
        found.append({"path": candidate_folder, "kind": "folder"})              #changed
        seen_paths.add(candidate_folder)                                         #changed

    for item in search_root.iterdir():                                           #changed
        if item.is_dir():                                                        #changed
            continue                                                             #changed
        if item.name.startswith(pmcid) and item not in seen_paths:              #changed
            found.append({"path": item, "kind": "file"})                        #changed
            seen_paths.add(item)                                                 #changed

    return found                                                                 #changed


def discover_supp_sources(pmcid: str, supp_root: Path) -> list[dict]:
    """
    Locate supplementary content for a single PMCID under supp_root.

    Returns a list of source descriptors:
      [{"path": Path, "kind": "folder" | "file"}, ...]

    Search order:                                                                #changed
      1. Top level of supp_root  (supp_root/PMCID/)                             #changed
      2. Each immediate sub-folder of supp_root (e.g. supp_root/golden/PMCID/) #changed
    Both levels are checked; results are merged (de-duplicated by path).        #changed
    The sub-folder that matched is logged so misplaced PMCIDs are easy to spot. #changed
    """
    sources    = []
    seen_paths = set()

    # --- Level 1: top level of supp_root ---
    top_level = _search_dir(pmcid, supp_root, seen_paths)               #changed
    sources.extend(top_level)                                            #changed

    # --- Level 2: immediate sub-folders of supp_root ---                #changed
    # Skip folders whose name == pmcid; those were handled in level 1.  #changed
    for subdir in sorted(supp_root.iterdir()):                           #changed
        if not subdir.is_dir():                                          #changed
            continue                                                     #changed
        if subdir.name == pmcid:                                         #changed
            continue  # already processed at level 1                    #changed
        sub_results = _search_dir(pmcid, subdir, seen_paths)            #changed
        if sub_results:                                                  #changed
            logger.debug(                                                #changed
                "Found %s under sub-folder: %s", pmcid, subdir.name,   #changed
            )                                                            #changed
            sources.extend(sub_results)                                  #changed

    return sources


# ===========================================================================
# Copy helpers
# ===========================================================================

def _copy_folder(
    src: Path,
    dest_root: Path,
    pmcid: str,
    dry_run: bool,
) -> list[dict]:
    """
    Copy an entire PMCID sub-folder into dest_root.

    The destination folder is dest_root / pmcid.
    Individual files inside are checked for existence to avoid overwriting.
    Returns a list of changelog entries.
    """
    entries   = []
    dest_dir  = dest_root / pmcid

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src.rglob("*")):
        if src_file.is_dir():
            continue

        relative   = src_file.relative_to(src)
        dest_file  = dest_dir / relative

        if dest_file.exists():
            logger.warning(
                "%s already exists in attachments/%s/ — skipping",
                src_file.name, pmcid,
            )
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] Would copy: %s/%s  ->  attachments/%s/",
                pmcid, relative, pmcid,
            )
        else:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dest_file))
            logger.info(
                "Copied: %s/%s  ->  attachments/%s/",
                pmcid, relative, pmcid,
            )

        entries.append({
            "pmcid":     pmcid,
            "kind":      "folder",
            "filename":  str(relative),
            "source":    str(src_file),
            "dest":      str(dest_file),
            "timestamp": datetime.now().isoformat(),
            "dry_run":   dry_run,
        })

    return entries


def _copy_file(
    src: Path,
    dest_root: Path,
    pmcid: str,
    dry_run: bool,
) -> list[dict]:
    """
    Copy a single flat file into dest_root.
    Returns a list containing one changelog entry (or none if skipped).
    """
    dest_file = dest_root / src.name

    if dest_file.exists():
        logger.warning(
            "%s already exists in attachments/ — skipping", src.name
        )
        return []

    if dry_run:
        logger.info(
            "[DRY RUN] Would copy: %s  ->  attachments/", src.name
        )
    else:
        shutil.copy2(str(src), str(dest_file))
        logger.info("Copied: %s  ->  attachments/", src.name)

    return [{
        "pmcid":     pmcid,
        "kind":      "file",
        "filename":  src.name,
        "source":    str(src),
        "dest":      str(dest_file),
        "timestamp": datetime.now().isoformat(),
        "dry_run":   dry_run,
    }]


# ===========================================================================
# Core processing
# ===========================================================================

def process_pmcids(
    pmcids:    list[str],
    supp_root: Path,
    dest_root: Path,
    dry_run:   bool,
) -> list[dict]:
    """
    Iterate over supp PMCIDs, discover their source files, and copy them.
    Returns the full changelog for the run.
    """
    changelog         = []
    copied_count      = 0
    skipped_not_found = 0

    for pmcid in pmcids:
        sources = discover_supp_sources(pmcid, supp_root)

        if not sources:
            logger.warning(
                "No supplementary content found for %s — skipping", pmcid
            )
            skipped_not_found += 1
            continue

        for source in sources:
            if source["kind"] == "folder":
                entries = _copy_folder(
                    source["path"], dest_root, pmcid, dry_run
                )
            else:
                entries = _copy_file(
                    source["path"], dest_root, pmcid, dry_run
                )

            changelog.extend(entries)
            copied_count += len(entries)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    mode_label = "[DRY RUN]" if dry_run else "[APPLIED]"

    logger.info("-" * 60)
    logger.info("%s Summary", mode_label)
    logger.info("-" * 60)
    logger.info("  %-12s : %d", "Files copied", copied_count)
    logger.info("  %-12s : %d", "PMCIDs missed", skipped_not_found)

    if dry_run:
        logger.info(
            "Dry-run complete. Re-run with --apply to execute copies."
        )

    return changelog


# ===========================================================================
# Changelog writer
# ===========================================================================

def write_changelog(changelog: list[dict], dest_root: Path):
    """
    Append changelog entries to the JSON audit file at dest_root.
    Written for both dry-run and applied runs (entries carry dry_run flag).
    """
    changelog_path = dest_root / CHANGELOG_NAME

    existing = []
    if changelog_path.exists():
        try:
            with open(changelog_path, encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            logger.warning(
                "Could not read existing changelog; starting fresh."
            )

    existing.extend(changelog)

    with open(changelog_path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, ensure_ascii=False)

    logger.info(
        "Changelog written (%d total entries): %s",
        len(existing), changelog_path,
    )


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    print(f"supp_copy.py starting — Python: {sys.executable}", flush=True)  #changed
    parser = argparse.ArgumentParser(
        description=(
            "Copy supplementary files for 'supp' PMCIDs from "
            "SUPPLEMENTARY_PATH to ATTACHMENTS_PATH."
        )
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help=(
            "Path to the cleanup manifest CSV. "
            f"Defaults to GROUND_TRUTH_PATH/{MANIFEST_NAME}"
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute copies. Without this flag the script runs as a dry-run.",
    )
    args = parser.parse_args()

    dry_run = not args.apply

    # -----------------------------------------------------------------------
    # Resolve paths
    # -----------------------------------------------------------------------
    supp_root = Path(cfg.SUPPLEMENTARY_PATH)
    dest_root = Path(cfg.ATTACHMENTS_PATH)

    manifest_path = (
        Path(args.manifest) if args.manifest
        else Path(cfg.GROUND_TRUTH_PATH) / MANIFEST_NAME
    )

    # -----------------------------------------------------------------------
    # Pre-flight checks
    # -----------------------------------------------------------------------
    if not supp_root.exists():
        logger.error("SUPPLEMENTARY_PATH does not exist: %s", supp_root)
        sys.exit(1)

    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured destination: %s", dest_root)
    else:
        exists_label = "exists" if dest_root.exists() else "will be created"
        logger.info(
            "[DRY RUN] ATTACHMENTS_PATH %s: %s", exists_label, dest_root
        )

    # -----------------------------------------------------------------------
    # Load manifest — supp PMCIDs only
    # -----------------------------------------------------------------------
    pmcids = load_supp_pmcids(manifest_path)

    if not pmcids:
        logger.warning(
            "No PMCIDs with action='supp' found in manifest. Nothing to do."
        )
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Process
    # -----------------------------------------------------------------------
    changelog = process_pmcids(pmcids, supp_root, dest_root, dry_run)

    # -----------------------------------------------------------------------
    # Write changelog
    # -----------------------------------------------------------------------
    if changelog:
        write_changelog(changelog, dest_root)


if __name__ == "__main__":
    main()
