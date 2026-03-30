"""
run_holdout.py
==============
Run holdout inference using a GEPA-optimised programme and evaluate
against ground truth.

Loads the optimised programme saved by run_gepa.py and runs it on
the holdout test set, producing per-record results and a summary
report identical in format to run_baseline.py output.

Usage:
    python run_holdout.py --programme path/to/optimised_programme.json
    python run_holdout.py --programme path/to/optimised_programme.json --dry-run
    python run_holdout.py --programme path/to/optimised_programme.json --output-label gepa_holdout_100pct

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-018
"""

import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path resolution: ensure src/ is on sys.path
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import cfg                                                         # noqa: E402

import dspy                                                                    # noqa: E402

from extract.article_loader import load_article_text, load_ground_truth        # noqa: E402
from extract.extractor import AssayExtractor, parse_extraction_output          # noqa: E402
from evaluate.scorer import score_record, RecordResult                         # noqa: E402
from evaluate.report import generate_report                                    # noqa: E402
from optimise.data_loader import load_splits, build_datasets                   # noqa: E402


# ===========================================================================
# Logging setup
# ===========================================================================

def setup_logging(log_dir: Path, run_label: str) -> None:
    """Configure logging to both console and file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"holdout_{run_label}_{timestamp}.log"

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
        description="Holdout inference with GEPA-optimised programme (DD-2026-018)."
    )

    parser.add_argument(
        "--programme",
        type=Path,
        required=True,
        help="Path to the GEPA-optimised programme JSON.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-6",
        choices=list(cfg.DSPY_MODEL_STRINGS.keys()),
        help="Model key for inference (must match the student model used in GEPA).",
    )
    parser.add_argument(
        "--output-label",
        type=str,
        default="gepa_holdout",
        help="Subdirectory name under gt_diagnostic_analysis/ (default: gepa_holdout).",
    )
    parser.add_argument(
        "--splits-file",
        type=Path,
        default=None,
        help="Override path to splits JSON (default: from config).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between API calls (default: 1.5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs only; no LLM calls.",
    )

    return parser.parse_args()


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Holdout inference pipeline: load programme, run, evaluate, report."""

    args = parse_args()

    # --- Output directory ---
    output_base = Path(cfg.DRIVE_BASE) / "assay" / "gt_diagnostic_analysis"
    output_dir = output_base / args.output_label
    raw_output_dir = output_dir / "raw_extractions"

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.output_label)
    logging.info("Holdout inference starting")
    logging.info("Arguments: %s", vars(args))

    # --- Load splits ---
    splits_filepath = args.splits_file or Path(cfg.GEPA_SPLITS_FILE)           #changed
    splits = load_splits(splits_filepath)

    # --- Build holdout dataset ---
    logging.info("Building holdout dataset...")
    _, _, holdout_set = build_datasets(
        splits=splits,
        cfg=cfg,
        split_pct=100,
    )

    logging.info("Holdout set: %d records", len(holdout_set))

    # --- Pre-flight summary ---
    print(f"\n{'=' * 60}")
    print(f"  HOLDOUT INFERENCE PRE-FLIGHT")
    print(f"{'=' * 60}")
    print(f"  Programme:        {args.programme}")
    print(f"  Holdout records:  {len(holdout_set)}")
    print(f"  Model:            {args.model}")
    print(f"  Output:           {output_dir}")
    print(f"  Dry run:          {args.dry_run}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        logging.info("Dry run complete. Exiting without LLM calls.")
        return

    # --- Configure DSPy LM ---
    model_string = cfg.DSPY_MODEL_STRINGS[args.model]
    lm_kwargs = {"model": model_string, "max_tokens": 64000}

    if model_string.startswith("anthropic/"):
        lm_kwargs["api_key"] = cfg.ANTHROPIC_API_KEY

    student_lm = dspy.LM(**lm_kwargs)
    dspy.configure(lm=student_lm)
    logging.info("LM configured: %s", model_string)

    # --- Load optimised programme ---
    logging.info("Loading optimised programme from %s", args.programme)
    extractor = AssayExtractor()
    extractor.load(str(args.programme))
    logging.info("Optimised programme loaded successfully")

    # --- Print the evolved prompt ---
    try:
        predictors = extractor.predictors()
        if predictors:
            evolved = predictors[0].signature.instructions
            logging.info("Evolved prompt (first 200 chars): %s", evolved[:200])
    except Exception as e:
        logging.warning("Could not inspect evolved prompt: %s", e)

    # --- Run inference on holdout ---
    results = []
    failed_pmcids = []
    start_time = time.time()

    for i, example in enumerate(holdout_set):
        pmcid = example.pmcid
        article_text = example.article_text
        gt_data = json.loads(example.gt_json)

        if (i + 1) % 10 == 0 or (i + 1) == len(holdout_set):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logging.info(
                "Progress: %d/%d (%.1f docs/min)",
                i + 1, len(holdout_set), rate * 60,
            )

        # Extract
        raw_output = ""
        ext_data = {}
        try:
            prediction = extractor(article_text=article_text)
            raw_output = prediction.assay_info
            ext_data = parse_extraction_output(raw_output)
        except Exception as e:
            logging.error("Extraction failed for %s: %s", pmcid, str(e))
            result = RecordResult(pmcid=pmcid, error_message=str(e))
            results.append(result)
            failed_pmcids.append(pmcid)
            time.sleep(args.delay)
            continue

        # Save raw output
        raw_output_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "pmcid": pmcid,
            "timestamp": datetime.now().isoformat(),
            "raw_output": raw_output,
            "parsed_output": ext_data,
        }
        filepath = raw_output_dir / f"{pmcid}_extraction.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

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
            result.primary_f1, result.tp, result.fp, result.fn,
        )

        time.sleep(args.delay)

    # --- Generate report ---
    elapsed_total = time.time() - start_time
    logging.info(
        "Inference complete: %d/%d succeeded, %d failed, %.1f minutes",
        len(results) - len(failed_pmcids),
        len(holdout_set),
        len(failed_pmcids),
        elapsed_total / 60,
    )

    generate_report(
        results=results,
        output_dir=output_dir,
        run_label=args.output_label,
        model_name=args.model,
    )

    logging.info("Holdout inference complete. Output: %s", output_dir)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
