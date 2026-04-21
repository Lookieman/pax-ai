"""
style.py
========
Shared matplotlib style configuration for all report figures.

Sets up consistent fonts, colours, and sizing suitable for LaTeX
embedding via includegraphics.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
"""

import matplotlib
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------
# Use non-interactive backend for PDF generation
# -----------------------------------------------------------------------
matplotlib.use("Agg")

# -----------------------------------------------------------------------
# Colour palette (colourblind-friendly where possible)
# -----------------------------------------------------------------------
COLOUR_BASELINE = "#4477AA"       # Steel blue
COLOUR_GEPA = "#EE6677"          # Rose
COLOUR_GEPA_30 = "#228833"       # Forest green
COLOUR_TRANSFER = "#AA3377"      # Purple (cross-model transfer)
COLOUR_BEST = "#66CCEE"          # Cyan (best candidate in DAG)
COLOUR_PARETO = "#CCBB44"        # Sand/gold (Pareto front in DAG)
COLOUR_DEFAULT_NODE = "#BBBBBB"  # Light grey (other candidates in DAG)
COLOUR_DIAGONAL = "#999999"      # Grey (reference lines)
COLOUR_IWL = "#4477AA"           # Category: IWL
COLOUR_NIOAI = "#EE6677"         # Category: NIOAI
COLOUR_IWOL = "#228833"          # Category: IWOL

CATEGORY_COLOURS = {
    "IWL": COLOUR_IWL,
    "NIOAI": COLOUR_NIOAI,
    "IWOL": COLOUR_IWOL,
}

# -----------------------------------------------------------------------
# Figure sizing (inches) — single-column LaTeX width ~3.5in, full ~7in
# -----------------------------------------------------------------------
FIG_SINGLE = (7, 4)          # Standard single figure
FIG_WIDE = (10, 5)           # Wide figure (grouped bars, heatmaps)
FIG_SQUARE = (6, 6)          # Square figure (scatter, confusion)
FIG_PAIR = (10, 4)           # Side-by-side pair (confusion matrices)


def apply_style():
    """Apply consistent matplotlib style for all report figures."""
    plt.rcParams.update({
        # Font
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,

        # Lines and markers
        "lines.linewidth": 1.5,
        "lines.markersize": 5,

        # Axes
        "axes.grid": True,
        "axes.grid.which": "major",
        "grid.alpha": 0.3,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,

        # Figure
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,

        # PDF backend for vector output
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
