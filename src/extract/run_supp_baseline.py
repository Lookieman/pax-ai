"""
run_supp_baseline.py
====================
Supplementary extraction baseline: extract assay information from
article text + supplementary files (images, spreadsheets, PDFs, DOCX)
and evaluate against supplementary ground truth.

This script targets the supplementary set-aside records --- articles whose
assay data resides in supplementary materials rather than the article body.
It uses the same evaluation pipeline (scorer, metric, report) as the
article-only v4 baseline.

Usage:
    python run_supp_baseline.py --pmcid-list path/to/supp_pmcids.txt
    python run_supp_baseline.py --pmcid-list supp_pmcids.txt --model claude-haiku-4.5 --dry-run
    python run_supp_baseline.py --pmcid-list supp_pmcids.txt --golden-pmcids golden_supp.txt

Output is written to:
    <DRIVE_BASE>/assay/gt_diagnostic_analysis/<output-label>/

Requires:
    pip install attachments[office]

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-016
"""

import sys
import os
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
from extract.supp_loader import (                                              # noqa: E402
    discover_supp_files,
    load_attachments,
    build_supp_file_manifest,
)
from extract.extractor import (                                                # noqa: E402
    SupplementaryAssayExtractor,
    parse_extraction_output,
)
from evaluate.scorer import score_record, RecordResult                          # noqa: E402
from evaluate.report import generate_report                                     # noqa: E402


# ===========================================================================
# Logging setup
# ===========================================================================

def setup_logging(log_dir: Path, run_label: str) -> None:
    """Configure logging to both console and file."""
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
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Supplementary baseline: extract assay information from "
            "article text + supplementary files and evaluate against GT."
        )
    )

    parser.add_argument(
        "--pmcid-list",
        type=Path,
        required=True,
        help="Path to text file with one PMCID per line (supp set-aside records).",
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
        default="v4_supp_baseline",
        help="Subdirectory name under gt_diagnostic_analysis/ (default: v4_supp_baseline).",
    )
    parser.add_argument(
        "--gt-dir",
        type=Path,
        default=None,
        help="Override supp GT directory (default: config SUPP_GT_PATH).",
    )
    parser.add_argument(
        "--xml-dir",
        type=Path,
        default=None,
        help="Override XML directory (default: config XML_PATH).",
    )
    parser.add_argument(
        "--supp-dir",
        type=Path,
        default=None,
        help="Override supplementary files directory (default: config SUPPLEMENTARY_PATH).",
    )
    parser.add_argument(
        "--attach-dir",
        type=Path,
        default=None,
        help="Override attachments directory (default: config ATTACHMENTS_PATH).",
    )
    parser.add_argument(
        "--golden-pmcids",
        type=Path,
        default=None,
        help="Optional file listing golden supp PMCIDs (uses golden supp GT dir).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and report file manifest only; no LLM calls.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between API calls (default: 2.0; higher due to multimodal cost).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=100000,
        help="Maximum article text length before truncation (default: 100000).",
    )

    return parser.parse_args()


# ===========================================================================
# Raw output saving
# ===========================================================================

def save_raw_extraction(
    pmcid: str,
    raw_output: str,
    parsed_output: dict,
    file_manifest: dict,
    output_dir: Path,
) -> None:
    """Save raw and parsed LLM output plus file manifest for reproducibility."""
    output_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pmcid": pmcid,
        "timestamp": datetime.now().isoformat(),
        "file_manifest": file_manifest,
        "raw_output": raw_output,
        "parsed_output": parsed_output,
    }
    filepath = output_dir / f"{pmcid}_supp_extraction.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


# ===========================================================================
# DSPy LM configuration (reused from run_baseline.py)
# ===========================================================================

def configure_dspy_lm(model_key: str) -> None:
    """Configure DSPy language model from config."""
    model_string = cfg.DSPY_MODEL_STRINGS[model_key]
    logging.info("Configuring DSPy LM: %s -> %s", model_key, model_string)

    lm_kwargs = {
        "model": model_string,
        "max_tokens": 64000,
    }

    if model_string.startswith("anthropic/"):
        lm_kwargs["api_key"] = cfg.ANTHROPIC_API_KEY
        if not cfg.ANTHROPIC_API_KEY:
            logging.warning("ANTHROPIC_API_KEY is not set")

    elif model_string.startswith("bedrock/"):
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
    """Supplementary extraction pipeline: extract, evaluate, report."""

    args = parse_args()

    # --- Output directory ---
    output_base = Path(cfg.DRIVE_BASE) / "assay" / "gt_diagnostic_analysis"
    output_dir = output_base / args.output_label
    raw_output_dir = output_dir / "raw_extractions"

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.output_label)
    logging.info("Supplementary baseline run starting")
    logging.info("Arguments: %s", vars(args))

    # --- Resolve directories ---
    gt_dir_main = Path(args.gt_dir) if args.gt_dir else Path(cfg.SUPP_GT_PATH)
    gt_dir_golden = Path(cfg.SUPP_GOLDEN_GT_PATH)
    xml_dir_main = Path(args.xml_dir) if args.xml_dir else Path(cfg.XML_PATH)
    xml_dir_golden = Path(cfg.XML_PATH) / "golden"
    supp_dir = Path(args.supp_dir) if args.supp_dir else Path(cfg.SUPPLEMENTARY_PATH)
    attach_dir = Path(args.attach_dir) if args.attach_dir else Path(cfg.ATTACHMENTS_PATH)

    logging.info("GT dir (supp main):    %s", gt_dir_main)
    logging.info("GT dir (supp golden):  %s", gt_dir_golden)
    logging.info("XML dir (main):        %s", xml_dir_main)
    logging.info("Supplementary dir:     %s", supp_dir)
    logging.info("Attachments dir:       %s", attach_dir)
    logging.info("Output dir:            %s", output_dir)

    # --- Load PMCID list ---
    pmcid_list = load_pmcid_list(args.pmcid_list)
    logging.info("Loaded %d PMCIDs from %s", len(pmcid_list), args.pmcid_list)

    # --- Load golden PMCID set (optional explicit override) ---
    golden_explicit = set()
    if args.golden_pmcids:
        golden_explicit = set(load_pmcid_list(args.golden_pmcids))
        logging.info("Explicit golden supp PMCIDs loaded: %d", len(golden_explicit))

    # --- Build XML mappings ---
    xml_map_main = build_xml_mapping(xml_dir_main)
    xml_map_golden = build_xml_mapping(xml_dir_golden)
    logging.info("XML mappings: main=%d, golden=%d",
                 len(xml_map_main), len(xml_map_golden))

    # --- Resolve per-PMCID paths (main first, golden fallback) ---         #changed
    resolved = {}       # pmcid -> {"gt_dir": Path, "xml_path": Path}
    missing_xml = []
    missing_gt = []
    missing_supp = []
    auto_golden = []
    manifests = {}

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

        # Check supplementary files (independent of GT/XML resolution)
        supp_files = discover_supp_files(pmcid, supp_dir, attach_dir)
        if not supp_files:
            missing_supp.append(pmcid)

        manifests[pmcid] = build_supp_file_manifest(pmcid, supp_dir, attach_dir)

        if gt_dir is not None and xml_path is not None and supp_files:
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
    if missing_supp:
        logging.warning("PMCIDs missing supp files (%d): %s",
                        len(missing_supp), missing_supp[:10])

    runnable = [p for p in pmcid_list if p in resolved]
    logging.info("Runnable PMCIDs: %d / %d", len(runnable), len(pmcid_list))

    # --- File type summary ---
    ext_counts = {}
    total_files = 0
    for m in manifests.values():
        for f_info in m["supp_files"] + m["attach_files"]:
            ext = f_info["ext"]
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            total_files += 1

    # --- Pre-flight summary ---
    print(f"\n{'=' * 60}")
    print(f"  SUPPLEMENTARY BASELINE PRE-FLIGHT")
    print(f"{'=' * 60}")
    print(f"  Total PMCIDs:        {len(pmcid_list)}")
    print(f"  Resolved (main):     {len(runnable) - len(auto_golden)}")      #changed
    print(f"  Resolved (golden):   {len(auto_golden)}")                       #changed
    print(f"  Missing XML:         {len(missing_xml)}")
    print(f"  Missing GT:          {len(missing_gt)}")
    print(f"  Missing supp files:  {len(missing_supp)}")
    print(f"  Runnable:            {len(runnable)}")
    print(f"  Total supp files:    {total_files}")
    print(f"  Model:               {args.model}")
    print(f"  Output:              {output_dir}")
    print(f"  Dry run:             {args.dry_run}")
    print(f"\n  --- File Type Distribution ---")
    for ext in sorted(ext_counts.keys()):
        print(f"    {ext:>6}: {ext_counts[ext]}")
    print(f"{'=' * 60}\n")

    # Save manifests for audit
    manifest_path = output_dir / "supp_file_manifests.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifests, f, indent=2, ensure_ascii=False)
    logging.info("File manifests saved: %s", manifest_path)

    if args.dry_run:
        logging.info("Dry run complete. Exiting without LLM calls.")
        return

    if not runnable:
        logging.error("No runnable PMCIDs. Aborting.")
        return

    # --- Configure DSPy LM ---
    configure_dspy_lm(args.model)

    # --- Run extraction + evaluation ---
    extractor = SupplementaryAssayExtractor()
    results = []
    failed_pmcids = []

    start_time = time.time()

    for i, pmcid in enumerate(runnable):
        if (i + 1) % 5 == 0 or (i + 1) == len(runnable):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logging.info(
                "Progress: %d/%d (%.1f docs/min)",
                i + 1, len(runnable), rate * 60
            )

        # Determine directories
        # Use pre-resolved paths                                              #changed
        pmcid_paths = resolved[pmcid]
        gt_dir = pmcid_paths["gt_dir"]
        xml_path = pmcid_paths["xml_path"]

        # Load article text
        article_text = load_article_text(xml_path, max_chars=args.max_chars)

        # Load ground truth
        gt_data = load_ground_truth(pmcid, gt_dir)
        if gt_data is None:
            logging.warning("Skipping %s: GT is None after loading", pmcid)
            continue

        # Load supplementary files via attachments library
        supp_files = discover_supp_files(pmcid, supp_dir, attach_dir)
        try:
            attachments_obj = load_attachments(supp_files)
            supplementary_content = str(attachments_obj)                        #changed: text repr for signature
        except Exception as e:
            logging.error(
                "Failed to load attachments for %s: %s", pmcid, str(e)
            )
            result = RecordResult(
                pmcid=pmcid,
                error_message=f"Attachment loading failed: {str(e)}",
            )
            results.append(result)
            failed_pmcids.append(pmcid)
            time.sleep(args.delay)
            continue

        logging.info(
            "%s: article=%d chars, supp=%d chars, %d files",
            pmcid,
            len(article_text),
            len(supplementary_content),
            len(supp_files),
        )

        # Extract
        raw_output = ""
        ext_data = {}
        try:
            prediction = extractor(
                article_text=article_text,
                supplementary_content=supplementary_content,
            )
            raw_output = prediction.assay_info
            ext_data = parse_extraction_output(raw_output)
        except Exception as e:
            logging.error("Extraction failed for %s: %s", pmcid, str(e))
            result = RecordResult(pmcid=pmcid, error_message=str(e))
            results.append(result)
            failed_pmcids.append(pmcid)
            time.sleep(args.delay)
            continue

        # Save raw output with file manifest
        save_raw_extraction(
            pmcid, raw_output, ext_data, manifests.get(pmcid, {}), raw_output_dir
        )

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

        time.sleep(args.delay)

    # --- Generate report ---
    elapsed_total = time.time() - start_time
    logging.info(
        "Extraction complete: %d/%d succeeded, %d failed, %.1f minutes",
        len(results) - len(failed_pmcids),
        len(runnable),
        len(failed_pmcids),
        elapsed_total / 60,
    )

    generate_report(
        results=results,
        output_dir=output_dir,
        run_label=args.output_label,
        model_name=args.model,
    )

    logging.info("Supplementary baseline run complete. Output: %s", output_dir)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
