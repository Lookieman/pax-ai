"""
run_holdout.py (AICORE BRANCH)
===============================
Run holdout inference using a GEPA-optimised programme via SAP AI Core.
Also supports cross-pathogen inference with custom PMCID lists and
data directories.

Changes from main branch:
- Uses AICoreLanguageModel instead of dspy.LM
- Adds --service-key for AI Core authentication
- Adds --quiet mode
- Adds --pmcid-list, --xml-dir, --gt-dir for cross-pathogen inference
- --programme is now optional (defaults to CoT baseline when omitted)

Usage:
    python optimise/run_holdout.py -k path/to/sk.json --programme path/to/optimised.json
    python optimise/run_holdout.py -k path/to/sk.json --programme path/to/optimised.json --quiet
    python optimise/run_holdout.py -k path/to/sk.json --programme path/to/optimised.json --dry-run

    # Cross-pathogen baseline (no programme = default CoT):
    python optimise/run_holdout.py -k path/to/sk.json --pmcid-list hepa_pmcids.txt --xml-dir path/to/xml --gt-dir path/to/gt --output-label v5_cross_pathogen_baseline_sonnet45

    # Cross-pathogen with Salmonella-optimised prompt:
    python optimise/run_holdout.py -k path/to/sk.json --pmcid-list hepa_pmcids.txt --xml-dir path/to/xml --gt-dir path/to/gt --programme path/to/optimised.json --output-label v5_cross_pathogen_gepa_sonnet45

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Branch: aicore
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
from extract.article_loader import load_pmcid_list, build_xml_mapping          # noqa: E402  #changed_120426
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
        description="Holdout inference with GEPA-optimised programme via AI Core (DD-2026-018)."
    )

    parser.add_argument(
        "--programme",
        type=Path,
        default=None,                                                          #changed_120426
        help="Path to the GEPA-optimised programme JSON. When omitted, "       #changed_120426
             "uses default CoT (baseline inference).",                         #changed_120426
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-4.5-sonnet",
        help="Model key for inference (default: claude-4.5-sonnet).",
    )
    parser.add_argument(
        "--output-label",
        type=str,
        default="gepa_holdout",
        help="Subdirectory name under assay/gt_diagnostic_analysis/ (default: gepa_holdout).",
    )
    parser.add_argument(
        "--splits-file",
        type=Path,
        default=None,
        help="Override path to splits JSON (default: from config).",
    )
    parser.add_argument(                                                       #changed_120426
        "--pmcid-list",                                                        #changed_120426
        type=Path,                                                             #changed_120426
        default=None,                                                          #changed_120426
        help="Path to text file with one PMCID per line. When provided, "      #changed_120426
             "overrides the splits-based holdout set (e.g. for cross-pathogen "#changed_120426
             "inference). Requires --xml-dir and --gt-dir.",                    #changed_120426
    )                                                                          #changed_120426
    parser.add_argument(                                                       #changed_120426
        "--xml-dir",                                                           #changed_120426
        type=Path,                                                             #changed_120426
        default=None,                                                          #changed_120426
        help="Override XML article directory (for cross-pathogen inference).",  #changed_120426
    )                                                                          #changed_120426
    parser.add_argument(                                                       #changed_120426
        "--gt-dir",                                                            #changed_120426
        type=Path,                                                             #changed_120426
        default=None,                                                          #changed_120426
        help="Override ground truth directory (for cross-pathogen inference).", #changed_120426
    )                                                                          #changed_120426
    parser.add_argument(                                                       #changed
        "--service-key", "-k",                                                 #changed
        type=str,                                                              #changed
        default=None,                                                          #changed
        help="Path to SAP AI Core service key JSON file.",                     #changed
    )                                                                          #changed
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
    parser.add_argument(                                                       #changed
        "--quiet", "-q",                                                       #changed
        action="store_true",                                                   #changed
        help="Suppress DSPy's internal INFO logs from console.",               #changed
    )                                                                          #changed
    parser.add_argument(                                                       #changed_08042026
        "--no-resume",                                                         #changed_08042026
        action="store_true",                                                   #changed_08042026
        help="Force a clean run, ignoring any previously completed "           #changed_08042026
             "extractions in the output directory.",                            #changed_08042026
    )                                                                          #changed_08042026
    parser.add_argument(                                                       #changed_16042026
        "--no-cot",                                                            #changed_16042026
        action="store_true",                                                   #changed_16042026
        help="Use dspy.Predict instead of dspy.ChainOfThought. "               #changed_16042026
             "Produces a zero-shot Predict baseline for ablation.",            #changed_16042026
    )                                                                          #changed_16042026

    return parser.parse_args()


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Holdout inference pipeline via SAP AI Core."""

    args = parse_args()

    # --- Output directory ---
    output_base = Path(cfg.DRIVE_BASE) / "assay" / "gt_diagnostic_analysis"
    output_dir = output_base / args.output_label
    raw_output_dir = output_dir / "raw_extractions"

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.output_label)
    logging.info("Holdout inference starting (AICORE BRANCH)")                 #changed
    logging.info("Arguments: %s", vars(args))

    # --- Quiet mode ---                                                       #changed
    if args.quiet:                                                             #changed
        for _name in ("dspy", "dspy.evaluate", "dspy.teleprompt",              #changed
                      "dspy.teleprompt.gepa", "dspy.teleprompt.gepa.gepa",     #changed
                      "litellm", "httpx"):                                     #changed
            logging.getLogger(_name).setLevel(logging.WARNING)                 #changed
        logging.info("Quiet mode enabled")                                     #changed

    # --- Load AI Core credentials ---                                         #changed
    if args.service_key:                                                       #changed
        from aicore.aicore_lm import set_service_key                           #changed_020426
        set_service_key(args.service_key)                                      #changed_020426
        logging.info("AI Core credentials loaded from %s", args.service_key)   #changed
    else:                                                                      #changed
        cfg.load_service_key_if_exists()                                       #changed

    # --- Build holdout dataset ---                                             #changed_120426
    if args.pmcid_list:                                                        #changed_120426
        # Cross-pathogen / custom PMCID list path                              #changed_120426
        if not args.xml_dir or not args.gt_dir:                                #changed_120426
            logging.error(                                                     #changed_120426
                "--pmcid-list requires both --xml-dir and --gt-dir"            #changed_120426
            )                                                                  #changed_120426
            sys.exit(1)                                                        #changed_120426
                                                                               #changed_120426
        pmcid_list = load_pmcid_list(args.pmcid_list)                          #changed_120426
        xml_map = build_xml_mapping(args.xml_dir)                              #changed_120426
        logging.info(                                                          #changed_120426
            "Custom PMCID list: %d PMCIDs, %d XML files found",               #changed_120426
            len(pmcid_list), len(xml_map),                                     #changed_120426
        )                                                                      #changed_120426
                                                                               #changed_120426
        holdout_set = []                                                       #changed_120426
        skipped_missing = []                                                   #changed_120426
        for pmcid in pmcid_list:                                               #changed_120426
            if pmcid not in xml_map:                                           #changed_120426
                logging.warning("No XML found for %s, skipping", pmcid)        #changed_120426
                skipped_missing.append(pmcid)                                  #changed_120426
                continue                                                       #changed_120426
            gt_path = args.gt_dir / f"{pmcid}.json"                            #changed_120426
            if not gt_path.exists():                                           #changed_120426
                logging.warning("No GT found for %s, skipping", pmcid)         #changed_120426
                skipped_missing.append(pmcid)                                  #changed_120426
                continue                                                       #changed_120426
            article_text = load_article_text(                                  #changed_120426
                xml_map[pmcid], max_chars=100000                               #changed_120426
            )                                                                  #changed_120426
            gt_data = load_ground_truth(pmcid, args.gt_dir)                    #changed_120426
            example = dspy.Example(                                            #changed_120426
                pmcid=pmcid,                                                   #changed_120426
                article_text=article_text,                                     #changed_120426
                gt_json=json.dumps(gt_data, ensure_ascii=False),               #changed_120426
            ).with_inputs("article_text")                                      #changed_120426
            holdout_set.append(example)                                        #changed_120426
        if skipped_missing:                                                    #changed_120426
            logging.warning(                                                   #changed_120426
                "Skipped %d PMCIDs (missing XML or GT): %s",                   #changed_120426
                len(skipped_missing), skipped_missing,                         #changed_120426
            )                                                                  #changed_120426
    else:                                                                      #changed_120426
        # Standard Salmonella holdout path via splits file                     #changed_120426
        splits_filepath = args.splits_file or Path(cfg.GEPA_SPLITS_FILE)
        splits = load_splits(splits_filepath)

        logging.info("Building holdout dataset...")
        _, _, holdout_set = build_datasets(
            splits=splits,
            cfg=cfg,
            split_pct=100,
        )

    logging.info("Holdout set: %d records", len(holdout_set))

    # --- Pre-flight summary ---
    print(f"\n{'=' * 60}")
    print(f"  HOLDOUT INFERENCE PRE-FLIGHT (AICORE)")                          #changed
    print(f"{'=' * 60}")
    print(f"  Programme:        {args.programme or '(default CoT)'}")            #changed_120426
    print(f"  CoT mode:         {'Predict (ablation)' if args.no_cot else 'ChainOfThought'}")  #changed_16042026
    print(f"  Holdout records:  {len(holdout_set)}")
    print(f"  Model:            {args.model}")
    if args.pmcid_list:                                                        #changed_120426
        print(f"  PMCID list:       {args.pmcid_list}")                        #changed_120426
        print(f"  XML dir:          {args.xml_dir}")                           #changed_120426
        print(f"  GT dir:           {args.gt_dir}")                            #changed_120426
    print(f"  Output:           {output_dir}")
    print(f"  Quiet mode:       {args.quiet}")                                 #changed
    print(f"  Dry run:          {args.dry_run}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        logging.info("Dry run complete. Exiting without LLM calls.")
        return

    # --- Configure AI Core LM ---                                             #changed
    from aicore.aicore_lm import AICoreLanguageModel                           #changed

    model_name = cfg.resolve_model(args.model)                                 #changed_020426
    student_lm = AICoreLanguageModel(                                          #changed
        model_name=model_name,                                                 #changed_020426
        temperature=0.0,                                                       #changed
        max_tokens=64000,                                                      #changed
    )                                                                          #changed
    dspy.configure(lm=student_lm)                                              #changed
    logging.info("LM (AI Core): %s", model_name)                              #changed_020426

    # --- Load optimised programme or default CoT ---                           #changed_120426
    extractor = AssayExtractor(use_cot=not args.no_cot)                        #changed_16042026
    if args.programme:                                                         #changed_120426
        logging.info("Loading optimised programme from %s", args.programme)
        extractor.load(str(args.programme))                                    #changed_120426
        logging.info("Optimised programme loaded successfully")
    else:                                                                      #changed_120426
        logging.info("Using default CoT extractor (no programme provided)")    #changed_120426

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
    skipped_pmcids = []                                                        #changed_08042026
    start_time = time.time()

    # --- Resume: detect previously completed extractions ---                  #changed_08042026
    completed_pmcids = set()                                                   #changed_08042026
    if not args.no_resume:                                                     #changed_08042026
        raw_output_dir.mkdir(parents=True, exist_ok=True)                      #changed_08042026
        for existing in raw_output_dir.glob("*_extraction.json"):              #changed_08042026
            completed_pmcids.add(existing.stem.replace("_extraction", ""))     #changed_08042026
        if completed_pmcids:                                                   #changed_08042026
            logging.info(                                                      #changed_08042026
                "Resume mode: found %d completed extractions in %s",           #changed_08042026
                len(completed_pmcids), raw_output_dir,                         #changed_08042026
            )                                                                  #changed_08042026
    else:                                                                      #changed_08042026
        logging.info("No-resume mode: all records will be re-extracted")       #changed_08042026

    for i, example in enumerate(holdout_set):
        pmcid = example.pmcid
        article_text = example.article_text
        gt_data = json.loads(example.gt_json)

        # --- Resume: skip already-completed records ---                       #changed_08042026
        if pmcid in completed_pmcids:                                          #changed_08042026
            cached_path = raw_output_dir / f"{pmcid}_extraction.json"          #changed_08042026
            try:                                                               #changed_08042026
                with open(cached_path, "r", encoding="utf-8") as f:            #changed_08042026
                    cached = json.load(f)                                      #changed_08042026
                ext_data = cached.get("parsed_output", {})                     #changed_08042026
                result = score_record(                                         #changed_08042026
                    pmcid=pmcid, gt_data=gt_data, ext_data=ext_data,           #changed_08042026
                )                                                              #changed_08042026
                results.append(result)                                         #changed_08042026
                skipped_pmcids.append(pmcid)                                   #changed_08042026
                logging.info(                                                  #changed_08042026
                    "Skipping %d/%d: %s (cached)",                             #changed_08042026
                    i + 1, len(holdout_set), pmcid,                            #changed_08042026
                )                                                              #changed_08042026
                continue                                                       #changed_08042026
            except Exception as e:                                             #changed_08042026
                logging.warning(                                               #changed_08042026
                    "Could not load cached result for %s, re-extracting: %s",  #changed_08042026
                    pmcid, e,                                                  #changed_08042026
                )                                                              #changed_08042026

        logging.info(                                                          #changed_060426
            "Extracting %d/%d: %s (%d chars)",                                 #changed_060426
            i + 1, len(holdout_set), pmcid, len(article_text),                 #changed_060426
        )                                                                      #changed_060426

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
        "Inference complete: %d/%d succeeded, %d cached, %d failed, %.1f minutes",  #changed_08042026
        len(results) - len(failed_pmcids) - len(skipped_pmcids),               #changed_08042026
        len(holdout_set),
        len(skipped_pmcids),                                                   #changed_08042026
        len(failed_pmcids),
        elapsed_total / 60,
    )

    generate_report(
        results=results,
        output_dir=output_dir,
        run_label=args.output_label,
        model_name=args.model,
    )

    # --- Log AI Core usage ---                                                #changed
    try:                                                                       #changed
        usage = student_lm.get_usage_summary()                                 #changed
        logging.info(                                                          #changed
            "AI Core usage: %d calls, %d prompt tokens, "                      #changed
            "%d completion tokens, %.0fs total",                               #changed
            usage["request_count"],                                            #changed
            usage["prompt_tokens"],                                            #changed
            usage["completion_tokens"],                                        #changed
            usage["total_inference_time"],                                     #changed
        )                                                                      #changed
    except Exception as e:                                                     #changed
        logging.warning("Could not log AI Core usage: %s", e)                  #changed

    logging.info("Holdout inference complete. Output: %s", output_dir)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
