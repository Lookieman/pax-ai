"""
article_loader.py
=================
Load XML articles, ground truth JSONs, and PMCID lists from disk.

All paths are resolved via config.cfg unless overridden by explicit arguments.

Usage:
    from extract.article_loader import (
        build_xml_mapping, load_article_text, load_ground_truth, load_pmcid_list
    )

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XML mapping
# ---------------------------------------------------------------------------

def build_xml_mapping(xml_dir: Path) -> Dict[str, Path]:
    """Scan xml_dir for *.xml files, return {PMCID: filepath}.

    Filenames are expected as PMC{id}_{date}.xml or PMC{id}.xml.
    The PMCID is extracted by splitting on '_' and taking the first part.

    Args:
        xml_dir: Directory containing XML article files.

    Returns:
        Dictionary mapping PMCID string to its full file path.
    """
    mapping = {}
    xml_dir = Path(xml_dir)

    if not xml_dir.exists():
        logger.warning("XML directory does not exist: %s", xml_dir)
        return mapping

    for xml_file in xml_dir.glob("*.xml"):
        pmcid = xml_file.stem.split("_")[0]
        mapping[pmcid] = xml_file

    logger.info("XML mapping built: %d files from %s", len(mapping), xml_dir)
    return mapping


# ---------------------------------------------------------------------------
# Article text extraction
# ---------------------------------------------------------------------------

def load_article_text(xml_path: Path, max_chars: int = 100000) -> str:
    """Read XML file, strip tags, return plain text.

    If the stripped text exceeds max_chars, the middle section is truncated
    (keeping first 70% and last 30%) with a truncation marker.

    Args:
        xml_path: Path to the XML article file.
        max_chars: Maximum character length before truncation.

    Returns:
        Plain text string extracted from the XML.
    """
    xml_path = Path(xml_path)

    with open(xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    # Strip all XML tags
    text = re.sub(r"<[^>]+>", " ", xml_content)
    text = re.sub(r"\s+", " ", text).strip()

    total_length = len(text)

    if total_length > max_chars:
        keep_start = int(max_chars * 0.7)
        keep_end = int(max_chars * 0.3)
        text = (
            text[:keep_start]
            + "\n[...TRUNCATED...]\n"
            + text[total_length - keep_end:]
        )
        logger.info(
            "Truncated article text: %d -> %d chars",
            total_length, len(text)
        )

    return text


# ---------------------------------------------------------------------------
# Ground truth loading
# ---------------------------------------------------------------------------

def load_ground_truth(pmcid: str, gt_dir: Path) -> Optional[Dict]:
    """Load GT JSON for a PMCID from the specified directory.

    Args:
        pmcid: The PubMed Central ID (e.g. 'PMC1234567').
        gt_dir: Directory containing ground truth JSON files.

    Returns:
        Parsed JSON as a dictionary, or None if file does not exist.
    """
    gt_path = Path(gt_dir) / f"{pmcid}.json"

    if not gt_path.exists():
        logger.debug("GT file not found: %s", gt_path)
        return None

    with open(gt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()                                                    #changed

    # Repair trailing commas (common in hand-edited GT files)                  #changed
    raw_text = re.sub(r",\s*([}\]])", r"\1", raw_text)                        #changed

    try:                                                                       #changed
        return json.loads(raw_text)                                            #changed
    except json.JSONDecodeError as e:                                          #changed
        logger.error("Failed to parse GT JSON for %s: %s", pmcid, e)          #changed
        return None                                                            #changed


# ---------------------------------------------------------------------------
# PMCID list loading
# ---------------------------------------------------------------------------

def load_pmcid_list(filepath: Path) -> List[str]:
    """Load a PMCID list from a text file (one per line).

    Skips blank lines, header lines (e.g. 'PMCID'), and comment lines
    (starting with '#').

    Args:
        filepath: Path to the text file.

    Returns:
        Sorted list of PMCID strings.
    """
    filepath = Path(filepath)
    skip_headers = {"pmcid", "pmid", "id", ""}
    pmcids = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#"):                                        #changed: skip comment lines
                continue
            if stripped.lower() in skip_headers:
                continue
            if stripped:
                pmcids.append(stripped)

    pmcids = sorted(set(pmcids))
    logger.info("Loaded %d PMCIDs from %s", len(pmcids), filepath)
    return pmcids
