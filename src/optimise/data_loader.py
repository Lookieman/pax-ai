"""
data_loader.py
==============
Load GEPA split definitions and build DSPy Example objects for
training, validation, and holdout sets.

Resolves XML paths and GT directories using the same dual-directory
logic as run_baseline.py (main-first, golden-fallback).

Usage:
    from optimise.data_loader import load_splits, build_datasets

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-018
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import dspy

from extract.article_loader import (
    build_xml_mapping,
    load_article_text,
    load_ground_truth,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Split JSON loading
# ===========================================================================

def load_splits(splits_filepath: Path) -> Dict:
    """Load the GEPA splits JSON file (assay_gepa_splits_v4.json).

    Args:
        splits_filepath: Path to the JSON file.

    Returns:
        Parsed dictionary with holdout, validation, training, split_30 keys.

    Raises:
        FileNotFoundError: If the splits file does not exist.
    """
    splits_filepath = Path(splits_filepath)

    if not splits_filepath.exists():
        raise FileNotFoundError(f"Splits file not found: {splits_filepath}")

    with open(splits_filepath, "r", encoding="utf-8") as f:
        splits = json.load(f)

    logger.info(
        "Loaded splits v%s: holdout=%d, validation=%d, training=%d, split_30=%d",
        splits["metadata"].get("version", "?"),
        splits["holdout_test_set"]["total"],
        splits["validation_set"]["total"],
        splits["training_pool"]["total"],
        splits["split_30"]["total"],
    )

    return splits


# ===========================================================================
# Path resolution (mirrors run_baseline.py logic)
# ===========================================================================

def resolve_pmcid_paths(
    pmcid_list: List[str],
    gt_dir_main: Path,
    gt_dir_golden: Path,
    xml_map_main: Dict[str, Path],
    xml_map_golden: Dict[str, Path],
) -> Dict[str, Dict[str, Path]]:
    """Resolve GT directory and XML path for each PMCID.

    Checks main directories first, falls back to golden directories.

    Args:
        pmcid_list: List of PMCIDs to resolve.
        gt_dir_main: Primary GT directory.
        gt_dir_golden: Golden GT directory (fallback).
        xml_map_main: Main XML mapping {PMCID: Path}.
        xml_map_golden: Golden XML mapping {PMCID: Path}.

    Returns:
        Dictionary mapping PMCID to {"gt_dir": Path, "xml_path": Path}.
        PMCIDs that cannot be resolved are omitted with a warning.
    """
    resolved = {}
    missing_xml = []
    missing_gt = []

    for pmcid in pmcid_list:
        gt_dir = None
        xml_path = None

        # GT: main first, golden fallback
        if (gt_dir_main / f"{pmcid}.json").exists():
            gt_dir = gt_dir_main
        elif (gt_dir_golden / f"{pmcid}.json").exists():
            gt_dir = gt_dir_golden

        # XML: main first, golden fallback
        if pmcid in xml_map_main:
            xml_path = xml_map_main[pmcid]
        elif pmcid in xml_map_golden:
            xml_path = xml_map_golden[pmcid]

        if gt_dir is None:
            missing_gt.append(pmcid)
        if xml_path is None:
            missing_xml.append(pmcid)

        if gt_dir is not None and xml_path is not None:
            resolved[pmcid] = {"gt_dir": gt_dir, "xml_path": xml_path}

    if missing_gt:
        logger.warning("PMCIDs missing GT (%d): %s", len(missing_gt), missing_gt[:10])
    if missing_xml:
        logger.warning("PMCIDs missing XML (%d): %s", len(missing_xml), missing_xml[:10])

    return resolved


# ===========================================================================
# DSPy Example construction
# ===========================================================================

def _determine_gt_category(gt_data: Dict) -> str:
    """Determine the GT category from a ground truth dictionary.

    Uses the same logic as normalise._determine_category but operates
    on the raw GT dict (before flattening).

    Args:
        gt_data: Raw ground truth dictionary.

    Returns:
        Category string: IWL, IWOL, NIOAI, IWL+IWOL, or EMPTY.
    """
    iwl_raw = gt_data.get("isolates_with_linking", [])
    iwol_raw = gt_data.get("isolate_without_linking", [])
    nioai_raw = gt_data.get("no_isolates_only_assayinformation", {})

    has_iwl = False
    has_iwol = False
    has_nioai = False

    # IWL: list-of-dicts or non-empty dict
    if isinstance(iwl_raw, list) and iwl_raw:
        has_iwl = True
    elif isinstance(iwl_raw, dict) and iwl_raw:
        has_iwl = True

    # IWOL: non-empty list
    if isinstance(iwol_raw, list) and iwol_raw:
        has_iwol = True

    # NIOAI: non-empty dict with at least one truthy value
    if isinstance(nioai_raw, dict) and any(nioai_raw.values()):
        has_nioai = True

    if has_iwl and has_iwol:
        return "IWL+IWOL"
    if has_iwl:
        return "IWL"
    if has_iwol:
        return "IWOL"
    if has_nioai:
        return "NIOAI"
    return "EMPTY"


def build_dspy_examples(
    pmcid_list: List[str],
    resolved_paths: Dict[str, Dict[str, Path]],
    max_chars: int = 100000,
) -> List[dspy.Example]:
    """Convert a list of PMCIDs into DSPy Example objects.

    Each Example contains:
        - article_text (InputField): plain text from XML
        - pmcid: PubMed Central ID (metadata, not input)
        - gt_json: serialised GT dict (metadata, not input)
        - gt_category: GT category string (metadata, not input)

    Args:
        pmcid_list: PMCIDs to load.
        resolved_paths: Output of resolve_pmcid_paths().
        max_chars: Maximum article text length.

    Returns:
        List of DSPy Examples with article_text as the sole input field.
    """
    examples = []
    skipped = []

    for pmcid in pmcid_list:
        if pmcid not in resolved_paths:
            skipped.append(pmcid)
            continue

        paths = resolved_paths[pmcid]
        gt_dir = paths["gt_dir"]
        xml_path = paths["xml_path"]

        # Load article text
        article_text = load_article_text(xml_path, max_chars=max_chars)
        if not article_text:
            logger.warning("Empty article text for %s, skipping", pmcid)
            skipped.append(pmcid)
            continue

        # Load ground truth
        gt_data = load_ground_truth(pmcid, gt_dir)
        if gt_data is None:
            logger.warning("GT is None for %s, skipping", pmcid)
            skipped.append(pmcid)
            continue

        # Determine category
        gt_category = _determine_gt_category(gt_data)

        # Serialise GT for storage in Example
        gt_json_str = json.dumps(gt_data, ensure_ascii=False)

        # Build Example with article_text as the sole input
        example = dspy.Example(
            pmcid=pmcid,
            article_text=article_text,
            gt_json=gt_json_str,
            gt_category=gt_category,
        ).with_inputs("article_text")

        examples.append(example)

    if skipped:
        logger.warning("Skipped %d PMCIDs: %s", len(skipped), skipped[:10])

    logger.info("Built %d DSPy Examples from %d PMCIDs", len(examples), len(pmcid_list))
    return examples


# ===========================================================================
# High-level dataset builders
# ===========================================================================

def build_datasets(
    splits: Dict,
    cfg,
    split_pct: int = 100,
    max_chars: int = 100000,
) -> Tuple[List[dspy.Example], List[dspy.Example], List[dspy.Example]]:
    """Build training, validation, and holdout DSPy Example sets.

    Args:
        splits: Parsed splits dictionary from load_splits().
        cfg: Config object with path attributes.
        split_pct: Training split percentage (100 or 30).
        max_chars: Maximum article text length.

    Returns:
        Tuple of (trainset, valset, holdout_set).
    """
    # Resolve directories
    gt_dir_main = Path(cfg.GROUND_TRUTH_PATH)
    gt_dir_golden = Path(cfg.GOLDEN_GT_PATH)
    xml_dir_main = Path(cfg.XML_PATH)
    xml_dir_golden = Path(cfg.XML_PATH) / "golden"

    # Build XML mappings
    xml_map_main = build_xml_mapping(xml_dir_main)
    xml_map_golden = build_xml_mapping(xml_dir_golden)

    # Collect all PMCIDs across all splits
    all_pmcids = set()

    # Training PMCIDs
    if split_pct == 100:
        train_pmcids = splits["training_pool"]["pmcids"]
    elif split_pct == 30:
        train_pmcids = splits["split_30"]["pmcids"]
    else:
        raise ValueError(f"Unsupported split_pct: {split_pct}. Use 100 or 30.")

    val_pmcids = splits["validation_set"]["pmcids"]
    holdout_pmcids = (
        splits["holdout_test_set"]["golden"]
        + splits["holdout_test_set"]["supplement"]
    )

    all_pmcids.update(train_pmcids)
    all_pmcids.update(val_pmcids)
    all_pmcids.update(holdout_pmcids)

    # Resolve paths for all PMCIDs at once
    resolved = resolve_pmcid_paths(
        list(all_pmcids),
        gt_dir_main,
        gt_dir_golden,
        xml_map_main,
        xml_map_golden,
    )

    logger.info("Resolved %d / %d PMCIDs", len(resolved), len(all_pmcids))

    # Build Example sets
    trainset = build_dspy_examples(train_pmcids, resolved, max_chars)
    valset = build_dspy_examples(val_pmcids, resolved, max_chars)
    holdout_set = build_dspy_examples(holdout_pmcids, resolved, max_chars)

    logger.info(
        "Datasets built: train=%d (%d%%), val=%d, holdout=%d",
        len(trainset), split_pct, len(valset), len(holdout_set),
    )

    return trainset, valset, holdout_set
