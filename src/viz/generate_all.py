"""
generate_all.py
===============
CLI entry point to generate all report figures.

Usage:
    python -m viz.generate_all --gepa-dir <path> [options]

Examples:
    # Generate only GEPA-internal plots (Vis 1, 2, 3, 8):
    python -m viz.generate_all ^
        --gepa-dir C:\\proj\\pax-ai-working\\assay\\v1\\gepa\\assay_100pct_sonnet_evals5 ^
        --output-dir C:\\proj\\pax-ai-working\\figures ^
        --baseline-f1 0.596

    # Generate all plots including holdout comparisons (Vis 4-7):
    python -m viz.generate_all ^
        --gepa-dir C:\\proj\\pax-ai-working\\assay\\v1\\gepa\\assay_100pct_sonnet_evals5 ^
        --baseline-holdout-dir C:\\proj\\pax-ai-working\\assay\\v1\\holdout\\baseline ^
        --gepa-holdout-dir C:\\proj\\pax-ai-working\\assay\\v1\\holdout\\gepa_100pct ^
        --output-dir C:\\proj\\pax-ai-working\\figures ^
        --baseline-f1 0.596

    # Add GEPA-30% condition for the distribution plot (Vis 7):
    python -m viz.generate_all ^
        --gepa-dir C:\\proj\\pax-ai-working\\assay\\v1\\gepa\\assay_100pct_sonnet_evals5 ^
        --baseline-holdout-dir C:\\proj\\pax-ai-working\\assay\\v1\\holdout\\baseline ^
        --gepa-holdout-dir C:\\proj\\pax-ai-working\\assay\\v1\\holdout\\gepa_100pct ^
        --gepa30-holdout-dir C:\\proj\\pax-ai-working\\assay\\v1\\holdout\\gepa_30pct ^
        --output-dir C:\\proj\\pax-ai-working\\figures ^
        --baseline-f1 0.596

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
"""

import argparse
import json
import logging
import os
import sys

from viz.load_data import load_gepa_data, load_holdout_results
from viz.gepa_plots import (
    plot_convergence,
    plot_pareto_frontier_size,
    plot_record_heatmap,
    plot_dag,
)
from viz.holdout_plots import (
    plot_paired_scatter,
    plot_per_field_bars,
    plot_confusion_matrices,
    plot_f1_distribution,
    plot_cross_model_transfer,
    plot_ablation_bar,                                                         #changed_16042026
)


def main():
    """Parse arguments and generate requested figures."""
    parser = argparse.ArgumentParser(
        description="Generate report figures for AI6129 Pathogen Tracking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required
    parser.add_argument(
        "--gepa-dir",
        required=True,
        help="Path to GEPA experiment directory (contains gepa_logs/, "
             "detailed_results.json, etc.)",
    )

    # Output
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output PDF figures (default: current dir).",
    )

    # Baseline reference
    parser.add_argument(
        "--baseline-f1",
        type=float,
        default=None,
        help="Baseline mean F1 for reference line on convergence plot "
             "(e.g. 0.596).",
    )

    # Holdout directories (optional — needed for Vis 4-7)
    parser.add_argument(
        "--baseline-holdout-dir",
        default=None,
        help="Path to baseline holdout results: either a *_results.json "
             "file or a directory containing one.",
    )
    parser.add_argument(
        "--gepa-holdout-dir",
        default=None,
        help="Path to GEPA-optimised holdout results: either a "
             "*_results.json file or a directory containing one.",
    )
    parser.add_argument(
        "--gepa30-holdout-dir",
        default=None,
        help="Path to GEPA-30%% holdout results (optional, for Vis 7): "
             "either a *_results.json file or a directory.",
    )
    parser.add_argument(                                                       #changed_16042026
        "--predict-holdout-dir",                                               #changed_16042026
        default=None,                                                          #changed_16042026
        help="Path to Predict (no-CoT) holdout results for Vis 10 ablation. " #changed_16042026
             "Requires --baseline-holdout-dir (CoT) to also be set.",         #changed_16042026
    )                                                                          #changed_16042026

    # Validation PMCIDs (optional — for heatmap labels)
    parser.add_argument(
        "--val-pmcids",
        nargs="*",
        default=None,
        help="Ordered list of validation PMCIDs for heatmap row labels.",
    )

    # Cross-model transfer (optional — for Vis 9)
    parser.add_argument(
        "--transfer-json",
        default=None,
        help="Path to a JSON file specifying cross-model transfer data "
             "for Vis 9. See run_experiments.md for schema.",
    )

    # Selective generation
    parser.add_argument(
        "--only",
        nargs="*",
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],         #changed_16042026
        default=None,
        help="Generate only specified visualisation numbers "
             "(default: all available).",
    )

    # Verbosity
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress info-level logging.",
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    )

    # -------------------------------------------------------------------
    # Ensure output directory exists
    # -------------------------------------------------------------------
    os.makedirs(args.output_dir, exist_ok=True)

    # -------------------------------------------------------------------
    # Determine which visualisations to generate
    # -------------------------------------------------------------------
    requested = set(args.only) if args.only else None  # None = all

    def should_generate(vis_num):
        """Check if a visualisation number should be generated."""
        return requested is None or str(vis_num) in requested

    # -------------------------------------------------------------------
    # Load GEPA data
    # -------------------------------------------------------------------
    gepa_data = load_gepa_data(args.gepa_dir)
    print(gepa_data.summary())

    generated = []
    skipped = []

    # -------------------------------------------------------------------
    # Vis 1: Score convergence curve
    # -------------------------------------------------------------------
    if should_generate(1):
        output_file = os.path.join(args.output_dir, "vis1_convergence.pdf")
        plot_convergence(gepa_data, output_file, args.baseline_f1)
        generated.append("Vis 1: Score convergence curve")

    # -------------------------------------------------------------------
    # Vis 2: Pareto frontier size
    # -------------------------------------------------------------------
    if should_generate(2):
        if gepa_data.val_subscores:
            output_file = os.path.join(args.output_dir, "vis2_pareto_frontier.pdf")
            plot_pareto_frontier_size(gepa_data, output_file)
            generated.append("Vis 2: Pareto frontier size")
        else:
            skipped.append("Vis 2: Pareto frontier — no val_subscores data")

    # -------------------------------------------------------------------
    # Vis 3: Per-record heatmap
    # -------------------------------------------------------------------
    if should_generate(3):
        if gepa_data.val_subscores:
            output_file = os.path.join(args.output_dir, "vis3_record_heatmap.pdf")
            plot_record_heatmap(
                gepa_data, output_file, val_pmcids=args.val_pmcids,
            )
            generated.append("Vis 3: Per-record heatmap")
        else:
            skipped.append("Vis 3: Heatmap — no val_subscores data")

    # -------------------------------------------------------------------
    # Vis 8: GEPA DAG (numbered 8 but generated here with GEPA data)
    # -------------------------------------------------------------------
    if should_generate(8):
        if gepa_data.parents:
            output_file = os.path.join(args.output_dir, "vis8_gepa_dag")
            plot_dag(gepa_data, output_file)
            generated.append("Vis 8: GEPA optimisation trajectory DAG")
        else:
            skipped.append("Vis 8: DAG — no parent lineage data")

    # -------------------------------------------------------------------
    # Holdout comparison plots (Vis 4-7): require holdout directories
    # -------------------------------------------------------------------
    has_holdout = (
        args.baseline_holdout_dir is not None
        and args.gepa_holdout_dir is not None
    )

    baseline_holdout = {}
    gepa_holdout = {}
    gepa30_holdout = {}

    if has_holdout:
        baseline_holdout = load_holdout_results(args.baseline_holdout_dir)
        gepa_holdout = load_holdout_results(args.gepa_holdout_dir)
        if args.gepa30_holdout_dir:
            gepa30_holdout = load_holdout_results(args.gepa30_holdout_dir)

    # -------------------------------------------------------------------
    # Vis 4: Paired F1 scatter plot
    # -------------------------------------------------------------------
    if should_generate(4):
        if has_holdout and baseline_holdout and gepa_holdout:
            output_file = os.path.join(args.output_dir, "vis4_paired_scatter.pdf")
            plot_paired_scatter(baseline_holdout, gepa_holdout, output_file)
            generated.append("Vis 4: Paired F1 scatter plot")
        else:
            skipped.append("Vis 4: Scatter — holdout directories not provided")

    # -------------------------------------------------------------------
    # Vis 5: Per-field F1 grouped bars
    # -------------------------------------------------------------------
    if should_generate(5):
        if has_holdout and baseline_holdout and gepa_holdout:
            output_file = os.path.join(args.output_dir, "vis5_field_bars.pdf")
            plot_per_field_bars(baseline_holdout, gepa_holdout, output_file)
            generated.append("Vis 5: Per-field F1 grouped bars")
        else:
            skipped.append("Vis 5: Field bars — holdout directories not provided")

    # -------------------------------------------------------------------
    # Vis 6: Category confusion matrices
    # -------------------------------------------------------------------
    if should_generate(6):
        if has_holdout and baseline_holdout and gepa_holdout:
            output_file = os.path.join(args.output_dir, "vis6_confusion.pdf")
            plot_confusion_matrices(
                baseline_holdout, gepa_holdout, output_file,
            )
            generated.append("Vis 6: Category confusion matrices")
        else:
            skipped.append("Vis 6: Confusion — holdout directories not provided")

    # -------------------------------------------------------------------
    # Vis 7: F1 distribution box/violin plot
    # -------------------------------------------------------------------
    if should_generate(7):
        if has_holdout and baseline_holdout and gepa_holdout:
            condition_data = {}

            baseline_scores = [
                rec.overall_f1 for rec in baseline_holdout.values()
            ]
            gepa_scores = [
                rec.overall_f1 for rec in gepa_holdout.values()
            ]

            condition_data["Baseline"] = baseline_scores
            condition_data["GEPA-100%"] = gepa_scores

            if gepa30_holdout:
                gepa30_scores = [
                    rec.overall_f1 for rec in gepa30_holdout.values()
                ]
                condition_data["GEPA-30%"] = gepa30_scores

            output_file = os.path.join(args.output_dir, "vis7_f1_distribution.pdf")
            plot_f1_distribution(condition_data, output_file)
            generated.append("Vis 7: F1 distribution plot")
        else:
            skipped.append("Vis 7: Distribution — holdout directories not provided")

    # -------------------------------------------------------------------
    # Vis 9: Cross-model prompt transfer
    # -------------------------------------------------------------------
    if should_generate(9):
        if args.transfer_json and os.path.isfile(args.transfer_json):
            with open(args.transfer_json, "r", encoding="utf-8") as fh:
                transfer_data = json.load(fh)
            output_file = os.path.join(
                args.output_dir, "vis9_cross_model_transfer.pdf"
            )
            plot_cross_model_transfer(transfer_data, output_file)
            generated.append("Vis 9: Cross-model prompt transfer")
        else:
            skipped.append(
                "Vis 9: Transfer -- --transfer-json not provided or not found"
            )

    # -------------------------------------------------------------------     #changed_16042026
    # Vis 10: Predict vs CoT ablation bar chart                               #changed_16042026
    # -------------------------------------------------------------------     #changed_16042026
    if should_generate(10):                                                    #changed_16042026
        has_predict = args.predict_holdout_dir is not None                     #changed_16042026
        has_cot = args.baseline_holdout_dir is not None                        #changed_16042026
        if has_predict and has_cot:                                            #changed_16042026
            predict_holdout = load_holdout_results(args.predict_holdout_dir)   #changed_16042026
            cot_holdout = (                                                    #changed_16042026
                baseline_holdout                                               #changed_16042026
                if baseline_holdout                                            #changed_16042026
                else load_holdout_results(args.baseline_holdout_dir)           #changed_16042026
            )                                                                  #changed_16042026
            output_file = os.path.join(                                        #changed_16042026
                args.output_dir, "vis10_ablation_predict_vs_cot.pdf"           #changed_16042026
            )                                                                  #changed_16042026
            plot_ablation_bar(                                                 #changed_16042026
                predict_records=predict_holdout,                               #changed_16042026
                cot_records=cot_holdout,                                       #changed_16042026
                output_path=output_file,                                       #changed_16042026
                gepa_records=gepa_holdout if gepa_holdout else None,           #changed_16042026
                gepa_best_micro_f1=0.6478,                                     #changed_16042026
                model_label="Sonnet 4.5",                                      #changed_16042026
            )                                                                  #changed_16042026
            generated.append("Vis 10: Predict vs CoT ablation bar chart")     #changed_16042026
        else:                                                                  #changed_16042026
            skipped.append(                                                    #changed_16042026
                "Vis 10: Ablation -- --predict-holdout-dir and "               #changed_16042026
                "--baseline-holdout-dir must both be provided"                 #changed_16042026
            )                                                                  #changed_16042026

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print("")
    print("=" * 50)
    print("Figure Generation Summary")
    print("=" * 50)

    if generated:
        print(f"\nGenerated ({len(generated)}):")
        for item in generated:
            print(f"  [OK] {item}")

    if skipped:
        print(f"\nSkipped ({len(skipped)}):")
        for item in skipped:
            print(f"  [--] {item}")

    print(f"\nOutput directory: {os.path.abspath(args.output_dir)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
