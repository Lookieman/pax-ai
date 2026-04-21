"""
holdout_plots.py
================
Visualisations comparing baseline vs GEPA-optimised holdout results.

Vis 4: Paired F1 scatter plot
Vis 5: Per-field F1 grouped bar chart
Vis 6: Category confusion matrices (before/after)
Vis 7: F1 distribution box/violin plot

All functions accept dicts of HoldoutRecord instances (from load_data.py)
and produce PDF figures for LaTeX inclusion.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
"""

import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from viz.style import (
    apply_style,
    COLOUR_BASELINE, COLOUR_GEPA, COLOUR_GEPA_30, COLOUR_TRANSFER,
    COLOUR_DIAGONAL, CATEGORY_COLOURS,
    FIG_SINGLE, FIG_WIDE, FIG_SQUARE, FIG_PAIR,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Vis 4 — Paired F1 Scatter Plot
# ===================================================================

def plot_paired_scatter(baseline_records, gepa_records, output_path):
    """Plot baseline F1 (x) vs GEPA F1 (y) per holdout record.

    Points above the diagonal indicate improvement.
    Colour-coded by article category (IWL, NIOAI, IWOL).

    Args:
        baseline_records: Dict of PMCID -> HoldoutRecord (baseline).
        gepa_records:     Dict of PMCID -> HoldoutRecord (GEPA).
        output_path:      File path for output PDF.
    """
    apply_style()

    # Align on common PMCIDs
    common_pmcids = sorted(
        set(baseline_records.keys()) & set(gepa_records.keys())
    )

    if not common_pmcids:
        logger.warning("No common PMCIDs between baseline and GEPA results")
        return

    x_vals = []
    y_vals = []
    categories = []

    for pmcid in common_pmcids:
        b_rec = baseline_records[pmcid]
        g_rec = gepa_records[pmcid]
        x_vals.append(b_rec.overall_f1)
        y_vals.append(g_rec.overall_f1)
        # Normalise hybrid categories for colour coding
        cat = b_rec.category_gt
        if "IWL" in cat and "IWOL" in cat:
            cat = "IWL"
        categories.append(cat)

    # Count improved, degraded, unchanged
    n_improved = sum(1 for x, y in zip(x_vals, y_vals) if y > x)
    n_degraded = sum(1 for x, y in zip(x_vals, y_vals) if y < x)
    n_unchanged = len(x_vals) - n_improved - n_degraded

    # Build figure
    fig, ax = plt.subplots(figsize=FIG_SQUARE)

    # Diagonal reference
    ax.plot(
        [0, 1], [0, 1],
        linestyle="--", linewidth=1.0, color=COLOUR_DIAGONAL,
        zorder=1,
    )

    # Shade improvement region
    ax.fill_between(
        [0, 1], [0, 1], [1, 1],
        alpha=0.04, color=COLOUR_GEPA, zorder=0,
    )

    # Scatter by category
    for cat in ["IWL", "NIOAI", "IWOL"]:
        cat_x = [x for x, c in zip(x_vals, categories) if c == cat]
        cat_y = [y for y, c in zip(y_vals, categories) if c == cat]
        if cat_x:
            colour = CATEGORY_COLOURS.get(cat, COLOUR_DIAGONAL)
            ax.scatter(
                cat_x, cat_y,
                color=colour, s=50, alpha=0.75,
                edgecolors="white", linewidths=0.5,
                label=f"{cat} (n={len(cat_x)})",
                zorder=3,
            )

    ax.set_xlabel("Baseline F1")
    ax.set_ylabel("GEPA-optimised F1")
    ax.set_title("Paired F1 Comparison: Baseline vs GEPA")
    ax.set_xlim(-0.02, 1.05)
    ax.set_ylim(-0.02, 1.05)
    ax.set_aspect("equal")
    ax.legend(loc="upper left", framealpha=0.9)

    # Summary annotation
    summary_text = (
        f"Improved: {n_improved}\n"
        f"Degraded: {n_degraded}\n"
        f"Unchanged: {n_unchanged}"
    )
    ax.text(
        0.97, 0.03, summary_text,
        transform=ax.transAxes, fontsize=8,
        verticalalignment="bottom", horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved paired scatter to %s", output_path)


# ===================================================================
# Vis 5 — Per-Field F1 Grouped Bar Chart
# ===================================================================

def plot_per_field_bars(baseline_records, gepa_records, output_path,
                       fields=None):
    """Plot per-field micro F1 as grouped bars (baseline vs GEPA).

    Aggregates TP/FP/FN across all holdout records for each field,
    then computes micro F1 per field.

    Args:
        baseline_records: Dict of PMCID -> HoldoutRecord (baseline).
        gepa_records:     Dict of PMCID -> HoldoutRecord (GEPA).
        output_path:      File path for output PDF.
        fields:           Optional list of field names to include.
    """
    apply_style()

    if fields is None:
        fields = [
            "serotype", "mlst", "ast_data", "amr",
            "virulence_genes", "plasmid",
        ]

    common_pmcids = sorted(
        set(baseline_records.keys()) & set(gepa_records.keys())
    )

    if not common_pmcids:
        logger.warning("No common PMCIDs for per-field bars")
        return

    baseline_f1s = {}
    gepa_f1s = {}

    for field in fields:
        b_tp, b_fp, b_fn = 0, 0, 0
        g_tp, g_fp, g_fn = 0, 0, 0

        for pmcid in common_pmcids:
            b_field = baseline_records[pmcid].per_field_scores.get(field, {})
            g_field = gepa_records[pmcid].per_field_scores.get(field, {})

            b_tp += b_field.get("tp", 0)
            b_fp += b_field.get("fp", 0)
            b_fn += b_field.get("fn", 0)

            g_tp += g_field.get("tp", 0)
            g_fp += g_field.get("fp", 0)
            g_fn += g_field.get("fn", 0)

        baseline_f1s[field] = _compute_f1(b_tp, b_fp, b_fn)
        gepa_f1s[field] = _compute_f1(g_tp, g_fp, g_fn)

    # Filter out fields with zero data in both conditions
    active_fields = [
        f for f in fields
        if baseline_f1s[f] > 0 or gepa_f1s[f] > 0
    ]

    if not active_fields:
        logger.warning("No fields with data; skipping per-field bars")
        return

    # Build figure
    fig, ax = plt.subplots(figsize=FIG_WIDE)

    x_pos = np.arange(len(active_fields))
    bar_width = 0.35

    b_vals = [baseline_f1s[f] for f in active_fields]
    g_vals = [gepa_f1s[f] for f in active_fields]

    bars_b = ax.bar(
        x_pos - bar_width / 2, b_vals, bar_width,
        label="Baseline", color=COLOUR_BASELINE, alpha=0.85,
    )
    bars_g = ax.bar(
        x_pos + bar_width / 2, g_vals, bar_width,
        label="GEPA-optimised", color=COLOUR_GEPA, alpha=0.85,
    )

    # Value labels on bars
    for bar_group in [bars_b, bars_g]:
        for bar in bar_group:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, height + 0.01,
                    f"{height:.2f}",
                    ha="center", va="bottom", fontsize=7,
                )

    ax.set_xlabel("Extraction field")
    ax.set_ylabel("Micro F1")
    ax.set_title("Per-Field F1: Baseline vs GEPA")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(
        [_format_field_label(f) for f in active_fields],
        rotation=30, ha="right",
    )
    ax.set_ylim(0, 1.1)
    ax.legend()

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved per-field bars to %s", output_path)


# ===================================================================
# Vis 6 — Category Confusion Matrices (Before/After)
# ===================================================================

def plot_confusion_matrices(baseline_records, gepa_records, output_path):
    """Plot side-by-side 3x3 confusion matrices for baseline and GEPA.

    Categories: IWL, NIOAI, IWOL.

    Args:
        baseline_records: Dict of PMCID -> HoldoutRecord (baseline).
        gepa_records:     Dict of PMCID -> HoldoutRecord (GEPA).
        output_path:      File path for output PDF.
    """
    apply_style()

    categories = ["IWL", "NIOAI", "IWOL"]

    # Normalise hybrid categories (e.g. IWL+IWOL -> IWL for matrix)
    def _normalise_cat(cat):
        """Map hybrid categories to their primary category."""
        if "IWL" in cat and "IWOL" in cat:
            return "IWL"      # IWL+IWOL treated as IWL for confusion
        return cat

    common_pmcids = sorted(
        set(baseline_records.keys()) & set(gepa_records.keys())
    )

    if not common_pmcids:
        logger.warning("No common PMCIDs for confusion matrices")
        return

    # Collect ground truth and predictions
    b_true = []
    b_pred = []
    g_true = []
    g_pred = []

    for pmcid in common_pmcids:
        b_rec = baseline_records[pmcid]
        g_rec = gepa_records[pmcid]
        b_true.append(_normalise_cat(b_rec.category_gt))
        b_pred.append(_normalise_cat(b_rec.category_pred))
        g_true.append(_normalise_cat(g_rec.category_gt))
        g_pred.append(_normalise_cat(g_rec.category_pred))

    b_cm = _build_confusion_matrix(b_true, b_pred, categories)
    g_cm = _build_confusion_matrix(g_true, g_pred, categories)

    # Build figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_PAIR)

    _draw_confusion(ax1, b_cm, categories, "Baseline")
    _draw_confusion(ax2, g_cm, categories, "GEPA-optimised")

    fig.suptitle("Category Classification Confusion Matrices", fontsize=11)
    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved confusion matrices to %s", output_path)


# ===================================================================
# Vis 7 — F1 Distribution Box/Violin Plot
# ===================================================================

def plot_f1_distribution(condition_data, output_path):
    """Plot side-by-side violin plots of per-record F1 distributions.

    Args:
        condition_data: Dict mapping condition label to list of F1 scores.
                        Example: {"Baseline": [0.5, 0.8, ...],
                                  "GEPA-100%": [0.6, 0.9, ...],
                                  "GEPA-30%": [0.55, 0.85, ...]}
        output_path:    File path for output PDF.
    """
    apply_style()

    labels = list(condition_data.keys())
    data_lists = [condition_data[label] for label in labels]

    if not data_lists or all(len(d) == 0 for d in data_lists):
        logger.warning("No F1 data available for distribution plot")
        return

    palette = [COLOUR_BASELINE, COLOUR_GEPA, COLOUR_GEPA_30]

    fig, ax = plt.subplots(figsize=FIG_SINGLE)

    # Violin plot
    parts = ax.violinplot(
        data_lists,
        positions=range(len(labels)),
        showmeans=True, showmedians=True, showextrema=False,
    )

    # Colour the violins
    for i, body in enumerate(parts["bodies"]):
        colour_idx = min(i, len(palette) - 1)
        body.set_facecolor(palette[colour_idx])
        body.set_alpha(0.3)

    # Overlay individual points (strip plot)
    for i, scores in enumerate(data_lists):
        jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(scores))
        x_points = [i + j for j in jitter]
        colour_idx = min(i, len(palette) - 1)
        ax.scatter(
            x_points, scores,
            color=palette[colour_idx], s=20, alpha=0.6,
            edgecolors="white", linewidths=0.3,
            zorder=3,
        )

    # Mean labels
    for i, scores in enumerate(data_lists):
        mean_val = np.mean(scores)
        ax.text(
            i, mean_val + 0.02, f"{mean_val:.3f}",
            ha="center", va="bottom", fontsize=8, fontweight="bold",
        )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Per-record F1")
    ax.set_title("F1 Score Distribution by Condition")
    ax.set_ylim(-0.02, 1.1)

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved F1 distribution plot to %s", output_path)


# ===================================================================
# Vis 9 -- Cross-Model Prompt Transfer Bar Chart
# ===================================================================

def plot_cross_model_transfer(transfer_data, output_path):
    """Plot grouped bar chart for cross-model prompt transfer results.

    Shows per-model performance across three conditions:
    native baseline, native GEPA-optimised, and transferred prompt
    (Sonnet 4.5 GEPA prompt applied to each model).

    Args:
        transfer_data: Dict with the following structure:
            {
                "models": ["Haiku 4.5", "Sonnet 4.5", "Sonnet 4.6", "Opus 4.6"],
                "conditions": {
                    "Native baseline": {
                        "Haiku 4.5": <mean_f1 or micro_f1>,
                        "Sonnet 4.5": ...,
                        "Sonnet 4.6": ...,
                    },
                    "Native GEPA": {
                        "Haiku 4.5": ...,
                        "Sonnet 4.5": ...,
                        "Sonnet 4.6": ...,
                    },
                    "S4.5 prompt transfer": {
                        "Haiku 4.5": ...,
                        "Sonnet 4.5": ...,  # same as Native GEPA for the source model
                        "Sonnet 4.6": ...,
                        "Opus 4.6": ...,
                    },
                },
                "metric_label": "Mean F1" or "Micro F1",
            }
        output_path: File path for output PDF.
    """
    apply_style()

    models = transfer_data["models"]
    conditions = transfer_data["conditions"]
    metric_label = transfer_data.get("metric_label", "Mean F1")
    n_models = len(models)
    condition_labels = list(conditions.keys())
    n_conditions = len(condition_labels)

    # Colour assignment per condition
    palette = [COLOUR_BASELINE, COLOUR_GEPA, COLOUR_TRANSFER]
    # Extend if more than 3 conditions
    while len(palette) < n_conditions:
        palette.append(COLOUR_GEPA_30)

    # Build figure
    fig, ax = plt.subplots(figsize=FIG_WIDE)

    bar_width = 0.8 / n_conditions
    x_pos = np.arange(n_models)

    for c_idx, cond_label in enumerate(condition_labels):
        cond_scores = conditions[cond_label]
        values = []
        for model in models:
            values.append(cond_scores.get(model, 0.0))

        offset = (c_idx - (n_conditions - 1) / 2) * bar_width
        bars = ax.bar(
            x_pos + offset, values, bar_width,
            label=cond_label, color=palette[c_idx], alpha=0.85,
        )

        # Value labels on bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, height + 0.008,
                    f"{height:.3f}",
                    ha="center", va="bottom", fontsize=7,
                )

    ax.set_xlabel("Model")
    ax.set_ylabel(metric_label)
    ax.set_title("Cross-Model Prompt Transfer: S4.5 GEPA Prompt on Other Models")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(models, fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", fontsize=8)

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved cross-model transfer plot to %s", output_path)


# ===================================================================
# Vis 10 -- Predict vs CoT Ablation Bar Chart                        #changed_16042026
# ===================================================================

def plot_ablation_bar(                                                         #changed_16042026
    predict_records,                                                           #changed_16042026
    cot_records,                                                               #changed_16042026
    output_path,                                                               #changed_16042026
    gepa_records=None,                                                         #changed_16042026
    gepa_best_micro_f1=None,                                                   #changed_16042026
    model_label="Sonnet 4.5",                                                  #changed_16042026
):                                                                             #changed_16042026
    """Plot strict micro F1 progression: Predict -> CoT -> CoT+GEPA.          #changed_16042026

    When gepa_records is provided, a third bar is rendered for the GEPA       #changed_16042026
    optimised condition and the dashed reference line is suppressed (it would  #changed_16042026
    be redundant). When gepa_records is absent, the reference line is shown   #changed_16042026
    if gepa_best_micro_f1 is supplied.                                        #changed_16042026

    Strict micro F1 is computed by aggregating TP/FP/FN across all fields    #changed_16042026
    in per_field_scores for every record in the dict.                         #changed_16042026

    Args:                                                                      #changed_16042026
        predict_records:    Dict of PMCID -> HoldoutRecord (Predict run).     #changed_16042026
        cot_records:        Dict of PMCID -> HoldoutRecord (CoT run).         #changed_16042026
        output_path:        File path for output PDF.                          #changed_16042026
        gepa_records:       Optional dict of PMCID -> HoldoutRecord (GEPA     #changed_16042026
                            optimised run). Adds a third bar when provided.   #changed_16042026
        gepa_best_micro_f1: Optional float; fallback dashed reference line    #changed_16042026
                            used only when gepa_records is None.              #changed_16042026
        model_label:        Model name for the chart title.                   #changed_16042026
    """                                                                        #changed_16042026
    apply_style()                                                              #changed_16042026

    def _micro_f1_from_records(records):                                       #changed_16042026
        """Aggregate TP/FP/FN across all records and fields, return micro F1.  #changed_16042026

        HoldoutRecord stores per-field TP/FP/FN in per_field_scores rather    #changed_16042026
        than as top-level attributes, so we sum across all fields per record.  #changed_16042026
        """                                                                    #changed_16042026
        total_tp = 0                                                           #changed_16042026
        total_fp = 0                                                           #changed_16042026
        total_fn = 0                                                           #changed_16042026
        for rec in records.values():                                           #changed_16042026
            for field_scores in rec.per_field_scores.values():                 #changed_16042026
                total_tp += field_scores.get("tp", 0)                         #changed_16042026
                total_fp += field_scores.get("fp", 0)                         #changed_16042026
                total_fn += field_scores.get("fn", 0)                         #changed_16042026
        return _compute_f1(total_tp, total_fp, total_fn)                      #changed_16042026

    predict_f1 = _micro_f1_from_records(predict_records)                      #changed_16042026
    cot_f1 = _micro_f1_from_records(cot_records)                              #changed_16042026

    labels = ["Predict\n(zero-shot)", "CoT\n(baseline)"]                      #changed_16042026
    values = [predict_f1, cot_f1]                                             #changed_16042026
    colours = [COLOUR_BASELINE, COLOUR_GEPA_30]                               #changed_16042026

    # Add GEPA bar if records are provided                                     #changed_16042026
    if gepa_records:                                                           #changed_16042026
        gepa_f1 = _micro_f1_from_records(gepa_records)                        #changed_16042026
        labels.append("CoT + GEPA\n(optimised)")                              #changed_16042026
        values.append(gepa_f1)                                                 #changed_16042026
        colours.append(COLOUR_GEPA)                                            #changed_16042026

    fig, ax = plt.subplots(figsize=FIG_SINGLE)                                #changed_16042026

    bars = ax.bar(                                                             #changed_16042026
        labels, values, width=0.45,                                           #changed_16042026
        color=colours, alpha=0.85,                                            #changed_16042026
    )                                                                          #changed_16042026

    # Value labels on bars                                                     #changed_16042026
    for bar in bars:                                                           #changed_16042026
        height = bar.get_height()                                              #changed_16042026
        ax.text(                                                               #changed_16042026
            bar.get_x() + bar.get_width() / 2, height + 0.008,               #changed_16042026
            f"{height:.4f}",                                                  #changed_16042026
            ha="center", va="bottom", fontsize=9, fontweight="bold",          #changed_16042026
        )                                                                      #changed_16042026

    # Dashed reference line only when no GEPA bar is present                  #changed_16042026
    if gepa_records is None and gepa_best_micro_f1 is not None:               #changed_16042026
        ax.axhline(                                                            #changed_16042026
            y=gepa_best_micro_f1,                                             #changed_16042026
            linestyle="--", linewidth=1.2, color=COLOUR_DIAGONAL,             #changed_16042026
            label=f"GEPA best ({gepa_best_micro_f1:.4f})",                    #changed_16042026
        )                                                                      #changed_16042026
        ax.legend(fontsize=8, loc="lower right")                              #changed_16042026

    ax.set_ylabel("Strict Micro F1")                                          #changed_16042026
    ax.set_title(                                                              #changed_16042026
        f"Predict vs ChainOfThought vs ChainOfThought + GEPA -- {model_label} (n=35 holdout)", #changed_16042026
        fontsize=10,                                                           #changed_16042026
    )                                                                          #changed_16042026
    ax.set_ylim(0, 1.05)                                                      #changed_16042026

    fig.savefig(output_path, format="pdf")                                    #changed_16042026
    plt.close(fig)                                                            #changed_16042026
    logger.info("Saved ablation bar chart to %s", output_path)                #changed_16042026




def _compute_f1(tp, fp, fn):
    """Compute F1 from TP, FP, FN counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _format_field_label(field_name):
    """Format a field name for display on axis labels."""
    replacements = {
        "ast_data": "AST",
        "amr": "AMR Genes",
        "virulence_genes": "Virulence",
        "plasmid": "Plasmid",
        "serotype": "Serotype",
        "mlst": "MLST",
        "cgmlst": "cgMLST",
        "pfge": "PFGE",
        "phage_type": "Phage Type",
    }
    return replacements.get(field_name, field_name)


def _build_confusion_matrix(y_true, y_pred, labels):
    """Build a confusion matrix as a 2D list.

    Args:
        y_true:  List of ground truth labels.
        y_pred:  List of predicted labels.
        labels:  Ordered list of category labels.

    Returns:
        2D list: matrix[true_idx][pred_idx] = count.
    """
    n = len(labels)
    label_to_idx = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * n for _ in range(n)]

    for true_val, pred_val in zip(y_true, y_pred):
        t_idx = label_to_idx.get(true_val, -1)
        p_idx = label_to_idx.get(pred_val, -1)
        if t_idx >= 0 and p_idx >= 0:
            matrix[t_idx][p_idx] += 1

    return matrix


def _draw_confusion(ax, matrix, labels, title):
    """Draw a single confusion matrix heatmap on an axes.

    Args:
        ax:     Matplotlib axes object.
        matrix: 2D list of counts.
        labels: List of category labels.
        title:  Subplot title.
    """
    matrix_np = np.array(matrix)
    n = len(labels)

    im = ax.imshow(matrix_np, cmap="Blues", interpolation="nearest")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Predicted", fontsize=9)
    ax.set_ylabel("Ground Truth", fontsize=9)
    ax.set_title(title, fontsize=10)

    # Annotate cells with counts
    for i in range(n):
        for j in range(n):
            val = matrix_np[i, j]
            text_colour = "white" if val > matrix_np.max() / 2 else "black"
            ax.text(
                j, i, str(int(val)),
                ha="center", va="center",
                fontsize=12, fontweight="bold",
                color=text_colour,
            )

    # Compute and display accuracy
    correct = sum(matrix_np[i][i] for i in range(n))
    total = matrix_np.sum()
    accuracy = correct / total if total > 0 else 0.0
    ax.text(
        0.5, -0.15, f"Accuracy: {accuracy:.1%}",
        transform=ax.transAxes, ha="center", fontsize=8,
    )
