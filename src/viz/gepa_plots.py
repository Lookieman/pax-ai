"""
gepa_plots.py
=============
Visualisations derived from GEPA optimisation internals.

Vis 1: Score convergence curve
Vis 2: Pareto frontier size over iterations
Vis 3: Per-validation-record improvement heatmap
Vis 8: GEPA optimisation trajectory DAG

All functions accept a GEPAData instance (from load_data.py) and an
output path, and produce a PDF figure for LaTeX inclusion.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
"""

import os
import logging
import numpy as np
import matplotlib.pyplot as plt

from viz.style import (
    apply_style,
    COLOUR_BASELINE, COLOUR_GEPA, COLOUR_BEST,
    COLOUR_PARETO, COLOUR_DEFAULT_NODE,
    FIG_SINGLE, FIG_WIDE,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Vis 1 — Score Convergence Curve
# ===================================================================

def plot_convergence(gepa_data, output_path, baseline_f1=None):
    """Plot validation aggregate score vs candidate index.

    Shows individual candidate scores as scatter points and a running
    best line. Optionally overlays a horizontal baseline reference.

    Args:
        gepa_data:   GEPAData instance.
        output_path: File path for output PDF.
        baseline_f1: Optional float for baseline reference line.
    """
    apply_style()

    scores = gepa_data.val_aggregate_scores
    n_candidates = len(scores)
    x_axis = list(range(n_candidates))

    # Compute running best (cumulative maximum)
    running_best = []
    current_best = float("-inf")
    for score in scores:
        current_best = max(current_best, score)
        running_best.append(current_best)

    # Build figure
    fig, ax = plt.subplots(figsize=FIG_SINGLE)

    ax.scatter(
        x_axis, scores,
        alpha=0.45, s=30, color=COLOUR_GEPA,
        label="Candidate score", zorder=3,
    )
    ax.plot(
        x_axis, running_best,
        color=COLOUR_BEST, linewidth=2.0,
        label="Running best", zorder=4,
    )

    if baseline_f1 is not None:
        ax.axhline(
            y=baseline_f1, linestyle="--", linewidth=1.2,
            color=COLOUR_BASELINE, label=f"v4 Sonnet baseline ({baseline_f1:.3f})",
            zorder=2,
        )

    ax.set_xlabel("Candidate index")
    ax.set_ylabel("Validation aggregate F1")
    ax.set_title("GEPA Score Convergence")
    ax.legend(loc="lower right")

    # Annotate best
    best_idx = gepa_data.best_idx
    best_score = scores[best_idx]
    ax.annotate(
        f"Best: {best_score:.3f} (#{best_idx})",
        xy=(best_idx, best_score),
        xytext=(best_idx + 1, best_score - 0.03),
        arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
        fontsize=8,
    )

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved convergence curve to %s", output_path)


# ===================================================================
# Vis 2 — Pareto Frontier Size Over Iterations
# ===================================================================

def plot_pareto_frontier_size(gepa_data, output_path):
    """Plot number of Pareto-dominant candidates as candidates accumulate.

    A growing frontier indicates GEPA finding complementary strategies;
    a stable frontier indicates refinement of existing strategies.

    Args:
        gepa_data:   GEPAData instance.
        output_path: File path for output PDF.
    """
    apply_style()

    subscores = gepa_data.val_subscores
    n_candidates = len(subscores)

    if n_candidates == 0:
        logger.warning("No val_subscores available; skipping Pareto plot")
        return

    # Convert subscores to matrix form [candidate][record] -> float
    score_matrix = _subscores_to_matrix(subscores)

    # Compute frontier size at each step (manual Pareto check)
    frontier_sizes = []
    for i in range(1, n_candidates + 1):
        subset = score_matrix[:i]
        dominators = _manual_pareto_check(subset)
        frontier_sizes.append(len(dominators))

    # Build figure
    fig, ax = plt.subplots(figsize=FIG_SINGLE)

    x_axis = list(range(1, n_candidates + 1))
    ax.plot(x_axis, frontier_sizes, marker="o", markersize=4, color=COLOUR_PARETO)
    ax.fill_between(x_axis, frontier_sizes, alpha=0.15, color=COLOUR_PARETO)

    ax.set_xlabel("Number of candidates evaluated")
    ax.set_ylabel("Pareto frontier size")
    ax.set_title("Pareto Frontier Growth")
    ax.set_xlim(1, n_candidates)
    ax.yaxis.get_major_locator().set_params(integer=True)

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved Pareto frontier plot to %s", output_path)


# ===================================================================
# Vis 3 — Per-Validation-Record Improvement Heatmap
# ===================================================================

def plot_record_heatmap(gepa_data, output_path, val_pmcids=None):
    """Plot heatmap of per-record F1 scores across GEPA candidates.

    Rows = validation records (18), columns = candidate indices.
    Colour intensity = F1 score (red=low, green=high).

    Args:
        gepa_data:   GEPAData instance.
        output_path: File path for output PDF.
        val_pmcids:  Optional list of 18 PMCID strings for row labels.
    """
    apply_style()

    subscores = gepa_data.val_subscores
    n_candidates = len(subscores)
    if n_candidates == 0:
        logger.warning("No val_subscores available; skipping heatmap")
        return

    # Build matrix: rows = records, cols = candidates
    score_matrix = _subscores_to_matrix(subscores)
    matrix_np = np.array(score_matrix).T  # shape: (n_records, n_candidates)

    n_records = matrix_np.shape[0]

    # Subsample columns if too many candidates for readability
    max_cols = 25
    if n_candidates > max_cols:
        step = n_candidates // max_cols
        col_indices = list(range(0, n_candidates, step))
        if (n_candidates - 1) not in col_indices:
            col_indices.append(n_candidates - 1)
        matrix_np = matrix_np[:, col_indices]
        col_labels = [str(c) for c in col_indices]
    else:
        col_labels = [str(c) for c in range(n_candidates)]

    # Row labels
    if val_pmcids and len(val_pmcids) == n_records:
        row_labels = [p[-7:] for p in val_pmcids]
    else:
        row_labels = [f"task_{i}" for i in range(n_records)]

    # Build figure
    fig_height = max(4, n_records * 0.35)
    fig_width = max(8, len(col_labels) * 0.45)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    im = ax.imshow(
        matrix_np, aspect="auto", cmap="RdYlGn",
        vmin=0.0, vmax=1.0, interpolation="nearest",
    )

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(n_records))
    ax.set_yticklabels(row_labels, fontsize=7)

    ax.set_xlabel("Candidate index")
    ax.set_ylabel("Validation record")
    ax.set_title("Per-Record F1 Across GEPA Candidates")

    # Annotate cells if small enough
    if len(col_labels) <= 25 and n_records <= 20:
        for r in range(n_records):
            for c in range(len(col_labels)):
                val = matrix_np[r, c]
                text_colour = "white" if val < 0.4 else "black"
                ax.text(
                    c, r, f"{val:.2f}",
                    ha="center", va="center",
                    fontsize=6, color=text_colour,
                )

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("F1 Score")

    fig.savefig(output_path, format="pdf")
    plt.close(fig)
    logger.info("Saved record heatmap to %s", output_path)


# ===================================================================
# Vis 8 — GEPA Optimisation Trajectory DAG
# ===================================================================

def plot_dag(gepa_data, output_path):
    """Build and render the GEPA lineage DAG as a PDF.

    Nodes = candidate programmes, labelled with index and score.
    Edges = parent-child relationships.
    Colour coding: best=cyan, Pareto=gold, others=grey.

    Requires the graphviz Python package and the dot binary on PATH.

    Args:
        gepa_data:   GEPAData instance.
        output_path: File path for output PDF (without extension;
                     graphviz appends .pdf automatically).
    """
    try:
        import graphviz
    except ImportError:
        logger.error(
            "graphviz package not installed. "
            "Run: pip install graphviz"
        )
        return

    parents = gepa_data.parents
    scores = gepa_data.val_aggregate_scores
    best_idx = gepa_data.best_idx
    n_candidates = len(scores)

    if not parents or n_candidates == 0:
        logger.warning("No parent or score data available; skipping DAG")
        return

    # Identify Pareto-dominant candidates
    pareto_indices = set()
    if gepa_data.val_subscores:                                      #changed_100426
        score_matrix = _subscores_to_matrix(gepa_data.val_subscores) #changed_100426
        pareto_indices = set(_manual_pareto_check(score_matrix))     #changed_100426

    # Choose layout direction based on candidate count
    rankdir = "LR" if n_candidates > 15 else "TB"

    # Build DOT string
    dot_lines = [
        "digraph GEPA {",
        f"  rankdir={rankdir};",
        '  node [shape=ellipse, style=filled, fontsize=9];',
        '  edge [arrowsize=0.7];',
    ]

    for i in range(n_candidates):
        label = f"{i}\\n{scores[i]:.3f}"

        if i == best_idx:
            fill_colour = COLOUR_BEST
        elif i in pareto_indices:
            fill_colour = COLOUR_PARETO
        else:
            fill_colour = COLOUR_DEFAULT_NODE

        dot_lines.append(
            f'  {i} [label="{label}", fillcolor="{fill_colour}"];'
        )

    for i in range(n_candidates):
        if i < len(parents) and parents[i] is not None:
            for parent_idx in parents[i]:
                if parent_idx is not None:
                    dot_lines.append(f"  {parent_idx} -> {i};")

    dot_lines.append("}")
    dot_string = "\n".join(dot_lines)

    # Strip .pdf extension if present (graphviz adds it)
    output_stem = output_path
    if output_stem.endswith(".pdf"):
        output_stem = output_stem[:-4]

    # Render
    graph = graphviz.Source(dot_string)
    rendered_path = graph.render(
        filename=output_stem, format="pdf", cleanup=True
    )
    logger.info("Saved GEPA DAG to %s", rendered_path)


# ===================================================================
# Internal helpers
# ===================================================================

def _subscores_to_matrix(subscores):
    """Convert list-of-dicts subscores to list-of-lists matrix.

    Args:
        subscores: List of dicts, each {record_idx: score}.

    Returns:
        List of lists: [candidate_idx][record_idx] = score.
    """
    matrix = []
    for entry in subscores:
        if isinstance(entry, dict):
            # Sort by key to ensure consistent record ordering
            sorted_keys = sorted(entry.keys(), key=int)
            row = [entry[k] for k in sorted_keys]
        elif isinstance(entry, list):
            row = list(entry)
        else:
            row = []
        matrix.append(row)
    return matrix


def _manual_pareto_check(score_matrix):
    """Identify Pareto-dominant candidates from a score matrix.

    A candidate i dominates candidate j if i >= j on all objectives
    and strictly > on at least one. A candidate is Pareto-optimal
    (non-dominated) if no other candidate dominates it.

    Args:
        score_matrix: List of lists [candidate][record] = score.

    Returns:
        List of non-dominated candidate indices.
    """
    n = len(score_matrix)
    non_dominated = []

    for i in range(n):
        dominated = False
        for j in range(n):
            if i == j:
                continue
            # Check if j dominates i
            all_geq = True
            any_greater = False
            for k in range(len(score_matrix[i])):
                if score_matrix[j][k] < score_matrix[i][k]:
                    all_geq = False
                    break
                if score_matrix[j][k] > score_matrix[i][k]:
                    any_greater = True
            if all_geq and any_greater:
                dominated = True
                break
        if not dominated:
            non_dominated.append(i)

    return non_dominated
