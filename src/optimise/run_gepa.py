"""
run_gepa.py (AICORE BRANCH)
============================
CLI entry point for GEPA prompt optimisation of assay extraction
using SAP AI Core model deployments.

Changes from main branch:
- Uses AICoreLanguageModel instead of dspy.LM
- Adds --service-key for AI Core authentication
- Adds --no-resume for clean checkpoint restarts
- Model keys resolve via deployment_endpoints.json

Usage:
    python optimise/run_gepa.py --service-key c:/proj/pax-ai/src/aicore/sk.json --split-pct 30 --max-full-evals 5 --quiet
    python optimise/run_gepa.py --service-key c:/proj/pax-ai/src/aicore/sk.json --split-pct 100 --max-full-evals 5 --quiet
    python optimise/run_gepa.py --service-key c:/proj/pax-ai/src/aicore/sk.json --smoke-test --quiet
    python optimise/run_gepa.py --service-key c:/proj/pax-ai/src/aicore/sk.json --dry-run

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Branch: aicore
Design Decision: DD-2026-018
"""

import sys
import os
import json
import shutil
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
    """Configure logging to both console and file."""
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
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GEPA optimisation for assay extraction via SAP AI Core (DD-2026-018)."
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
        default=5,
        help="GEPA budget: number of full validation evaluations (default: 5).",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="Experiment name for output directory. Use a fixed name to "
             "enable GEPA checkpoint resume (default: auto-generated).",
    )
    parser.add_argument(
        "--student-model",
        type=str,
        default="claude-4.5-sonnet",
        help="Student model key or deployment name (default: claude-4.5-sonnet).",
    )
    parser.add_argument(
        "--reflection-model",
        type=str,
        default="claude-4.5-opus",
        help="Reflection model key or deployment name (default: claude-4.5-opus).",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=2,                                                             #changed: conservative for AI Core
        help="Number of parallel evaluation threads (default: 2).",
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
    parser.add_argument(                                                       #changed
        "--service-key", "-k",                                                 #changed
        type=str,                                                              #changed
        default=None,                                                          #changed
        help="Path to SAP AI Core service key JSON file.",                     #changed
    )                                                                          #changed
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and estimate cost only; no GEPA execution.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Override max-full-evals to 3 for pipeline verification.",         #changed: 3 for aicore
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress DSPy's internal INFO logs from console.",
    )
    parser.add_argument(                                                       #changed
        "--no-resume",                                                         #changed
        action="store_true",                                                   #changed
        help="Delete existing programme and checkpoint before starting. "      #changed
             "Use when you want a clean run.",                                 #changed
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
    """Estimate the cost of a GEPA run."""
    student_pricing = cfg.MODEL_PRICING.get(
        student_model, {"input": 3.0, "output": 15.0}
    )
    # Per-call estimate: ~25K input + ~4K output for long articles             #changed
    per_extraction = (25000 * student_pricing["input"] / 1_000_000
                      + 4000 * student_pricing["output"] / 1_000_000)          #changed

    per_reflection = (30000 * 15.0 / 1_000_000                                #changed
                      + 5000 * 75.0 / 1_000_000)                              #changed

    total_rollouts = max_full_evals * (n_train + n_val)                        #changed
    est_iterations = max_full_evals * 5  # approx iterations

    extraction_cost = total_rollouts * per_extraction
    reflection_cost = est_iterations * per_reflection
    total_usd = extraction_cost + reflection_cost

    return {
        "max_full_evals": max_full_evals,
        "n_train": n_train,
        "n_val": n_val,
        "total_rollouts": total_rollouts,                                      #changed
        "per_extraction_usd": round(per_extraction, 4),
        "per_reflection_usd": round(per_reflection, 4),
        "extraction_cost_usd": round(extraction_cost, 2),
        "reflection_cost_usd": round(reflection_cost, 2),
        "total_usd": round(total_usd, 2),
        "total_sgd": round(total_usd * 1.35, 2),
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
    """Save experiment configuration and metadata to JSON."""
    metadata = {
        "experiment_name": args.experiment_name,
        "design_decision": "DD-2026-018",
        "branch": "aicore",                                                    #changed
        "platform": "SAP AI Core",                                             #changed
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
    """GEPA optimisation pipeline via SAP AI Core."""

    args = parse_args()

    # --- Override for smoke test ---
    if args.smoke_test:
        args.max_full_evals = 3                                                #changed: 3 for aicore
        logging.info("Smoke test mode: max_full_evals overridden to 3")

    # --- Generate experiment name ---
    if args.experiment_name is None:
        args.experiment_name = (
            f"assay_{args.split_pct}pct_"
            f"evals{args.max_full_evals}"
        )
        # No timestamp — enables checkpoint resume by default                  #changed

    # --- Output directory ---
    output_dir = Path(cfg.ASSAY_GEPA_OUTPUT) / args.experiment_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- GEPA log directory ---
    gepa_log_dir = output_dir / "gepa_logs"

    # --- No-resume: clean slate ---                                           #changed
    if args.no_resume:                                                         #changed
        programme_path = output_dir / "optimised_programme.json"               #changed
        if programme_path.exists():                                            #changed
            programme_path.unlink()                                            #changed
            print(f"  --no-resume: deleted {programme_path}")                  #changed
        if gepa_log_dir.exists():                                              #changed
            shutil.rmtree(gepa_log_dir)                                        #changed
            print(f"  --no-resume: deleted {gepa_log_dir}")                    #changed

    # --- Logging ---
    setup_logging(Path(cfg.LOG_PATH), args.experiment_name)
    logging.info("GEPA optimisation starting (AICORE BRANCH)")                 #changed
    logging.info("Arguments: %s", vars(args))
    logging.info("Output directory: %s", output_dir)

    # --- Quiet mode ---
    if args.quiet:
        for _name in ("dspy", "dspy.evaluate", "dspy.teleprompt",
                      "dspy.teleprompt.gepa", "dspy.teleprompt.gepa.gepa",
                      "litellm", "httpx"):
            logging.getLogger(_name).setLevel(logging.WARNING)
        logging.info("Quiet mode enabled: DSPy/LiteLLM INFO logs suppressed")

    # --- Load AI Core credentials ---                                         #changed
    if args.service_key:                                                       #changed
        from aicore.aicore_lm import set_service_key                           #changed_020426
        set_service_key(args.service_key)                                      #changed_020426
        logging.info("AI Core credentials loaded from %s", args.service_key)   #changed
    else:                                                                      #changed
        cfg.load_service_key_if_exists()                                       #changed

    # --- Load splits ---
    splits_filepath = args.splits_file or Path(cfg.GEPA_SPLITS_FILE)
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
    print(f"  GEPA OPTIMISATION PRE-FLIGHT (AICORE BRANCH)")                   #changed
    print(f"{'=' * 60}")
    print(f"  Experiment:       {args.experiment_name}")
    print(f"  Training split:   {args.split_pct}% ({len(trainset)} records)")
    print(f"  Validation:       {len(valset)} records")
    print(f"  Holdout:          {len(holdout_set)} records (not used in GEPA)")
    print(f"  Student model:    {args.student_model}")
    print(f"  Reflection model: {args.reflection_model}")
    print(f"  max_full_evals:   {args.max_full_evals}")
    print(f"  Total rollouts:   {cost_estimate['total_rollouts']}")            #changed
    print(f"  num_threads:      {args.num_threads}")
    print(f"  seed:             {args.seed}")
    print(f"  Output:           {output_dir}")
    print(f"  Est. cost:        ${cost_estimate['total_usd']:.2f} USD "
          f"/ ${cost_estimate['total_sgd']:.2f} SGD")
    print(f"  Quiet mode:       {args.quiet}")
    print(f"  Dry run:          {args.dry_run}")
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

    # --- Configure AI Core LMs ---                                            #changed
    from aicore.aicore_lm import AICoreLanguageModel                           #changed

    student_name = cfg.resolve_model(args.student_model)                       #changed_020426
    reflection_name = cfg.resolve_model(args.reflection_model)                 #changed_020426

    student_lm = AICoreLanguageModel(                                          #changed
        model_name=student_name,                                               #changed
        temperature=0.0,                                                       #changed
        max_tokens=64000,                                                      #changed
    )                                                                          #changed
    reflection_lm = AICoreLanguageModel(                                       #changed
        model_name=reflection_name,                                            #changed
        temperature=1.0,                                                       #changed
        max_tokens=32000,                                                      #changed
    )                                                                          #changed

    dspy.configure(lm=student_lm)                                              #changed
    logging.info("Student LM (AI Core): %s", student_name)                     #changed
    logging.info("Reflection LM (AI Core): %s", reflection_name)               #changed

    # --- Configure and run GEPA ---
    logging.info("Initialising GEPA optimiser...")

    gepa_log_dir.mkdir(parents=True, exist_ok=True)                            #changed

    optimizer = dspy.GEPA(
        metric=gepa_feedback_metric,
        max_full_evals=args.max_full_evals,
        num_threads=args.num_threads,
        seed=args.seed,
        track_stats=True,
        track_best_outputs=True,
        log_dir=str(gepa_log_dir),
        reflection_minibatch_size=3,
        reflection_lm=reflection_lm,
        use_merge=True,
        failure_score=0.0,
        perfect_score=1.0,
        gepa_kwargs={"use_cloudpickle": True},
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

    # --- Save evolved prompt ---
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

    # --- Log AI Core usage ---                                                #changed
    try:                                                                       #changed
        student_usage = student_lm.get_usage_summary()                         #changed
        reflection_usage = reflection_lm.get_usage_summary()                   #changed
        usage_summary = {                                                      #changed
            "student": student_usage,                                          #changed
            "reflection": reflection_usage,                                    #changed
        }                                                                      #changed
        usage_filepath = output_dir / "aicore_usage.json"                      #changed
        with open(usage_filepath, "w", encoding="utf-8") as f:                 #changed
            json.dump(usage_summary, f, indent=2)                              #changed
        logging.info(                                                          #changed
            "AI Core usage: student=%d calls (%.0fs), "                        #changed
            "reflection=%d calls (%.0fs)",                                     #changed
            student_usage["request_count"],                                    #changed
            student_usage["total_inference_time"],                              #changed
            reflection_usage["request_count"],                                 #changed
            reflection_usage["total_inference_time"],                           #changed
        )                                                                      #changed
    except Exception as e:                                                     #changed
        logging.warning("Could not log AI Core usage: %s", e)                  #changed

    # --- Final summary ---
    print(f"\n{'=' * 60}")
    print(f"  GEPA OPTIMISATION COMPLETE (AICORE)")                            #changed
    print(f"{'=' * 60}")
    print(f"  Duration:         {elapsed / 60:.1f} minutes")
    print(f"  Output:           {output_dir}")
    print(f"  Programme:        {programme_filepath}")
    print(f"  GEPA logs:        {gepa_log_dir}")
    print(f"{'=' * 60}\n")
    print(f"  Next step: run holdout inference with:")
    print(f"    python optimise/run_holdout.py --service-key {args.service_key} "
          f"--programme {programme_filepath}")
    print(f"{'=' * 60}\n")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
