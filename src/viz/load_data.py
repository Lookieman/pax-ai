"""
load_data.py
============
Data loading utilities for GEPA experiment outputs and holdout results.

Reads from:
- gepa_state.bin          (pickle, GEPA checkpoint with lineage data)
- detailed_results.json   (aggregate scores, per-record bests)
- holdout result JSONs    (per-record RecordResult from run_holdout.py)

Field name mapping (gepa_state.bin -> DspyGEPAResult):
    parent_program_for_candidate  -> parents
    prog_candidate_val_subscores  -> val_subscores
    num_metric_calls_by_discovery -> discovery_eval_counts
    program_candidates            -> candidates
    full_program_trace            -> (bonus iteration trace)

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   April 2026
"""

import json
import pickle
import os
import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# GEPA data structures
# -----------------------------------------------------------------------

class GEPAData:
    """Container for all GEPA experiment data needed by visualisations."""

    def __init__(self):
        self.val_aggregate_scores = []
        self.parents = []
        self.val_subscores = []
        self.discovery_eval_counts = []
        self.best_idx = -1
        self.full_program_trace = []
        self.total_metric_calls = 0
        self.num_full_evals = 0
        self.n_candidates = 0
        self.n_val_records = 0
        self.experiment_name = ""
        self.student_model = ""
        self.split_pct = 0

    def summary(self):
        """Print a human-readable summary of loaded data."""
        lines = [
            "GEPA Data Summary",
            "=" * 40,
            f"  Experiment       : {self.experiment_name}",
            f"  Student model    : {self.student_model}",
            f"  Split pct        : {self.split_pct}%",
            f"  Candidates       : {self.n_candidates}",
            f"  Validation recs  : {self.n_val_records}",
            f"  Best candidate   : {self.best_idx}",
            f"  Best score       : {self.val_aggregate_scores[self.best_idx]:.4f}" if self.best_idx >= 0 else "  Best score       : N/A",
            f"  Total metric calls: {self.total_metric_calls}",
            f"  Full evals       : {self.num_full_evals}",
            f"  Parents populated: {len(self.parents) > 0 and self.parents[0] is not None}",
            "=" * 40,
        ]
        return "\n".join(lines)


def load_gepa_data(experiment_dir):
    """Load all GEPA data from an experiment directory.

    Args:
        experiment_dir: Path to experiment folder containing
                        gepa_state.bin, detailed_results.json,
                        and experiment_metadata.json.

    Returns:
        GEPAData instance with all fields populated.
    """
    experiment_dir = str(experiment_dir)
    data = GEPAData()

    # -------------------------------------------------------------------
    # 1. Load experiment metadata
    # -------------------------------------------------------------------
    metadata_path = os.path.join(experiment_dir, "experiment_metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        data.experiment_name = meta.get("experiment_name", "")
        data.student_model = meta.get("student_model", "")
        data.split_pct = meta.get("split_pct", 0)
        logger.info("Loaded experiment metadata: %s", data.experiment_name)
    else:
        logger.warning("No experiment_metadata.json found in %s", experiment_dir)

    # -------------------------------------------------------------------
    # 2. Load detailed_results.json (aggregate scores)
    # -------------------------------------------------------------------
    dr_path = os.path.join(experiment_dir, "detailed_results.json")
    if os.path.exists(dr_path):
        with open(dr_path, "r", encoding="utf-8") as fh:
            dr = json.load(fh)
        data.val_aggregate_scores = dr.get("val_aggregate_scores", [])
        logger.info(
            "Loaded %d aggregate scores from detailed_results.json",
            len(data.val_aggregate_scores),
        )
    else:
        logger.warning("No detailed_results.json found in %s", experiment_dir)

    # -------------------------------------------------------------------
    # 3. Load gepa_state.bin (lineage + per-record scores)
    # -------------------------------------------------------------------
    state_path = os.path.join(
        experiment_dir, "gepa_logs", "gepa_state.bin"
    )
    if os.path.exists(state_path):
        with open(state_path, "rb") as fh:
            state = pickle.load(fh)

        # Parents (lineage)
        raw_parents = state.get("parent_program_for_candidate", [])
        data.parents = raw_parents

        # Per-record validation subscores
        raw_subscores = state.get("prog_candidate_val_subscores", [])
        data.val_subscores = raw_subscores

        # Discovery eval counts
        data.discovery_eval_counts = state.get(
            "num_metric_calls_by_discovery", []
        )

        # Iteration trace
        data.full_program_trace = state.get("full_program_trace", [])

        # Run totals
        data.total_metric_calls = state.get("total_num_evals", 0)
        data.num_full_evals = state.get("num_full_ds_evals", 0)

        # Fall back to state scores if detailed_results.json was missing
        if not data.val_aggregate_scores and raw_subscores:
            logger.info("Deriving aggregate scores from state subscores")
            for subscore_dict in raw_subscores:
                values = list(subscore_dict.values())
                mean_score = sum(values) / len(values) if values else 0.0
                data.val_aggregate_scores.append(mean_score)

        logger.info(
            "Loaded gepa_state.bin: %d candidates, %d trace entries",
            len(raw_parents),
            len(data.full_program_trace),
        )
    else:
        logger.warning("No gepa_state.bin found in %s", state_path)

    # -------------------------------------------------------------------
    # 4. Derive best_idx
    # -------------------------------------------------------------------
    if data.val_aggregate_scores:
        data.best_idx = data.val_aggregate_scores.index(
            max(data.val_aggregate_scores)
        )
        data.n_candidates = len(data.val_aggregate_scores)

    # -------------------------------------------------------------------
    # 5. Derive n_val_records from subscores
    # -------------------------------------------------------------------
    if data.val_subscores:
        first_subscore = data.val_subscores[0]
        if isinstance(first_subscore, dict):
            data.n_val_records = len(first_subscore)
        elif isinstance(first_subscore, list):
            data.n_val_records = len(first_subscore)

    return data


# -----------------------------------------------------------------------
# Holdout result loading
# -----------------------------------------------------------------------

class HoldoutRecord:
    """Container for a single holdout record's evaluation result."""

    def __init__(self):
        self.pmcid = ""
        self.category_gt = ""
        self.category_pred = ""
        self.overall_f1 = 0.0
        self.strict_f1 = 0.0
        self.loose_f1 = 0.0
        self.per_field_scores = {}


def load_holdout_results(results_path):
    """Load per-record holdout results from a results JSON file or directory.

    Supports two formats:
    1. Single JSON file with a top-level "records" array
       (produced by run_holdout.py as *_results.json).
    2. Directory of per-PMCID JSON files (one file per record).

    Field name mapping (run_holdout.py schema -> HoldoutRecord):
        ext_category   -> category_pred
        primary_f1     -> overall_f1 (also stored as strict_f1)
        loose_f1       -> loose_f1
        field_scores   -> per_field_scores

    Args:
        results_path: Path to either a *_results.json file or a directory
                      containing per-record JSON files.

    Returns:
        Dict mapping PMCID -> HoldoutRecord.
    """
    results_path = str(results_path)
    records = {}

    # ---------------------------------------------------------------
    # Detect format: single file vs directory
    # ---------------------------------------------------------------
    if os.path.isfile(results_path):
        records = _load_from_single_file(results_path)
    elif os.path.isdir(results_path):
        # Check for *_results.json inside the directory
        result_files = sorted([
            f for f in os.listdir(results_path)
            if f.endswith("_results.json")
        ])
        if result_files:
            # Use the first (or only) results file found
            filepath = os.path.join(results_path, result_files[0])
            records = _load_from_single_file(filepath)
        else:
            # Fall back to per-PMCID JSON files
            records = _load_from_directory(results_path)
    else:
        logger.warning(
            "Holdout results path not found: %s", results_path
        )

    return records


def _load_from_single_file(filepath):
    """Load holdout records from a single results JSON file.

    Expected schema:
    {
        "metadata": { ... },
        "records": [
            {
                "pmcid": "PMC...",
                "gt_category": "IWL",
                "ext_category": "IWL",
                "primary_f1": 0.85,
                "loose_f1": 0.90,
                "field_scores": { "serotype": {"tp":5,"fp":1,"fn":0,"f1":0.9}, ... },
                ...
            },
            ...
        ]
    }
    """
    records = {}

    with open(filepath, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    record_list = raw.get("records", [])

    for entry in record_list:
        rec = _parse_record(entry)
        records[rec.pmcid] = rec

    logger.info(
        "Loaded %d holdout records from %s", len(records), filepath
    )
    return records


def _load_from_directory(results_dir):
    """Load holdout records from a directory of per-PMCID JSON files."""
    records = {}

    json_files = sorted([
        f for f in os.listdir(results_dir) if f.endswith(".json")
    ])

    for filename in json_files:
        filepath = os.path.join(results_dir, filename)
        with open(filepath, "r", encoding="utf-8") as fh:
            entry = json.load(fh)

        rec = _parse_record(entry, fallback_pmcid=filename.replace(".json", ""))
        records[rec.pmcid] = rec

    logger.info(
        "Loaded %d holdout records from %s", len(records), results_dir
    )
    return records


def _parse_record(raw, fallback_pmcid=""):
    """Parse a single record dict into a HoldoutRecord.

    Handles field name variations across different output formats.

    Args:
        raw:             Dict from JSON.
        fallback_pmcid:  PMCID to use if not present in the dict.

    Returns:
        HoldoutRecord instance.
    """
    rec = HoldoutRecord()

    # PMCID
    rec.pmcid = raw.get("pmcid", fallback_pmcid)

    # Categories: gt_category is consistent; predicted uses ext_category
    rec.category_gt = raw.get(
        "gt_category", raw.get("category_gt", "")
    )
    rec.category_pred = raw.get(
        "ext_category",
        raw.get("predicted_category", raw.get("category_pred", "")),
    )

    # F1 scores: primary_f1 is the main metric in run_holdout.py
    rec.overall_f1 = raw.get(
        "primary_f1",
        raw.get("overall_f1", raw.get("strict_f1", 0.0)),
    )
    rec.strict_f1 = raw.get("primary_f1", raw.get("strict_f1", rec.overall_f1))
    rec.loose_f1 = raw.get("loose_f1", rec.strict_f1)

    # Per-field scores: field_scores in run_holdout.py
    rec.per_field_scores = raw.get(
        "field_scores", raw.get("per_field_scores", {})
    )

    return rec


# -----------------------------------------------------------------------
# Self-test
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python load_data.py <experiment_dir>")
        print("Example: python load_data.py C:\\proj\\pax-ai-working\\assay\\v1\\gepa\\assay_100pct_sonnet_evals5")
        sys.exit(1)

    gepa = load_gepa_data(sys.argv[1])
    print(gepa.summary())
