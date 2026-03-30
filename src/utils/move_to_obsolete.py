"""
move_to_obsolete.py
===================
Reads a list of PMCIDs and moves their GT JSON files from
GROUND_TRUTH_PATH and GOLDEN_GT_PATH into a timestamped
"obsolete" subdirectory.

Usage:
    python move_to_obsolete.py                         # dry run
    python move_to_obsolete.py --apply                 # execute moves
    python move_to_obsolete.py --pmcid-file <path>     # custom input file
    python move_to_obsolete.py --apply --pmcid-file <path>

Searches in order:
    1. cfg.GROUND_TRUTH_PATH
    2. cfg.GOLDEN_GT_PATH

Destination:
    cfg.GROUND_TRUTH_PATH / obsolete / <PMCID>.json

Author: AI6129 Pathogen Tracking Project
"""

import sys
import json
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path resolution — same pattern used across all project scripts
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from config import cfg

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_PMCID_FILE = Path(_SCRIPT_DIR) / "PMCIDs_updated_unique.txt"
OBSOLETE_DIR       = Path(cfg.GROUND_TRUTH_PATH) / "obsolete"

SEARCH_PATHS = [
    Path(cfg.GROUND_TRUTH_PATH),
    Path(cfg.GOLDEN_GT_PATH),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_pmcids(filepath: Path) -> list[str]:
    """Read PMCID list from a text file (one per line, ignores header/blanks)."""
    pmcids = []
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            val = line.strip()
            if val and val.upper().startswith("PMC"):
                pmcids.append(val)
    return pmcids


def find_json(pmcid: str, search_paths: list[Path]) -> Path | None:
    """Return the first JSON file found for this PMCID across search_paths."""
    filename = f"{pmcid}.json"
    for base in search_paths:
        candidate = base / filename
        if candidate.exists():
            return candidate
    return None


def move_file(src: Path, dst_dir: Path, apply: bool) -> str:
    """
    Move src to dst_dir / src.name.
    Returns a status string for the audit log.
    """
    dst = dst_dir / src.name

    if dst.exists():
        return "SKIPPED_DST_EXISTS"

    if apply:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return "MOVED"
    else:
        return "DRY_RUN"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Move updated GT JSON files to obsolete folder."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute moves (default: dry run only)",
    )
    parser.add_argument(
        "--pmcid-file",
        type=Path,
        default=DEFAULT_PMCID_FILE,
        help=f"Path to PMCID list file (default: {DEFAULT_PMCID_FILE})",
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(flush=True)
    log.info(f"Python: {sys.executable}")
    log.info(f"Mode: {mode}")
    log.info(f"PMCID file: {args.pmcid_file}")
    log.info(f"Search paths:")
    for p in SEARCH_PATHS:
        log.info(f"  {p}")
    log.info(f"Destination: {OBSOLETE_DIR}")
    log.info("-" * 60)

    # Load PMCIDs
    pmcids = load_pmcids(args.pmcid_file)
    log.info(f"PMCIDs to process: {len(pmcids)}")

    # Counters
    counts = {"MOVED": 0, "DRY_RUN": 0, "NOT_FOUND": 0, "SKIPPED_DST_EXISTS": 0}
    audit  = []

    for pmcid in pmcids:
        src = find_json(pmcid, SEARCH_PATHS)

        if src is None:
            log.warning(f"  NOT FOUND  : {pmcid}")
            counts["NOT_FOUND"] += 1
            audit.append({"pmcid": pmcid, "status": "NOT_FOUND", "source": None})
            continue

        status = move_file(src, OBSOLETE_DIR, apply=args.apply)
        counts[status] += 1

        if status == "MOVED":
            log.info(f"  MOVED      : {pmcid}  ({src})")
        elif status == "DRY_RUN":
            log.info(f"  DRY RUN    : {pmcid}  ({src})")
        elif status == "SKIPPED_DST_EXISTS":
            log.warning(f"  DST EXISTS : {pmcid}  (already in obsolete)")

        audit.append({"pmcid": pmcid, "status": status, "source": str(src)})

    # Summary
    log.info("-" * 60)
    log.info(f"Summary ({mode}):")
    for k, v in counts.items():
        log.info(f"  {k:<22}: {v}")

    # Write audit log
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path  = OBSOLETE_DIR if args.apply else Path(cfg.LOG_PATH)
    audit_path.mkdir(parents=True, exist_ok=True)
    audit_file  = audit_path / f"move_to_obsolete_{timestamp}.json"

    if args.apply or not args.apply:   # always write audit
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_file, "w", encoding="utf-8") as fh:
            json.dump({"mode": mode, "timestamp": timestamp, "records": audit},
                      fh, indent=2)
        log.info(f"Audit log: {audit_file}")

    if not args.apply:
        log.info("")
        log.info("Dry run complete. Add --apply to execute moves.")


if __name__ == "__main__":
    main()
