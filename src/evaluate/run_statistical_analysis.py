"""
run_statistical_analysis.py
============================
Statistical significance testing for PAX-AI experimental results.

Implements the pre-registered statistical plan (DD-2026-018):
- Wilcoxon signed-rank test (primary, per-record F1)
- Bootstrap 95% CI on mean delta F1
- McNemar's exact test (category classification)
- Holm-Bonferroni correction for multiple comparisons
- Matched-pairs rank-biserial effect size

Reads per-record CSV files from each run and pairs them by PMCID.

Usage:
    python run_statistical_analysis.py --results-dir <path_to_gt_diagnostic_analysis>
    python run_statistical_analysis.py --results-dir ... --output-dir <path_to_stats_output>
    python run_statistical_analysis.py --results-dir ... --alpha 0.05

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
Design Decision: DD-2026-018
"""

import csv
import json
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional

import numpy as np
from scipy import stats as scipy_stats


# ===========================================================================
# Logging
# ===========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# Data structures
# ===========================================================================

@dataclass
class PerRecordRow:
    """One row from a per-record CSV."""
    pmcid: str
    gt_category: str
    ext_category: str
    category_correct: bool
    primary_f1: float
    loose_f1: float


@dataclass
class PairedComparison:
    """Definition of a paired comparison between two runs."""
    label: str
    run_a_label: str          # e.g. "v5_baseline_sonnet45_holdout"
    run_b_label: str          # e.g. "gepa_holdout_100pct_sonnet45_evals5"
    description: str = ""
    family: str = ""          # grouping for Holm-Bonferroni correction


@dataclass
class ComparisonResult:
    """Result of a single paired statistical comparison."""
    label: str
    run_a: str
    run_b: str
    n_paired: int

    # Wilcoxon signed-rank
    wilcoxon_statistic: float = 0.0
    wilcoxon_p: float = 1.0
    effect_size_r: float = 0.0                # rank-biserial correlation

    # Bootstrap CI
    mean_delta_f1: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0

    # McNemar (category classification)
    mcnemar_statistic: float = 0.0
    mcnemar_p: float = 1.0
    discordant_ab: int = 0                    # A correct, B incorrect
    discordant_ba: int = 0                    # B correct, A incorrect

    # After Holm-Bonferroni
    family: str = ""
    corrected_alpha: float = 0.05
    wilcoxon_significant: bool = False
    mcnemar_significant: bool = False


# ===========================================================================
# Load per-record CSVs
# ===========================================================================

def load_per_record_csv(filepath: Path) -> Dict[str, PerRecordRow]:
    """Load a per-record CSV and return dict keyed by PMCID.

    Args:
        filepath: Path to the per-record CSV file.

    Returns:
        Dictionary mapping PMCID to PerRecordRow.
    """
    records = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pmcid = row["pmcid"]
            records[pmcid] = PerRecordRow(
                pmcid=pmcid,
                gt_category=row["gt_category"],
                ext_category=row["ext_category"],
                category_correct=(row["category_correct"] == "True"),
                primary_f1=float(row["primary_f1"]),
                loose_f1=float(row["loose_f1"]),
            )
    return records


def discover_runs(results_dir: Path) -> Dict[str, Path]:
    """Discover all run directories containing per-record CSVs.

    Args:
        results_dir: Base directory containing run subdirectories.

    Returns:
        Dictionary mapping run label to CSV file path.
    """
    runs = {}
    for subdir in sorted(results_dir.iterdir()):
        if not subdir.is_dir():
            continue
        # Look for *_per_record_results.csv
        csvs = list(subdir.glob("*_per_record_results.csv"))
        if csvs:
            run_label = subdir.name
            runs[run_label] = csvs[0]
            logger.info("Found run: %s -> %s", run_label, csvs[0].name)
    return runs


# ===========================================================================
# Wilcoxon signed-rank test
# ===========================================================================

def wilcoxon_signed_rank(
    f1_a: np.ndarray,
    f1_b: np.ndarray,
) -> Tuple[float, float, float]:
    """Compute Wilcoxon signed-rank test and rank-biserial effect size.

    Args:
        f1_a: Per-record F1 scores for run A (baseline).
        f1_b: Per-record F1 scores for run B (optimised).

    Returns:
        Tuple of (test_statistic, p_value, effect_size_r).
    """
    differences = f1_b - f1_a

    # Remove zero differences (ties) as Wilcoxon requires
    nonzero_mask = differences != 0
    nonzero_diffs = differences[nonzero_mask]

    if len(nonzero_diffs) < 2:
        logger.warning(
            "Fewer than 2 non-zero differences; Wilcoxon test not applicable"
        )
        return 0.0, 1.0, 0.0

    # scipy wilcoxon returns (statistic, p_value)
    # statistic is the smaller of W+ and W-
    stat, p_value = scipy_stats.wilcoxon(
        f1_a, f1_b,
        alternative="two-sided",
        method="exact" if len(nonzero_diffs) <= 25 else "approx",
    )

    # Rank-biserial effect size: r = 1 - (2W / (n*(n+1)/2))
    # where W is the test statistic (smaller of W+ and W-)
    n = len(nonzero_diffs)
    denominator = n * (n + 1) / 2
    effect_r = 1.0 - (2.0 * stat / denominator) if denominator > 0 else 0.0   #changed_09042026

    return float(stat), float(p_value), float(effect_r)


# ===========================================================================
# Bootstrap confidence interval
# ===========================================================================

def bootstrap_ci(
    f1_a: np.ndarray,
    f1_b: np.ndarray,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Compute bootstrap CI on mean delta F1 (B - A).

    Args:
        f1_a: Per-record F1 scores for run A.
        f1_b: Per-record F1 scores for run B.
        n_bootstrap: Number of bootstrap resamples.
        confidence: Confidence level (default 0.95).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (mean_delta, ci_lower, ci_upper).
    """
    rng = np.random.default_rng(seed)
    diffs = f1_b - f1_a
    n = len(diffs)
    mean_delta = float(np.mean(diffs))

    # Bootstrap resampling
    boot_means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)
        boot_means[i] = np.mean(diffs[indices])

    alpha = 1.0 - confidence
    ci_lower = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    return mean_delta, ci_lower, ci_upper


# ===========================================================================
# McNemar's exact test
# ===========================================================================

def mcnemar_exact(
    correct_a: np.ndarray,
    correct_b: np.ndarray,
) -> Tuple[float, float, int, int]:
    """Compute McNemar's exact test on paired binary classification.

    Args:
        correct_a: Boolean array, True if run A classified correctly.
        correct_b: Boolean array, True if run B classified correctly.

    Returns:
        Tuple of (statistic, p_value, n_ab, n_ba) where
        n_ab = A correct & B incorrect, n_ba = B correct & A incorrect.
    """
    # Discordant pairs
    n_ab = int(np.sum(correct_a & ~correct_b))    # A right, B wrong
    n_ba = int(np.sum(~correct_a & correct_b))    # B right, A wrong

    total_discordant = n_ab + n_ba

    if total_discordant == 0:
        logger.info("No discordant pairs; McNemar test not applicable")
        return 0.0, 1.0, n_ab, n_ba

    # Exact binomial test: under H0, discordant pairs are 50/50
    # Two-sided p-value
    p_value = float(
        scipy_stats.binomtest(
            min(n_ab, n_ba),
            n=total_discordant,
            p=0.5,
            alternative="two-sided",
        ).pvalue
    )

    statistic = float((n_ab - n_ba) ** 2 / total_discordant) if total_discordant > 0 else 0.0

    return statistic, p_value, n_ab, n_ba


# ===========================================================================
# Holm-Bonferroni correction
# ===========================================================================

def holm_bonferroni(
    p_values: List[float],
    alpha: float = 0.05,
) -> List[Tuple[float, bool]]:
    """Apply Holm-Bonferroni correction to a family of p-values.

    Args:
        p_values: List of raw p-values.
        alpha: Family-wise error rate.

    Returns:
        List of (corrected_alpha_threshold, is_significant) tuples,
        in the same order as the input p-values.
    """
    n = len(p_values)
    if n == 0:
        return []

    # Sort by p-value, keeping track of original index
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])

    results = [None] * n
    any_failed = False

    for rank, (orig_idx, p_val) in enumerate(indexed):
        threshold = alpha / (n - rank)

        if any_failed:
            results[orig_idx] = (threshold, False)
        elif p_val < threshold:
            results[orig_idx] = (threshold, True)
        else:
            results[orig_idx] = (threshold, False)
            any_failed = True

    return results


# ===========================================================================
# Run a single comparison
# ===========================================================================

def run_comparison(
    records_a: Dict[str, PerRecordRow],
    records_b: Dict[str, PerRecordRow],
    comparison: PairedComparison,
) -> ComparisonResult:
    """Execute all statistical tests for a single paired comparison.

    Args:
        records_a: Per-record data for run A (keyed by PMCID).
        records_b: Per-record data for run B (keyed by PMCID).
        comparison: Comparison definition.

    Returns:
        ComparisonResult with all test outcomes.
    """
    # Pair by PMCID
    common_pmcids = sorted(set(records_a.keys()) & set(records_b.keys()))
    n = len(common_pmcids)

    if n == 0:
        logger.error("No common PMCIDs between %s and %s",
                      comparison.run_a_label, comparison.run_b_label)
        return ComparisonResult(
            label=comparison.label,
            run_a=comparison.run_a_label,
            run_b=comparison.run_b_label,
            n_paired=0,
        )

    logger.info(
        "Comparison '%s': %d paired records (%s vs %s)",
        comparison.label, n, comparison.run_a_label, comparison.run_b_label,
    )

    # Build arrays
    f1_a = np.array([records_a[p].primary_f1 for p in common_pmcids])
    f1_b = np.array([records_b[p].primary_f1 for p in common_pmcids])
    correct_a = np.array([records_a[p].category_correct for p in common_pmcids])
    correct_b = np.array([records_b[p].category_correct for p in common_pmcids])

    # 1. Wilcoxon signed-rank
    w_stat, w_p, effect_r = wilcoxon_signed_rank(f1_a, f1_b)

    # 2. Bootstrap CI
    mean_delta, ci_lo, ci_hi = bootstrap_ci(f1_a, f1_b)

    # 3. McNemar's exact
    m_stat, m_p, n_ab, n_ba = mcnemar_exact(correct_a, correct_b)

    result = ComparisonResult(
        label=comparison.label,
        run_a=comparison.run_a_label,
        run_b=comparison.run_b_label,
        n_paired=n,
        wilcoxon_statistic=w_stat,
        wilcoxon_p=w_p,
        effect_size_r=effect_r,
        mean_delta_f1=mean_delta,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        mcnemar_statistic=m_stat,
        mcnemar_p=m_p,
        discordant_ab=n_ab,
        discordant_ba=n_ba,
        family=comparison.family,
    )

    return result


# ===========================================================================
# Default comparison families
# ===========================================================================

def build_default_comparisons() -> List[PairedComparison]:
    """Build the pre-registered comparison families.

    Returns:
        List of PairedComparison objects covering RQ1, RQ2, RQ3.
    """
    comparisons = []

    # RQ1: Baseline vs GEPA-best (per model)
    # Sonnet 4.5 is the primary; others are secondary
    comparisons.append(PairedComparison(
        label="RQ1: Baseline vs GEPA-100% (Sonnet 4.5)",
        run_a_label="v5_baseline_sonnet45_holdout",
        run_b_label="gepa_holdout_100pct_sonnet45_evals5",
        family="rq1_rq2",
    ))

    # RQ2: Sample efficiency -- 100% vs 30% (Sonnet 4.5)
    comparisons.append(PairedComparison(
        label="RQ2: GEPA-30% vs GEPA-100% (Sonnet 4.5)",
        run_a_label="gepa_holdout_30pct_sonnet45_evals5",
        run_b_label="gepa_holdout_100pct_sonnet45_evals5",
        family="rq1_rq2",
    ))

    # RQ3: Model comparisons (baselines)
    comparisons.append(PairedComparison(
        label="RQ3: Haiku vs Sonnet 4.5 (baseline)",
        run_a_label="v5_baseline_haiku_holdout",
        run_b_label="v5_baseline_sonnet45_holdout",
        family="rq3_baselines",
    ))
    comparisons.append(PairedComparison(
        label="RQ3: Haiku vs Sonnet 4.6 (baseline)",
        run_a_label="v5_baseline_haiku_holdout",
        run_b_label="v5_baseline_sonnet46_holdout",
        family="rq3_baselines",
    ))
    comparisons.append(PairedComparison(
        label="RQ3: Sonnet 4.5 vs Sonnet 4.6 (baseline)",
        run_a_label="v5_baseline_sonnet45_holdout",
        run_b_label="v5_baseline_sonnet46_holdout",
        family="rq3_baselines",
    ))

    # RQ3: Model comparisons (best GEPA per model)
    comparisons.append(PairedComparison(
        label="RQ3: Haiku-GEPA vs Sonnet4.5-GEPA (100%)",
        run_a_label="gepa_holdout_100pct_haiku_evals5",
        run_b_label="gepa_holdout_100pct_sonnet45_evals5",
        family="rq3_gepa",
    ))
    comparisons.append(PairedComparison(
        label="RQ3: Haiku-GEPA vs Sonnet4.6-GEPA (100%)",
        run_a_label="gepa_holdout_100pct_haiku_evals5",
        run_b_label="gepa_holdout_100pct_sonnet46_evals5",
        family="rq3_gepa",
    ))
    comparisons.append(PairedComparison(
        label="RQ3: Sonnet4.5-GEPA vs Sonnet4.6-GEPA (100%)",
        run_a_label="gepa_holdout_100pct_sonnet45_evals5",
        run_b_label="gepa_holdout_100pct_sonnet46_evals5",
        family="rq3_gepa",
    ))

    return comparisons


# ===========================================================================
# Apply corrections and print results
# ===========================================================================

def apply_corrections_and_report(
    results: List[ComparisonResult],
    alpha: float = 0.05,
) -> List[ComparisonResult]:
    """Apply Holm-Bonferroni within each family and print results.

    Args:
        results: List of ComparisonResult objects.
        alpha: Family-wise error rate.

    Returns:
        Updated results with corrected significance flags.
    """
    # Group by family
    families = {}
    for r in results:
        if r.family not in families:
            families[r.family] = []
        families[r.family].append(r)

    # Apply Holm-Bonferroni within each family
    for family_name, family_results in families.items():
        # Wilcoxon p-values
        w_pvals = [r.wilcoxon_p for r in family_results]
        w_corrections = holm_bonferroni(w_pvals, alpha)

        # McNemar p-values
        m_pvals = [r.mcnemar_p for r in family_results]
        m_corrections = holm_bonferroni(m_pvals, alpha)

        for i, r in enumerate(family_results):
            r.corrected_alpha = w_corrections[i][0]
            r.wilcoxon_significant = w_corrections[i][1]
            r.mcnemar_significant = m_corrections[i][1]

    return results


def print_results_table(results: List[ComparisonResult]) -> None:
    """Print a formatted results table to console.

    Args:
        results: List of ComparisonResult objects (post-correction).
    """
    print(f"\n{'=' * 110}")
    print(f"  STATISTICAL SIGNIFICANCE RESULTS")
    print(f"{'=' * 110}")

    current_family = ""
    for r in results:
        if r.family != current_family:
            current_family = r.family
            print(f"\n  --- Family: {current_family} ---")
            print(f"  {'Comparison':<50} {'n':>4} {'dF1':>7} {'95% CI':>16} "
                  f"{'W-p':>8} {'r':>6} {'Sig':>4} {'McN-p':>8} {'Disc':>6}")
            print(f"  {'-' * 106}")

        sig_marker = " *" if r.wilcoxon_significant else "  "
        mcn_marker = " *" if r.mcnemar_significant else "  "

        ci_str = f"[{r.ci_lower:+.4f}, {r.ci_upper:+.4f}]"

        print(
            f"  {r.label:<50} {r.n_paired:>4} "
            f"{r.mean_delta_f1:>+.4f} {ci_str:>16} "
            f"{r.wilcoxon_p:>8.4f} {r.effect_size_r:>6.3f}{sig_marker} "
            f"{r.mcnemar_p:>8.4f} {r.discordant_ab:>2}/{r.discordant_ba:<2}{mcn_marker}"
        )

    print(f"\n  * = significant after Holm-Bonferroni correction at alpha = 0.05")
    print(f"  dF1 = mean(B - A); positive = B outperforms A")
    print(f"  r = matched-pairs rank-biserial correlation")
    print(f"  Disc = discordant pairs (A-correct/B-correct)")
    print(f"{'=' * 110}\n")


# ===========================================================================
# JSON output
# ===========================================================================

def write_results_json(
    results: List[ComparisonResult],
    filepath: Path,
) -> None:
    """Write results to JSON for downstream consumption.

    Args:
        results: List of ComparisonResult objects.
        filepath: Output JSON path.
    """
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "n_comparisons": len(results),
            "alpha": 0.05,
            "bootstrap_samples": 10000,
            "bootstrap_seed": 42,
        },
        "comparisons": [asdict(r) for r in results],
    }

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Results JSON written: %s", filepath)


# ===========================================================================
# LaTeX table generation
# ===========================================================================

def write_latex_table(
    results: List[ComparisonResult],
    filepath: Path,
) -> None:
    """Generate a LaTeX table fragment for direct inclusion in the report.

    Args:
        results: List of ComparisonResult objects.
        filepath: Output .tex path.
    """
    lines = []
    lines.append("% Auto-generated by run_statistical_analysis.py")
    lines.append(f"% Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Statistical significance of pairwise comparisons. "
                 r"Wilcoxon signed-rank test on per-record strict F1; "
                 r"bootstrap 95\% CI on mean $\Delta$F1; "
                 r"Holm-Bonferroni correction applied within each family.}")
    lines.append(r"\label{tab:statistical-tests}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{lcrcccc}")
    lines.append(r"\toprule")
    lines.append(r"Comparison & $n$ & $\Delta$F1 & 95\% CI & $p$ (Wilcoxon) & $r$ & Sig. \\")
    lines.append(r"\midrule")

    current_family = ""
    for r in results:
        if r.family != current_family:
            current_family = r.family
            # Add a midrule between families (except the first)
            if lines[-1] != r"\midrule":
                lines.append(r"\midrule")

        sig = r"$\checkmark$" if r.wilcoxon_significant else "--"
        ci_str = f"[{r.ci_lower:+.3f}, {r.ci_upper:+.3f}]"

        # Shorten the label for the table
        short_label = r.label.replace("RQ1: ", "").replace("RQ2: ", "").replace("RQ3: ", "")

        lines.append(
            f"{short_label} & {r.n_paired} & "
            f"{r.mean_delta_f1:+.4f} & {ci_str} & "
            f"{r.wilcoxon_p:.4f} & {r.effect_size_r:.3f} & {sig} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("LaTeX table written: %s", filepath)


# ===========================================================================
# Argument parsing
# ===========================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Statistical significance testing for PAX-AI experiments."
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        required=True,
        help="Base directory containing run subdirectories with per-record CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for JSON and LaTeX results (default: results-dir/stats).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Family-wise error rate (default: 0.05).",
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=10000,
        help="Number of bootstrap resamples (default: 10000).",
    )

    return parser.parse_args()


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Main entry point."""
    args = parse_args()

    output_dir = args.output_dir or (args.results_dir / "stats")
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Discover runs ---
    runs = discover_runs(args.results_dir)

    if not runs:
        logger.error("No runs found in %s", args.results_dir)
        sys.exit(1)

    print(f"\nDiscovered {len(runs)} runs:")
    for label in sorted(runs.keys()):
        print(f"  - {label}")

    # --- Load all per-record data ---
    all_records = {}
    for label, csv_path in runs.items():
        all_records[label] = load_per_record_csv(csv_path)
        logger.info("Loaded %d records from %s", len(all_records[label]), label)

    # --- Build comparisons ---
    comparisons = build_default_comparisons()

    # Filter to only comparisons where both runs exist
    valid_comparisons = []
    for c in comparisons:
        if c.run_a_label not in all_records:
            logger.warning("Skipping '%s': run A '%s' not found", c.label, c.run_a_label)
            continue
        if c.run_b_label not in all_records:
            logger.warning("Skipping '%s': run B '%s' not found", c.label, c.run_b_label)
            continue
        valid_comparisons.append(c)

    logger.info("Running %d comparisons (of %d defined)",
                len(valid_comparisons), len(comparisons))

    # --- Run comparisons ---
    results = []
    for c in valid_comparisons:
        result = run_comparison(all_records[c.run_a_label],
                                all_records[c.run_b_label], c)
        results.append(result)

    # --- Apply corrections and report ---
    results = apply_corrections_and_report(results, alpha=args.alpha)
    print_results_table(results)

    # --- Write outputs ---
    write_results_json(results, output_dir / "statistical_results.json")
    write_latex_table(results, output_dir / "statistical_table.tex")

    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()
