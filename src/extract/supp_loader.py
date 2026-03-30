"""
supp_loader.py
==============
Discover and load supplementary files and figure attachments for a PMCID.

Scans two directories per record:
- supplementary/PMC{id}/  -> downloaded supp files (xlsx, pdf, docx)
- attachments/PMC{id}/    -> article figures (png, jpg)

Returns an Attachments object combining all discovered files, ready for
DSPy multimodal extraction.

All paths are resolved via config.cfg unless overridden.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-016
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported file extensions (matched against what attachments library handles)
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    # Documents
    ".xlsx", ".xls",
    ".pdf",
    ".docx", ".doc",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    # Text / data
    ".csv", ".tsv", ".txt",
}


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_supp_files(
    pmcid: str,
    supp_dir: Path,
    attach_dir: Path,
) -> List[Path]:
    """Discover all supplementary and attachment files for a PMCID.

    Scans:
    - supp_dir/PMC{id}/ for downloaded supplementary files
    - attach_dir/PMC{id}/ for article figures

    Only files with supported extensions are returned.
    Files are sorted by type (documents first, then images) for
    consistent ordering.

    Args:
        pmcid: PubMed Central ID (e.g. 'PMC7738724').
        supp_dir: Root supplementary directory (e.g. cfg.SUPPLEMENTARY_PATH).
        attach_dir: Root attachments directory (e.g. cfg.ATTACHMENTS_PATH).

    Returns:
        Sorted list of Path objects for all discovered files.
        Empty list if no files found.
    """
    found_files = []

    # Scan supplementary directory
    supp_pmcid_dir = Path(supp_dir) / pmcid
    if supp_pmcid_dir.is_dir():
        for f in supp_pmcid_dir.iterdir():
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                found_files.append(f)

    # Scan attachments directory
    attach_pmcid_dir = Path(attach_dir) / pmcid
    if attach_pmcid_dir.is_dir():
        for f in attach_pmcid_dir.iterdir():
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                found_files.append(f)

    # Sort: documents first (xlsx, pdf, docx), then images, then others
    doc_extensions = {".xlsx", ".xls", ".pdf", ".docx", ".doc", ".csv", ".tsv", ".txt"}

    def sort_key(path: Path):
        is_doc = 0 if path.suffix.lower() in doc_extensions else 1
        return (is_doc, path.suffix.lower(), path.name.lower())

    found_files.sort(key=sort_key)

    if found_files:
        logger.info(
            "%s: discovered %d supp/attachment files", pmcid, len(found_files)
        )
        for f in found_files:
            logger.debug("  %s (%s)", f.name, f.suffix)
    else:
        logger.debug("%s: no supplementary or attachment files found", pmcid)

    return found_files


def build_supp_file_manifest(
    pmcid: str,
    supp_dir: Path,
    attach_dir: Path,
) -> Dict:
    """Build a manifest of supplementary files with metadata.

    Useful for reporting and audit trails.

    Args:
        pmcid: PubMed Central ID.
        supp_dir: Root supplementary directory.
        attach_dir: Root attachments directory.

    Returns:
        Dictionary with file counts and details:
        {
            "pmcid": str,
            "total_files": int,
            "supp_files": [{"name": str, "ext": str, "size_kb": float}],
            "attach_files": [{"name": str, "ext": str, "size_kb": float}],
        }
    """
    manifest = {
        "pmcid": pmcid,
        "total_files": 0,
        "supp_files": [],
        "attach_files": [],
    }

    supp_pmcid_dir = Path(supp_dir) / pmcid
    if supp_pmcid_dir.is_dir():
        for f in sorted(supp_pmcid_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                manifest["supp_files"].append({
                    "name": f.name,
                    "ext": f.suffix.lower(),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })

    attach_pmcid_dir = Path(attach_dir) / pmcid
    if attach_pmcid_dir.is_dir():
        for f in sorted(attach_pmcid_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                manifest["attach_files"].append({
                    "name": f.name,
                    "ext": f.suffix.lower(),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })

    manifest["total_files"] = (
        len(manifest["supp_files"]) + len(manifest["attach_files"])
    )

    return manifest


def load_attachments(
    file_paths: List[Path],
):
    """Create an Attachments object from a list of file paths.

    This is the bridge between file discovery and the attachments library.
    Import is deferred to avoid requiring the attachments package for
    article-only extraction runs.

    Args:
        file_paths: List of paths to supplementary/attachment files.

    Returns:
        Attachments object ready for DSPy multimodal input.

    Raises:
        ImportError: If the attachments library is not installed.
        ValueError: If file_paths is empty.
    """
    if not file_paths:
        raise ValueError("No files provided to load_attachments")

    try:
        from attachments.dspy import Attachments                               #changed: deferred import
    except ImportError:
        raise ImportError(
            "The 'attachments' library is required for supplementary extraction. "
            "Install with: pip install attachments[office]"
        )

    # Convert Path objects to strings (attachments expects str paths)
    str_paths = [str(p) for p in file_paths]

    attachment = Attachments(*str_paths)

    logger.info(
        "Loaded %d files into Attachments object (%d images)",
        len(str_paths),
        len(attachment.images) if hasattr(attachment, "images") else 0,
    )

    return attachment
