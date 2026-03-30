"""
run_gepa.py
===========
CLI entry point for GEPA prompt optimisation of assay extraction.

Usage:
    python run_gepa.py --split-pct 100 --max-full-evals 60
    python run_gepa.py --split-pct 30  --max-full-evals 60
    python run_gepa.py --split-pct 100 --max-full-evals 5 --smoke-test
    python run_gepa.py --split-pct 100 --dry-run

Output is written to:
    <DRIVE_BASE>/assay/gepa/<experiment_name>/

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-018
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
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import cfg                                                         # noqa: E402

import dspy                                                                    # noqa: E402

from extract.extractor import AssayExtractor                                   # noqa: E402
from optimise.data_loader import load_splits, build_datasets                   # noqa: E402
from optimise.feedback_metric import gepa_feedback_metric                      # noqa: E402


# ===========================================================================
# Logging setup
# ===========================================================================

def setup_logging(log_dir: Path, experiment_name: str) -> None:
    """Configure logging to both console and file.

    Args:
        log_dir: Directory for the log file.
        experiment_name: Used in the log filename.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"gepa_{experiment_name}_{timestamp}.log"

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
        description="GEPA optimisation for assay extraction (DD-2026-018)."
    )

    parser.add_argument(
        "--split-pct",
        type=int,
        default=100,
        choices=[30, 100],
        help="Training split percentage (default: 100).",
    )
    parser.add_argument(
        "--max-full-evals",
        type=int,
        default=60,
        help="GEPA budget: number of full validation evaluations (default: 60).",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="Experiment name for output directory (default: auto-generated).",
    )
    parser.add_argument(
        "--student-model",
        type=str,
        default="claude-sonnet-4-6",
        choices=list(cfg.DSPY_MODEL_STRINGS.keys()),
        help="Student model key (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "--reflection-model",
        type=str,
        default="claude-opus-4-6",
        choices=list(cfg.DSPY_MODEL_STRINGS.keys()),
        help="Reflection model key (default: claude-opus-4-6).",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=4,
        help="Number of parallel evaluation threads (default: 4).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--splits-file",
        type=Path,
        default=None,
        help="Override path to splits JSON (default: from config).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and estimate cost only; no GEPA execution.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Override max-full-evals to 5 for pipeline verification.",
    )
    parser.add_argument(                                                       #changed
        "--quiet", "-q",                                                       #changed
        action="store_true",                                                   #changed
        help="Suppress DSPy's internal INFO logs from console. "               #changed
             "Logs are still written to log_dir.",                              #changed
    )                                                                          #changed

    return parser.parse_args()


# ===========================================================================
# Cost estimation
# ===========================================================================

def estimate_cost(
    n_train: int,
    n_val: int,
    max_full_evals: int,
    student_model: str,
    reflection_model: str,
) -> dict:
    """Estimate the cost of a GEPA run.

    Uses per-call cost estimates based on typical article lengths.

    Args:
        n_train: Number of training examples.
        n_val: Number of validation examples.
        max_full_evals: GEPA budget parameter.
        student_model: Student model key.
        reflection_model: Reflection model key.

    Returns:
        Dictionary with cost breakdown.
    """
    # Per-call estimates (USD) based on ~12K input + ~2K output tokens
    student_pricing = cfg.MODEL_PRICING.get(student_model, {"input": 3.0, "output": 15.0})
    per_extraction = (12000 * student_pricing["input"] / 1_000_000
                      + 2000 * student_pricing["output"] / 1_000_000)

    # Reflection cost (Opus: ~8K input + ~3K output)
    per_reflection = (8000 * 15.0 / 1_000_000
                      + 3000 * 75.0 / 1_000_000)

    # Per iteration: minibatch (3 extractions) + 1 reflection
    # ~50% of iterations trigger a full validation eval
    est_iterations = max_full_evals * 2
    minibatch_cost = est_iterations * 3 * per_extraction
    reflection_cost = est_iterations * per_reflection
    full_eval_cost = max_full_evals * n_val * per_extraction

    total_usd = minibatch_cost + reflection_cost + full_eval_cost
    total_sgd = total_usd * 1.35

    return {
        "max_full_evals": max_full_evals,
        "n_train": n_train,
        "n_val": n_val,
        "est_iterations": est_iterations,
        "per_extraction_usd": round(per_extraction, 4),
        "per_reflection_usd": round(per_reflection, 4),
        "minibatch_cost_usd": round(minibatch_cost, 2),
        "reflection_cost_usd": round(reflection_cost, 2),
        "full_eval_cost_usd": round(full_eval_cost, 2),
        "total_usd": round(total_usd, 2),
        "total_sgd": round(total_sgd, 2),
    }


# ===========================================================================
# Experiment metadata
# ===========================================================================

def save_experiment_metadata(
    output_dir: Path,
    args: argparse.Namespace,
    n_train: int,
    n_val: int,
    n_holdout: int,
    cost_estimate: dict,
) -> None:
    """Save experiment configuration and metadata to JSON.

    Args:
        output_dir: Output directory.
        args: Parsed CLI arguments.
        n_train: Number of training examples.
        n_val: Number of validation examples.
        n_holdout: Number of holdout examples.
        cost_estimate: Cost estimate dictionary.
    """
    metadata = {
        "experiment_name": args.experiment_name,
        "design_decision": "DD-2026-018",
        "timestamp": datetime.now().isoformat(),
        "split_pct": args.split_pct,
        "max_full_evals": args.max_full_evals,
        "student_model": args.student_model,
        "reflection_model": args.reflection_model,
        "num_threads": args.num_threads,
        "seed": args.seed,
        "n_train": n_train,
        "n_val": n_val,
        "n_holdout": n_holdout,
        "cost_estimate": cost_estimate,
    }

    filepath = output_dir / "experiment_metadata.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logging.info("Experiment metadata saved: %s", filepath)


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """GEPA optimisation pipeline: load data, configure, optimise, save."""

    args = parse_args()

    # --- Override for smoke test ---
    if args.smoke_test:
        args.max_full_evals = 5
        logging.info("Smoke test mode: max_full_evals overridden to 5")

    # --- Generate experiment name ---
    if args.experiment_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.experiment_name = (
            f"assay_{args.split_pct}pct_"
            f"evals{args.max_full_evals}_"
            f"{timestamp}"
        )

    # --- Output directory ---
    output_dir = Path(cfg.ASSAY_GEPA_OUTPUT) / args.experiment_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- GEPA log directory ---
    gepa_log_dir = str(output_dir / "gepa_logs")

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.experiment_name)
    logging.info("GEPA optimisation starting")
    logging.info("Arguments: %s", vars(args))
    logging.info("Output directory: %s", output_dir)

    # --- Quiet mode: suppress DSPy internal logs from console ---             #changed
    if args.quiet:                                                             #changed
        for _name in ("dspy", "dspy.evaluate", "dspy.teleprompt",              #changed
                      "dspy.teleprompt.gepa", "dspy.teleprompt.gepa.gepa",     #changed
                      "litellm", "httpx"):                                     #changed
            logging.getLogger(_name).setLevel(logging.WARNING)                 #changed
        logging.info("Quiet mode enabled: DSPy/LiteLLM INFO logs suppressed") #changed

    # --- Load splits ---
    splits_filepath = args.splits_file or Path(cfg.GEPA_SPLITS_FILE)           #changed
    splits = load_splits(splits_filepath)

    # --- Build datasets ---
    logging.info("Building datasets (split_pct=%d)...", args.split_pct)
    trainset, valset, holdout_set = build_datasets(
        splits=splits,
        cfg=cfg,
        split_pct=args.split_pct,
    )

    logging.info(
        "Datasets: train=%d, val=%d, holdout=%d",
        len(trainset), len(valset), len(holdout_set),
    )

    # --- Cost estimate ---
    cost_estimate = estimate_cost(
        n_train=len(trainset),
        n_val=len(valset),
        max_full_evals=args.max_full_evals,
        student_model=args.student_model,
        reflection_model=args.reflection_model,
    )

    # --- Pre-flight summary ---
    print(f"\n{'=' * 60}")
    print(f"  GEPA OPTIMISATION PRE-FLIGHT (DD-2026-018)")
    print(f"{'=' * 60}")
    print(f"  Experiment:       {args.experiment_name}")
    print(f"  Training split:   {args.split_pct}% ({len(trainset)} records)")
    print(f"  Validation:       {len(valset)} records")
    print(f"  Holdout:          {len(holdout_set)} records (not used in GEPA)")
    print(f"  Student model:    {args.student_model}")
    print(f"  Reflection model: {args.reflection_model}")
    print(f"  max_full_evals:   {args.max_full_evals}")
    print(f"  num_threads:      {args.num_threads}")
    print(f"  seed:             {args.seed}")
    print(f"  Output:           {output_dir}")
    print(f"  Est. cost:        ${cost_estimate['total_usd']:.2f} USD "
          f"/ ${cost_estimate['total_sgd']:.2f} SGD")
    print(f"  Dry run:          {args.dry_run}")
    print(f"  Quiet mode:       {args.quiet}")                                 #changed
    print(f"{'=' * 60}\n")

    # --- Save metadata ---
    save_experiment_metadata(
        output_dir, args,
        len(trainset), len(valset), len(holdout_set),
        cost_estimate,
    )

    if args.dry_run:
        logging.info("Dry run complete. Exiting without GEPA execution.")
        return

    # --- Configure DSPy models ---
    student_model_string = cfg.DSPY_MODEL_STRINGS[args.student_model]
    reflection_model_string = cfg.DSPY_MODEL_STRINGS[args.reflection_model]

    student_lm_kwargs = {
        "model": student_model_string,
        "max_tokens": 64000,
    }
    reflection_lm_kwargs = {
        "model": reflection_model_string,
        "temperature": 1.0,
        "max_tokens": 32000,
    }

    # Set API keys based on provider
    if student_model_string.startswith("anthropic/"):
        student_lm_kwargs["api_key"] = cfg.ANTHROPIC_API_KEY
    if reflection_model_string.startswith("anthropic/"):
        reflection_lm_kwargs["api_key"] = cfg.ANTHROPIC_API_KEY

    student_lm = dspy.LM(**student_lm_kwargs)
    reflection_lm = dspy.LM(**reflection_lm_kwargs)

    dspy.configure(lm=student_lm)
    logging.info("Student LM configured: %s", student_model_string)
    logging.info("Reflection LM configured: %s", reflection_model_string)

    # --- Configure and run GEPA ---
    logging.info("Initialising GEPA optimiser...")

    optimizer = dspy.GEPA(
        metric=gepa_feedback_metric,
        max_full_evals=args.max_full_evals,
        num_threads=args.num_threads,
        seed=args.seed,
        track_stats=True,
        track_best_outputs=True,
        log_dir=gepa_log_dir,
        reflection_minibatch_size=3,
        reflection_lm=reflection_lm,
        use_merge=True,
        failure_score=0.0,
        perfect_score=1.0,
        gepa_kwargs={"use_cloudpickle": True},                                 #changed: avoid StringSignature pickle error
    )

    programme = AssayExtractor()
    logging.info("Starting GEPA compile...")
    start_time = time.time()

    optimised = optimizer.compile(
        programme,
        trainset=trainset,
        valset=valset,
    )

    elapsed = time.time() - start_time
    logging.info("GEPA compile complete in %.1f minutes", elapsed / 60)

    # --- Save optimised programme ---
    programme_filepath = output_dir / "optimised_programme.json"
    optimised.save(str(programme_filepath))
    logging.info("Optimised programme saved: %s", programme_filepath)

    # --- Save detailed results ---
    if hasattr(optimised, "detailed_results") and optimised.detailed_results:
        detailed = optimised.detailed_results

        # Save what is serialisable
        results_to_save = {
            "val_aggregate_scores": (
                detailed.val_aggregate_scores
                if hasattr(detailed, "val_aggregate_scores") else None
            ),
            "highest_score_achieved_per_val_task": (
                detailed.highest_score_achieved_per_val_task
                if hasattr(detailed, "highest_score_achieved_per_val_task") else None
            ),
        }

        results_filepath = output_dir / "detailed_results.json"
        with open(results_filepath, "w", encoding="utf-8") as f:
            json.dump(results_to_save, f, indent=2, default=str)
        logging.info("Detailed results saved: %s", results_filepath)

    # --- Print evolved prompt ---
    try:
        predictors = optimised.predictors()
        if predictors:
            evolved_instruction = predictors[0].signature.instructions
            prompt_filepath = output_dir / "evolved_prompt.txt"
            with open(prompt_filepath, "w", encoding="utf-8") as f:
                f.write(evolved_instruction)
            logging.info("Evolved prompt saved: %s", prompt_filepath)
            print(f"\n{'=' * 60}")
            print("  EVOLVED PROMPT (first 500 chars):")
            print(f"{'=' * 60}")
            print(evolved_instruction[:500])
            print(f"{'=' * 60}\n")
    except Exception as e:
        logging.warning("Could not extract evolved prompt: %s", e)

    # --- Final summary ---
    print(f"\n{'=' * 60}")
    print(f"  GEPA OPTIMISATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Duration:         {elapsed / 60:.1f} minutes")
    print(f"  Output:           {output_dir}")
    print(f"  Programme:        {programme_filepath}")
    print(f"  GEPA logs:        {gepa_log_dir}")
    print(f"{'=' * 60}\n")
    print(f"  Next step: run holdout inference with:")
    print(f"    python run_holdout.py --programme {programme_filepath}")
    print(f"{'=' * 60}\n")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
