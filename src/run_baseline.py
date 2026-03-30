"""
run_baseline.py
===============
v4 baseline entry point: load PMCIDs, run DSPy extraction, evaluate
against ground truth, and generate reports.

Supports three modes:
  1. Full run:     Extract + score all PMCIDs in the list.
  2. Selective re-run: Re-extract + re-score specific PMCIDs, merge
                   into existing results, and regenerate all reports.
  3. Rescore only: Re-score specific PMCIDs from existing extractions
                   (no LLM calls). Use when GT changed but extraction
                   is still valid.

Usage:
    # Full run
    python run_baseline.py --pmcid-list path/to/pmcids.txt
    python run_baseline.py --pmcid-list pmcids.txt --model claude-haiku-4.5 --dry-run
    python run_baseline.py --pmcid-list pmcids.txt --golden-pmcids golden.txt --delay 2.0

    # Selective re-run (re-extract + re-score, merge into existing)
    python run_baseline.py --pmcid-list pmcids.txt --rerun-pmcids PMC1278947 PMC3020606

    # Rescore only (GT changed, reuse existing extraction)
    python run_baseline.py --pmcid-list pmcids.txt --rescore-only PMC1278947 PMC3020606

    # Rescore ALL from existing raw extractions (e.g. after crash)     #changed
    python run_baseline.py --pmcid-list pmcids.txt --rescore-only ALL  #changed

Output is written to:
    <DRIVE_BASE>/assay/gt_diagnostic_analysis/<output-label>/

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015
"""

import sys
import os
import csv                                                                     #changed
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path resolution: ensure src/ is on sys.path
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import cfg                                                         # noqa: E402

import dspy                                                                    # noqa: E402

from extract.article_loader import (                                           # noqa: E402
    build_xml_mapping,
    load_article_text,
    load_ground_truth,
    load_pmcid_list,
)
from extract.extractor import (                                                # noqa: E402  #changed
    AssayExtractor,                                                            #changed
    parse_extraction_output,                                                   #changed
    EMPTY_RESULT,                                                              #changed
)                                                                              #changed
from evaluate.scorer import score_record, RecordResult                          # noqa: E402
from evaluate.report import generate_report                                     # noqa: E402


# ===========================================================================
# Logging setup
# ===========================================================================

def setup_logging(log_dir: Path, run_label: str) -> None:
    """Configure logging to both console and file.

    Args:
        log_dir: Directory for the log file.
        run_label: Used in the log filename.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{run_label}_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=cfg.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Logging initialised: %s", log_file)


# ===========================================================================
# Argument parsing
# ===========================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Namespace with all CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description="v4 Baseline: extract assay information and evaluate against GT."
    )

    parser.add_argument(
        "--pmcid-list",
        type=Path,
        required=True,
        help="Path to text file with one PMCID per line.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-haiku-4.5",
        choices=list(cfg.DSPY_MODEL_STRINGS.keys()),
        help="Model key from config.DSPY_MODEL_STRINGS (default: claude-haiku-4.5).",
    )
    parser.add_argument(
        "--output-label",
        type=str,
        default="v4_baseline",
        help="Subdirectory name under gt_diagnostic_analysis/ (default: v4_baseline).",
    )
    parser.add_argument(
        "--gt-dir",
        type=Path,
        default=None,
        help="Override GT directory (default: config GROUND_TRUTH_PATH).",
    )
    parser.add_argument(
        "--xml-dir",
        type=Path,
        default=None,
        help="Override XML directory (default: config XML_PATH).",
    )
    parser.add_argument(
        "--golden-pmcids",
        type=Path,
        default=None,
        help="Optional file listing golden PMCIDs (uses golden GT/XML dirs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs only; no LLM calls.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between API calls (default: 1.5).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=100000,
        help="Maximum article text length before truncation (default: 100000).",
    )
    parser.add_argument(                                                       #changed
        "--max-retries",                                                       #changed
        type=int,                                                              #changed
        default=2,                                                             #changed
        help="Maximum extraction attempts per PMCID before giving up "         #changed
             "(default: 2). Set to 1 to disable retry.",                       #changed
    )                                                                          #changed
    parser.add_argument(                                                       #changed
        "--rerun-pmcids",                                                      #changed
        nargs="+",                                                             #changed
        default=None,                                                          #changed
        help="Re-extract + re-score specific PMCIDs. Merges into existing "    #changed
             "results and regenerates all reports.",                            #changed
    )                                                                          #changed
    parser.add_argument(                                                       #changed
        "--rescore-only",                                                      #changed
        nargs="+",                                                             #changed
        default=None,                                                          #changed
        help="Re-score specific PMCIDs from existing raw extractions "         #changed
             "(no LLM calls). Use 'ALL' to rescore every PMCID in the list "   #changed
             "(e.g. after a crash before report generation).",                  #changed
    )                                                                          #changed

    return parser.parse_args()


# ===========================================================================
# Raw output saving
# ===========================================================================

def save_raw_extraction(
    pmcid: str,
    raw_output: str,
    parsed_output: dict,
    output_dir: Path,
) -> None:
    """Save raw and parsed LLM output for reproducibility.

    Args:
        pmcid: PubMed Central ID.
        raw_output: Raw string from the LLM.
        parsed_output: Parsed v4-structured dictionary.
        output_dir: Directory to save into.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pmcid": pmcid,
        "timestamp": datetime.now().isoformat(),
        "raw_output": raw_output,
        "parsed_output": parsed_output,
    }
    filepath = output_dir / f"{pmcid}_extraction.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


# ===========================================================================
# Loading existing results for selective re-run                             #changed
# ===========================================================================

def load_existing_results(output_dir: Path) -> dict:                        #changed
    """Load existing per-record results CSV into a dict keyed by PMCID.

    Each value is a RecordResult reconstructed from the CSV row.
    Returns an empty dict if the CSV does not exist.

    Args:
        output_dir: Directory containing the per_record_results CSV.

    Returns:
        Dict mapping PMCID to RecordResult.
    """
    csv_path = output_dir / "v4_baseline_per_record_results.csv"            #changed
    if not csv_path.exists():                                               #changed
        logging.warning("No existing results CSV at %s", csv_path)         #changed
        return {}                                                           #changed

    existing = {}                                                           #changed
    with open(csv_path, newline="", encoding="utf-8") as f:                #changed
        reader = csv.DictReader(f)                                          #changed
        for row in reader:                                                  #changed
            pmcid = row["pmcid"]                                            #changed
            result = RecordResult(                                          #changed
                pmcid=pmcid,                                                #changed
                gt_category=row.get("gt_category", ""),                     #changed
                ext_category=row.get("ext_category", ""),                   #changed
                category_correct=row.get("category_correct", "").lower()    #changed
                    == "true",                                              #changed
                tp=int(row.get("tp", 0)),                                   #changed
                fp=int(row.get("fp", 0)),                                   #changed
                fn=int(row.get("fn", 0)),                                   #changed
                precision=float(row.get("precision", 0.0)),                 #changed
                recall=float(row.get("recall", 0.0)),                       #changed
                primary_f1=float(row.get("primary_f1", 0.0)),              #changed
                gt_item_count=int(row.get("gt_item_count", 0)),            #changed
                ext_item_count=int(row.get("ext_item_count", 0)),          #changed
                error_message=row.get("error_message", ""),                 #changed
            )                                                               #changed
            existing[pmcid] = result                                        #changed

    logging.info(                                                           #changed
        "Loaded %d existing results from %s", len(existing), csv_path      #changed
    )                                                                       #changed
    return existing                                                         #changed


def load_raw_extraction(pmcid: str, raw_output_dir: Path) -> dict:         #changed
    """Load a previously saved raw extraction JSON for re-scoring.

    Args:
        pmcid: PubMed Central ID.
        raw_output_dir: Directory containing {PMCID}_extraction.json files.

    Returns:
        Parsed extraction dict (v4 3-category structure), or empty dict
        if the file is not found or cannot be parsed.
    """
    ext_path = raw_output_dir / f"{pmcid}_extraction.json"                  #changed
    if not ext_path.exists():                                               #changed
        logging.warning("Raw extraction not found: %s", ext_path)          #changed
        return {}                                                           #changed

    with open(ext_path, "r", encoding="utf-8") as f:                       #changed
        data = json.load(f)                                                 #changed

    parsed = data.get("parsed_output", {})                                  #changed
    if not parsed:                                                          #changed
        logging.warning(                                                    #changed
            "%s: parsed_output is empty in extraction file", pmcid         #changed
        )                                                                   #changed
    return parsed                                                           #changed


# ===========================================================================
# DSPy LM configuration
# ===========================================================================

def configure_dspy_lm(model_key: str) -> None:
    """Configure DSPy language model from config.

    Resolves the model string from cfg.DSPY_MODEL_STRINGS and sets up
    the appropriate API key and parameters.

    Args:
        model_key: Key into cfg.DSPY_MODEL_STRINGS.
    """
    model_string = cfg.DSPY_MODEL_STRINGS[model_key]
    logging.info("Configuring DSPy LM: %s -> %s", model_key, model_string)

    # Determine API key based on model provider
    lm_kwargs = {
        "model": model_string,
        "max_tokens": 64000,
    }

    if model_string.startswith("anthropic/"):
        lm_kwargs["api_key"] = cfg.ANTHROPIC_API_KEY
        if not cfg.ANTHROPIC_API_KEY:
            logging.warning("ANTHROPIC_API_KEY is not set")

    elif model_string.startswith("bedrock/"):
        # Bedrock uses AWS credentials from environment
        os.environ.setdefault("AWS_ACCESS_KEY_ID", cfg.AWS_ACCESS_KEY_ID)
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", cfg.AWS_SECRET_ACCESS_KEY)
        os.environ.setdefault("AWS_DEFAULT_REGION", cfg.AWS_REGION_NAME)

    extraction_lm = dspy.LM(**lm_kwargs)
    dspy.configure(lm=extraction_lm)
    logging.info("DSPy LM configured successfully")


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """v4 baseline pipeline: extract, evaluate, report."""

    args = parse_args()

    # --- Output directory ---
    output_base = Path(cfg.DRIVE_BASE) / "assay" / "gt_diagnostic_analysis"
    output_dir = output_base / args.output_label
    raw_output_dir = output_dir / "raw_extractions"

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.output_label)
    logging.info("v4 baseline run starting")
    logging.info("Arguments: %s", vars(args))

    # --- Resolve directories ---
    gt_dir_main = Path(args.gt_dir) if args.gt_dir else Path(cfg.GROUND_TRUTH_PATH)
    xml_dir_main = Path(args.xml_dir) if args.xml_dir else Path(cfg.XML_PATH)
    gt_dir_golden = Path(cfg.GOLDEN_GT_PATH)
    xml_dir_golden = Path(cfg.XML_PATH) / "golden"

    logging.info("GT dir (main):   %s", gt_dir_main)
    logging.info("XML dir (main):  %s", xml_dir_main)
    logging.info("GT dir (golden): %s", gt_dir_golden)
    logging.info("XML dir (golden):%s", xml_dir_golden)
    logging.info("Output dir:      %s", output_dir)

    # --- Load PMCID list ---
    pmcid_list = load_pmcid_list(args.pmcid_list)
    logging.info("Loaded %d PMCIDs from %s", len(pmcid_list), args.pmcid_list)

    # --- Load golden PMCID set (optional explicit override) ---
    golden_explicit = set()
    if args.golden_pmcids:
        golden_explicit = set(load_pmcid_list(args.golden_pmcids))
        logging.info("Explicit golden PMCIDs loaded: %d", len(golden_explicit))

    # --- Build XML mappings ---
    xml_map_main = build_xml_mapping(xml_dir_main)
    xml_map_golden = build_xml_mapping(xml_dir_golden)
    logging.info("XML mappings: main=%d, golden=%d",
                 len(xml_map_main), len(xml_map_golden))

    # --- Resolve per-PMCID paths (main first, golden fallback) ---         #changed
    resolved = {}       # pmcid -> {"gt_dir": Path, "xml_path": Path}
    missing_xml = []
    missing_gt = []
    auto_golden = []    # PMCIDs resolved via golden fallback              #changed

    for pmcid in pmcid_list:
        gt_dir = None
        xml_path = None

        # If explicitly listed as golden, check golden first                #changed
        if pmcid in golden_explicit:
            if (gt_dir_golden / f"{pmcid}.json").exists():
                gt_dir = gt_dir_golden
            if pmcid in xml_map_golden:
                xml_path = xml_map_golden[pmcid]

        # Otherwise: check main first, then golden fallback                 #changed
        if gt_dir is None:
            if (gt_dir_main / f"{pmcid}.json").exists():
                gt_dir = gt_dir_main
            elif (gt_dir_golden / f"{pmcid}.json").exists():
                gt_dir = gt_dir_golden
                auto_golden.append(pmcid)

        if xml_path is None:
            if pmcid in xml_map_main:
                xml_path = xml_map_main[pmcid]
            elif pmcid in xml_map_golden:
                xml_path = xml_map_golden[pmcid]

        if gt_dir is None:
            missing_gt.append(pmcid)
        if xml_path is None:
            missing_xml.append(pmcid)

        if gt_dir is not None and xml_path is not None:
            resolved[pmcid] = {"gt_dir": gt_dir, "xml_path": xml_path}

    if auto_golden:                                                          #changed
        logging.info(
            "Auto-resolved %d PMCIDs from golden directories: %s",
            len(auto_golden), auto_golden[:10]
        )

    if missing_xml:
        logging.warning("PMCIDs missing XML (%d): %s",
                        len(missing_xml), missing_xml[:10])
    if missing_gt:
        logging.warning("PMCIDs missing GT (%d): %s",
                        len(missing_gt), missing_gt[:10])

    runnable = [p for p in pmcid_list if p in resolved]
    logging.info("Runnable PMCIDs: %d / %d", len(runnable), len(pmcid_list))

    # --- Pre-flight summary ---
    print(f"\n{'=' * 60}")
    print(f"  v4 BASELINE PRE-FLIGHT")
    print(f"{'=' * 60}")
    print(f"  Total PMCIDs:     {len(pmcid_list)}")
    print(f"  Resolved (main):  {len(runnable) - len(auto_golden)}")        #changed
    print(f"  Resolved (golden):{len(auto_golden)}")                         #changed
    print(f"  Missing XML:      {len(missing_xml)}")
    print(f"  Missing GT:       {len(missing_gt)}")
    print(f"  Runnable:         {len(runnable)}")
    print(f"  Model:            {args.model}")
    print(f"  Output:           {output_dir}")
    print(f"  Dry run:          {args.dry_run}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        logging.info("Dry run complete. Exiting without LLM calls.")
        return

    if not runnable:
        logging.error("No runnable PMCIDs. Aborting.")
        return

    # --- Determine run mode ---                                               #changed
    selective_pmcids = args.rerun_pmcids or args.rescore_only                   #changed
    is_rescore_only = args.rescore_only is not None                            #changed
    is_selective = selective_pmcids is not None                                 #changed

    # Expand 'ALL' keyword for --rescore-only (DD-2026-022)                    #changed
    if (is_selective                                                            #changed
            and len(selective_pmcids) == 1                                      #changed
            and selective_pmcids[0].upper() == "ALL"):                          #changed
        selective_pmcids = list(runnable)                                       #changed
        logging.info(                                                          #changed
            "ALL keyword: expanded to %d runnable PMCIDs", len(selective_pmcids)#changed
        )                                                                      #changed

    if is_selective:                                                            #changed
        mode_label = "RESCORE-ONLY" if is_rescore_only else "SELECTIVE RE-RUN" #changed
        logging.info(                                                          #changed
            "%s mode: %d PMCIDs targeted", mode_label, len(selective_pmcids)   #changed
        )                                                                      #changed

        # Validate that all targeted PMCIDs are in the runnable set             #changed
        not_runnable = [p for p in selective_pmcids if p not in resolved]       #changed
        if not_runnable:                                                        #changed
            logging.error(                                                     #changed
                "Targeted PMCIDs not resolvable (missing GT or XML): %s",      #changed
                not_runnable                                                   #changed
            )                                                                  #changed
            return                                                             #changed

        # Load existing results to merge into (empty dict is OK)               #changed
        existing_results = load_existing_results(output_dir)                   #changed
        if not existing_results:                                               #changed
            logging.warning(                                                   #changed
                "No existing results CSV at %s. "                              #changed
                "Starting from empty — all rescored PMCIDs will be fresh.",    #changed
                output_dir                                                     #changed
            )                                                                  #changed
            existing_results = {}                                              #changed

        # Process only the targeted PMCIDs                                     #changed
        target_set = set(selective_pmcids)                                      #changed
        run_list = [p for p in runnable if p in target_set]                     #changed
    else:                                                                      #changed
        run_list = runnable                                                    #changed

    # --- Configure DSPy LM (skip for rescore-only) ---                        #changed
    if not is_rescore_only:                                                     #changed
        configure_dspy_lm(args.model)

    # --- Run extraction + evaluation ---
    if not is_rescore_only:                                                     #changed
        extractor = AssayExtractor()
    results = []
    failed_pmcids = []

    start_time = time.time()

    for i, pmcid in enumerate(run_list):
        if (i + 1) % 10 == 0 or (i + 1) == len(run_list):                     #changed
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logging.info(
                "Progress: %d/%d (%.1f docs/min)",
                i + 1, len(run_list), rate * 60                                #changed
            )

        # Use pre-resolved paths                                              #changed
        pmcid_paths = resolved[pmcid]
        gt_dir = pmcid_paths["gt_dir"]
        xml_path = pmcid_paths["xml_path"]

        # Load GT (always needed for scoring)                                  #changed
        gt_data = load_ground_truth(pmcid, gt_dir)

        if gt_data is None:
            logging.warning("Skipping %s: GT is None after loading", pmcid)
            continue

        # --- Get extraction data ---                                          #changed
        raw_output = ""                                                        #changed
        ext_data = {}                                                          #changed

        if is_rescore_only:                                                    #changed
            # Load existing extraction from disk                               #changed
            ext_data = load_raw_extraction(pmcid, raw_output_dir)              #changed
            if not ext_data:                                                   #changed
                logging.warning(                                               #changed
                    "Skipping %s: no existing extraction for rescore", pmcid   #changed
                )                                                              #changed
                continue                                                       #changed
            logging.info(                                                      #changed
                "%s: rescoring from existing extraction", pmcid                #changed
            )                                                                  #changed
        else:                                                                  #changed
            # Run LLM extraction with retry (DD-2026-021)                      #changed
            article_text = load_article_text(xml_path, max_chars=args.max_chars)

            max_retries = args.max_retries                                     #changed
            attempt = 0                                                        #changed
            extraction_ok = False                                              #changed
            exception_abort = False                                            #changed

            while attempt < max_retries and not extraction_ok:                 #changed
                attempt += 1                                                   #changed
                try:
                    prediction = extractor(article_text=article_text)
                    raw_output = prediction.assay_info

                    # --- Silent failure check ---                             #changed
                    if raw_output is None or str(raw_output).strip() == "":    #changed
                        logging.warning(                                       #changed
                            "%s: empty output (attempt %d/%d)",                #changed
                            pmcid, attempt, max_retries                        #changed
                        )                                                      #changed
                        raw_output = ""                                        #changed
                        if attempt < max_retries:                              #changed
                            time.sleep(args.delay * 2)                         #changed
                            continue                                           #changed
                        break  # last attempt, exit with extraction_ok=False   #changed

                    # --- Self-truncation warning (informational) ---          #changed
                    if (raw_output                                             #changed
                            and (raw_output.rstrip().endswith("...")            #changed
                                 or "will be extremely" in raw_output)):        #changed
                        logging.warning(                                       #changed
                            "%s: self-truncated output (%d chars, "            #changed
                            "attempt %d/%d)",                                  #changed
                            pmcid, len(raw_output), attempt, max_retries       #changed
                        )                                                      #changed

                    # --- Parse and check for usable data ---                  #changed
                    ext_data = parse_extraction_output(raw_output)

                    if ext_data == EMPTY_RESULT and raw_output.strip() != "":  #changed
                        # JSON present but unparseable (truncation)            #changed
                        tail = raw_output[-300:] if len(raw_output) > 300 \
                            else raw_output                                    #changed
                        logging.warning(                                       #changed
                            "%s: parse failed (attempt %d/%d). "               #changed
                            "Tail: ...%s",                                     #changed
                            pmcid, attempt, max_retries, tail                  #changed
                        )                                                      #changed
                        if attempt < max_retries:                              #changed
                            time.sleep(args.delay * 2)                         #changed
                            continue                                           #changed
                        break  # last attempt, exit with extraction_ok=False   #changed

                    extraction_ok = True                                       #changed

                except Exception as e:
                    logging.error(                                             #changed
                        "%s: exception on attempt %d/%d: %s",                  #changed
                        pmcid, attempt, max_retries, str(e)                    #changed
                    )                                                          #changed
                    if attempt < max_retries:                                  #changed
                        time.sleep(args.delay * 2)                             #changed
                        continue                                               #changed
                    # Final attempt exception — record error and skip scoring  #changed
                    result = RecordResult(                                     #changed
                        pmcid=pmcid, error_message=str(e)                     #changed
                    )                                                          #changed
                    results.append(result)                                     #changed
                    failed_pmcids.append(pmcid)                               #changed
                    exception_abort = True                                     #changed
                    break                                                      #changed

            # Skip save/score if exception aborted the loop                    #changed
            if exception_abort:                                                #changed
                time.sleep(args.delay)                                         #changed
                continue                                                       #changed

            # --- Post-retry: log final failure ---                            #changed
            if not extraction_ok:                                              #changed
                tail = raw_output[-300:] if len(raw_output) > 300 \
                    else raw_output                                            #changed
                logging.warning(                                               #changed
                    "%s: FAILED after %d attempts. "                           #changed
                    "raw_output length=%d, tail: ...%s",                       #changed
                    pmcid, max_retries, len(raw_output), tail                  #changed
                )                                                              #changed
                failed_pmcids.append(pmcid)                                   #changed

            # Save whatever we got (even if failed — aids diagnosis)           #changed
            save_raw_extraction(pmcid, raw_output, ext_data, raw_output_dir)

        # Score
        result = score_record(
            pmcid=pmcid,
            gt_data=gt_data,
            ext_data=ext_data,
        )
        results.append(result)

        logging.debug(
            "%s: cat=%s->%s  F1=%.3f  TP=%d FP=%d FN=%d",
            pmcid, result.gt_category, result.ext_category,
            result.primary_f1, result.tp, result.fp, result.fn
        )

        if not is_rescore_only:                                                #changed
            time.sleep(args.delay)

    # --- Merge results for selective modes ---                                #changed
    elapsed_total = time.time() - start_time

    if is_selective:                                                            #changed
        # Replace targeted PMCIDs in existing results                          #changed
        for result in results:                                                 #changed
            existing_results[result.pmcid] = result                            #changed
            logging.info(                                                      #changed
                "  Updated %s: F1=%.3f (TP=%d FP=%d FN=%d)",                  #changed
                result.pmcid, result.primary_f1,                               #changed
                result.tp, result.fp, result.fn                                #changed
            )                                                                  #changed

        # Build merged list preserving original PMCID order from full list     #changed
        merged_results = []                                                    #changed
        for pmcid in pmcid_list:                                               #changed
            if pmcid in existing_results:                                      #changed
                merged_results.append(existing_results[pmcid])                 #changed
        results = merged_results                                               #changed

        logging.info(                                                          #changed
            "%s complete: %d PMCIDs updated, %d total results, %.1f seconds", #changed
            mode_label, len(selective_pmcids),                                 #changed
            len(results), elapsed_total                                        #changed
        )                                                                      #changed
    else:                                                                      #changed
        logging.info(
            "Extraction complete: %d/%d succeeded, %d failed, %.1f minutes",
            len(results) - len(failed_pmcids),
            len(runnable),
            len(failed_pmcids),
            elapsed_total / 60,
        )

    # --- Generate report (always from full result set) ---                    #changed
    generate_report(
        results=results,
        output_dir=output_dir,
        run_label=args.output_label,
        model_name=args.model,
    )

    logging.info("v4 baseline run complete. Output: %s", output_dir)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
