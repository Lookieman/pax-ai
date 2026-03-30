"""
gt_cleanup.py
=============
Cleans up the ground-truth folder by moving GT files into organised
sub-folders under GOLDEN_GT_PATH, based on a user-supplied manifest CSV.

Target sub-folders (all created under cfg.GOLDEN_GT_PATH):
  archive/   -- GT files duplicated from golden by a previous annotator
  supp/      -- PMCIDs set aside as supplementary
  excluded/  -- PMCIDs excluded from evaluation

Action values and their behaviour:
  archive      -- move from GROUND_TRUTH_PATH top-level -> GOLDEN_GT_PATH/archive
  supp         -- move from GROUND_TRUTH_PATH top-level -> GOLDEN_GT_PATH/supp
  excluded     -- move from GROUND_TRUTH_PATH top-level -> GOLDEN_GT_PATH/excluded
  golden       -- move from GROUND_TRUTH_PATH top-level -> GOLDEN_GT_PATH/archive
  golden_supp  -- move from GROUND_TRUTH_PATH top-level -> GOLDEN_GT_PATH/archive
                  AND move from GOLDEN_GT_PATH top-level -> SUPP_GOLDEN_GT_PATH
                  (both steps are independent; each runs even if the other finds nothing)

Manifest CSV format (place at cfg.GROUND_TRUTH_PATH):
  pmcid,action
  PMC1234567,archive
  PMC2345678,supp
  PMC3456789,excluded
  PMC4567890,golden
  PMC5678901,golden_supp

For "archive", "supp", "excluded", and "golden": only files at the TOP LEVEL of
cfg.GROUND_TRUTH_PATH are moved. For "golden_supp": additionally scans the TOP
LEVEL of cfg.GOLDEN_GT_PATH. Files inside any sub-folder are never touched.

Usage:
  python gt_cleanup.py                  # dry-run (no files moved)
  python gt_cleanup.py --apply          # execute moves
  python gt_cleanup.py --manifest path/to/other.csv --apply

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
VALID_ACTIONS   = {"archive", "supp", "excluded", "golden", "golden_supp"}  #changed
MANIFEST_NAME   = "gt_cleanup_manifest.csv"
CHANGELOG_NAME  = "gt_cleanup_changelog.json"


# ===========================================================================
# Logging setup
# ===========================================================================

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("gt_cleanup")
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
# Manifest loading and validation
# ===========================================================================

def load_manifest(manifest_path: Path) -> list[dict]:
    """
    Read the cleanup manifest CSV.

    Returns a list of validated rows: [{"pmcid": str, "action": str}, ...]
    Rows with missing columns or invalid action values are skipped with a
    warning; they do not halt execution.
    """
    rows         = []
    rejected     = 0
    line_number  = 0

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    with open(manifest_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate header
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

            if action not in VALID_ACTIONS:
                logger.warning(
                    "Line %d: invalid action '%s' for %s — skipping",
                    line_number, action, pmcid,
                )
                rejected += 1
                continue

            rows.append({"pmcid": pmcid, "action": action})

    logger.info(
        "Manifest loaded: %d valid rows, %d rejected", len(rows), rejected
    )
    return rows


# ===========================================================================
# File discovery
# ===========================================================================

def discover_gt_files(gt_root: Path) -> dict[str, list[Path]]:
    """
    Scan the TOP LEVEL of gt_root for GT files.

    Returns a dict mapping PMCID stem -> list of matching Path objects.
    Only direct children of gt_root are included; sub-directories are skipped.

    Example:
      {"PMC1234567": [Path(".../PMC1234567.json")],
       "PMC9999999": [Path(".../PMC9999999.json"),
                      Path(".../PMC9999999.json.bak")]}
    """
    lookup: dict[str, list[Path]] = {}

    for item in gt_root.iterdir():
        if item.is_dir():
            # Never recurse into sub-folders
            continue

        # Use the part of the name up to the FIRST dot as the PMCID stem
        stem = item.name.split(".")[0]

        if stem not in lookup:
            lookup[stem] = []
        lookup[stem].append(item)

    logger.info(
        "Discovered %d unique PMCID stems in %s", len(lookup), gt_root
    )
    return lookup


# ===========================================================================
# Move helper
# ===========================================================================

def _attempt_move(                                                   #changed
    pmcid:     str,                                                  #changed
    action:    str,                                                  #changed
    src_path:  Path,                                                 #changed
    dest_dir:  Path,                                                 #changed
    dry_run:   bool,                                                 #changed
    label:     str,                                                  #changed
) -> dict | None:                                                    #changed
    """                                                              
    Attempt to move src_path into dest_dir.                          

    Returns a changelog entry dict on success (or dry-run preview),
    or None if the destination already exists (clash).
    """                                                              #changed
    dest_path = dest_dir / src_path.name                            #changed

    if dest_path.exists():                                           #changed
        logger.warning(                                              #changed
            "%s already exists in %s — skipping",                   #changed
            src_path.name, label,                                    #changed
        )                                                            #changed
        return None                                                  #changed

    if dry_run:                                                      #changed
        logger.info(                                                 #changed
            "[DRY RUN] Would move: %s  ->  %s",                     #changed
            src_path.name, label,                                    #changed
        )                                                            #changed
    else:                                                            #changed
        shutil.move(str(src_path), str(dest_path))                  #changed
        logger.info("Moved: %s  ->  %s", src_path.name, label)      #changed

    return {                                                         #changed
        "pmcid":     pmcid,                                          #changed
        "action":    action,                                         #changed
        "filename":  src_path.name,                                  #changed
        "source":    str(src_path),                                  #changed
        "dest":      str(dest_path),                                 #changed
        "timestamp": datetime.now().isoformat(),                     #changed
        "dry_run":   dry_run,                                        #changed
    }                                                                #changed


# ===========================================================================
# Core move logic
# ===========================================================================

def process_manifest(
    rows:          list[dict],
    gt_lookup:     dict[str, list[Path]],
    golden_lookup: dict[str, list[Path]],                            #changed
    target_dirs:   dict[str, Path],
    dry_run:       bool,
) -> list[dict]:
    """
    Iterate over manifest rows and move (or preview) each matched file.

    gt_lookup     -- files discovered at GROUND_TRUTH_PATH top-level
    golden_lookup -- files discovered at GOLDEN_GT_PATH top-level    #changed

    Action routing:
      archive / supp / excluded : gt_lookup -> corresponding target_dir
      golden                    : gt_lookup -> archive
      golden_supp               : gt_lookup -> archive               #changed
                                  golden_lookup -> supp_golden_gt    #changed

    Returns a list of changelog entries for every file moved (or previewed).
    """
    changelog         = []
    moved_count       = 0
    skipped_not_found = 0
    skipped_exists    = 0

    # Counters per action
    action_counts: dict[str, int] = {a: 0 for a in VALID_ACTIONS}

    for row in rows:
        pmcid  = row["pmcid"]
        action = row["action"]

        # ------------------------------------------------------------------
        # Determine source lookup and destination for each action
        # ------------------------------------------------------------------
        if action in {"archive", "supp", "excluded"}:               #changed
            steps = [                                                #changed
                (gt_lookup, target_dirs[action], action),           #changed
            ]                                                        #changed

        elif action == "golden":                                     #changed
            steps = [                                                #changed
                (gt_lookup, target_dirs["archive"], "archive"),     #changed
            ]                                                        #changed

        elif action == "golden_supp":                               #changed
            steps = [                                                #changed
                (gt_lookup,     target_dirs["archive"],         "archive"),        #changed
                (golden_lookup, target_dirs["supp_golden_gt"],  "supp_golden_gt"), #changed
            ]                                                        #changed

        else:                                                        #changed
            # Should never reach here after manifest validation      #changed
            logger.error("Unhandled action '%s' for %s", action, pmcid)  #changed
            continue                                                 #changed

        # ------------------------------------------------------------------
        # Execute each step independently
        # ------------------------------------------------------------------
        row_moved = False                                            #changed

        for source_lookup, dest_dir, dest_label in steps:           #changed
            matched_files = source_lookup.get(pmcid)                #changed

            if not matched_files:                                    #changed
                logger.warning(                                      #changed
                    "No GT file found for %s in %s source — skipping step", #changed
                    pmcid, dest_label,                               #changed
                )                                                    #changed
                skipped_not_found += 1                              #changed
                continue                                             #changed

            for src_path in matched_files:                          #changed
                entry = _attempt_move(                              #changed
                    pmcid, action, src_path, dest_dir,              #changed
                    dry_run, dest_label,                            #changed
                )                                                    #changed
                if entry is None:                                    #changed
                    skipped_exists += 1                             #changed
                else:                                               #changed
                    changelog.append(entry)                         #changed
                    moved_count += 1                                #changed
                    action_counts[action] += 1                      #changed
                    row_moved = True                                #changed

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    mode_label = "[DRY RUN]" if dry_run else "[APPLIED]"

    logger.info("-" * 60)
    logger.info("%s Summary", mode_label)
    logger.info("-" * 60)
    for action, count in action_counts.items():
        logger.info("  %-15s : %d file(s)", action, count)
    logger.info("  %-15s : %d file(s)", "Total moved",   moved_count)
    logger.info("  %-15s : %d file(s)", "Not found",     skipped_not_found)
    logger.info("  %-15s : %d file(s)", "Dest clash",    skipped_exists)

    if dry_run:
        logger.info(
            "Dry-run complete. Re-run with --apply to execute moves."
        )

    return changelog


# ===========================================================================
# Changelog writer
# ===========================================================================

def write_changelog(changelog: list[dict], gt_root: Path, dry_run: bool):
    """
    Append changelog entries to the JSON audit file at gt_root.
    A dry-run still writes the changelog (marked dry_run=true) so you can
    inspect what would happen before committing.
    """
    changelog_path = gt_root / CHANGELOG_NAME

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
    print(f"gt_cleanup.py starting — Python: {sys.executable}", flush=True)  #changed
    # -----------------------------------------------------------------------
    # CLI arguments
    # -----------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=(
            "Clean up the ground-truth folder by moving GT files into "
            "archive/, supp/, or excluded/ sub-folders under GOLDEN_GT_PATH."
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
        help="Execute file moves. Without this flag the script runs as a dry-run.",
    )
    args = parser.parse_args()

    dry_run = not args.apply

    # -----------------------------------------------------------------------
    # Resolve paths from cfg
    # -----------------------------------------------------------------------
    gt_root          = Path(cfg.GROUND_TRUTH_PATH)
    golden_root      = Path(cfg.GOLDEN_GT_PATH)
    supp_golden_root = Path(cfg.SUPP_GOLDEN_GT_PATH)                #changed

    manifest_path = (
        Path(args.manifest) if args.manifest
        else gt_root / MANIFEST_NAME
    )

    target_dirs = {
        "archive":       golden_root / "archive",
        "supp":          golden_root / "supp",
        "excluded":      golden_root / "excluded",
        "supp_golden_gt": supp_golden_root,                          #changed
    }

    # -----------------------------------------------------------------------
    # Pre-flight checks
    # -----------------------------------------------------------------------
    if not gt_root.exists():
        logger.error("GROUND_TRUTH_PATH does not exist: %s", gt_root)
        sys.exit(1)

    if not golden_root.exists():
        logger.error("GOLDEN_GT_PATH does not exist: %s", golden_root)
        sys.exit(1)

    # Create target sub-directories now (even in dry-run, so paths are valid)
    for dir_label, dir_path in target_dirs.items():
        if not dry_run:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info("Ensured directory: %s", dir_path)
        else:
            exists_label = "exists" if dir_path.exists() else "will be created"
            logger.info(
                "[DRY RUN] Target dir %s/ %s", dir_label, exists_label
            )

    # -----------------------------------------------------------------------
    # Load manifest
    # -----------------------------------------------------------------------
    rows = load_manifest(manifest_path)

    if not rows:
        logger.warning("No valid rows in manifest. Nothing to do.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Discover GT files — two sources
    # -----------------------------------------------------------------------
    gt_lookup     = discover_gt_files(gt_root)
    golden_lookup = discover_gt_files(golden_root)                   #changed

    # -----------------------------------------------------------------------
    # Process
    # -----------------------------------------------------------------------
    changelog = process_manifest(                                    #changed
        rows, gt_lookup, golden_lookup, target_dirs, dry_run        #changed
    )                                                                #changed

    # -----------------------------------------------------------------------
    # Write changelog
    # -----------------------------------------------------------------------
    if changelog:
        write_changelog(changelog, golden_root, dry_run)


if __name__ == "__main__":
    main()
