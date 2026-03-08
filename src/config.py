"""
config.py
=========
Centralised configuration for the AI6129 Pathogen Tracking project.

Loads environment variables from a .env file (if present) and defines
all directory paths, API keys, and shared constants used across modules.

Usage:
    from config import cfg

    # Access paths
    xml_folder = cfg.XML_PATH
    gt_folder  = cfg.GROUND_TRUTH_PATH

    # Access API keys
    api_key = cfg.NCBI_API_KEY

    # Ensure directories exist before writing
    cfg.ensure_directories()

All paths are derived from a single DRIVE_BASE value.  Override order:
  1. Explicit argument to Config.__init__(base_dir=...)
  2. PUBMED_BASE_DIR environment variable
  3. Hard-coded default (Google Drive path)

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
"""

import os
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Attempt to load .env — silent if python-dotenv is not installed
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ===========================================================================
# Configuration class
# ===========================================================================

class Config:
    """Centralised, read-once configuration for the entire project."""

    # Hard-coded fallback (Google Drive on Windows)
    _DEFAULT_BASE = r"G:\My Drive\AI6129"

    def __init__(self, base_dir: str = None):
        # -----------------------------------------------------------------
        # 1. Resolve DRIVE_BASE
        # -----------------------------------------------------------------
        self.DRIVE_BASE = base_dir or os.environ.get(
            "PUBMED_BASE_DIR", self._DEFAULT_BASE
        )

        # -----------------------------------------------------------------
        # 2. Directory paths
        # -----------------------------------------------------------------

        # Data acquisition
        self.XML_PATH = os.path.join(self.DRIVE_BASE, "xml")
        self.SUPPLEMENTARY_PATH = os.path.join(self.DRIVE_BASE, "supplementary")
        self.ATTACHMENTS_PATH = os.path.join(self.DRIVE_BASE, "attachments")

        # Ground truth
        self.GROUND_TRUTH_PATH = os.path.join(self.DRIVE_BASE, "ground_truth")
        self.GOLDEN_GT_PATH = os.path.join(self.GROUND_TRUTH_PATH, "golden")
        self.GOLDEN_GT_INPUT_PATH = os.path.join(
            self.DRIVE_BASE, "design", "golden"
        )

        # Assay extraction outputs
        self.ASSAY_BASE_PATH = os.path.join(self.DRIVE_BASE, "assay")
        self.ASSAY_GEPA_OUTPUT = os.path.join(self.ASSAY_BASE_PATH, "gepa")
        self.ASSAY_COT_OUTPUT = os.path.join(self.ASSAY_BASE_PATH, "cot")

        # Accession extraction outputs
        self.ACCESSION_OUTPUT_PATH = os.path.join(
            self.DRIVE_BASE, "accession", "output"
        )

        # Validation splits
        self.VALIDATION_SPLITS_DIR = os.path.join(
            self.ASSAY_BASE_PATH, "validation_splits"
        )
        self.VALIDATION_SPLITS_FILE = os.path.join(
            self.VALIDATION_SPLITS_DIR,
            "assay_tadp_gepa_optimised_splits.json",
        )

        # Logging and tracking
        self.LOG_PATH = os.path.join(self.DRIVE_BASE, "logs")
        self.TRACKING_FILE = os.path.join(
            self.DRIVE_BASE, "download_tracker.csv"
        )
        self.MISSING_PMCID_LOG = os.path.join(
            self.DRIVE_BASE, "missing_pmcids"
        )

        # OA file list cache (used by PubMed downloader)
        self.OA_FILE_LIST_LOCAL = os.path.join(
            self.SUPPLEMENTARY_PATH, "oa_file_list.csv"
        )

        # Accession format rules (reference document for DSPy signatures)
        self.ACCESSION_FORMAT_RULES = os.path.join(
            self.DRIVE_BASE, "accession", "NCBI_Accession_Format_Rules.md"
        )

        # -----------------------------------------------------------------
        # 3. API keys (from environment)
        # -----------------------------------------------------------------
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        self.NCBI_API_KEY = os.environ.get("NCBI_API_KEY",
                                           os.environ.get("ENTREZ_API_KEY", ""))
        self.NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
        self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY",
                                             os.environ.get("GOOGLE_API_KEY", ""))

        # AWS Bedrock
        self.AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME",
                                              "ap-southeast-1")

        # -----------------------------------------------------------------
        # 4. NCBI / E-utilities constants
        # -----------------------------------------------------------------
        self.EUTILS_BASE_URL = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        )
        self.OA_FILE_LIST_URL = (
            "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv"
        )
        self.FTP_BASE_URL = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/"
        self.PMC_OA_SERVICE = (
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
        )

        # Rate limiting
        self.RATE_LIMIT_DELAY = 0.1 if self.NCBI_API_KEY else 0.34
        self.FTP_RATE_LIMIT_DELAY = 1.5
        self.PMC_RATE_LIMIT_DELAY = 1.0
        self.MAX_RETRIES = 3
        self.BATCH_SIZE = 10

        # File size limits (MB)
        self.MAX_XML_SIZE_MB = 10
        self.COMPRESS_THRESHOLD_MB = 1

        # -----------------------------------------------------------------
        # 5. DSPy model strings
        # -----------------------------------------------------------------
        self.DSPY_MODEL_STRINGS = {
            "claude-haiku-4.5": "anthropic/claude-haiku-4-5-20251001",
            "claude-sonnet-4": (
                "bedrock/apac.anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            "amazon-nova-pro": "bedrock/apac.amazon.nova-pro-v1:0",
        }

        self.MODEL_PRICING = {
            "claude-haiku-4.5": {"input": 1.00, "output": 5.00},
            "claude-sonnet-4": {"input": 3.00, "output": 15.00},
            "amazon-nova-pro": {"input": 0.80, "output": 3.20},
        }

        # -----------------------------------------------------------------
        # 6. Pathogen search configurations
        # -----------------------------------------------------------------
        self.PATHOGENS = {
            "hepatitis_a": {
                "name": "Hepatitis A",
                "mesh": "Hepatitis A",
                "term": "Hepatitis A",
            },
            "hepatitis_e": {
                "name": "Hepatitis E",
                "mesh": "Hepatitis E",
                "term": "Hepatitis E",
            },
        }

        # -----------------------------------------------------------------
        # 7. Golden GT converter constants
        # -----------------------------------------------------------------
        self.SALMONELLA_FILE = (
            "salmonella_golden-gt_manual-labelled.xlsx"
        )
        self.ECOLI_ISOLATES_SUFFIX = "Isolates_with_linking.xlsx"
        self.ECOLI_OTHERS_SUFFIX = "others.xlsx"

        # -----------------------------------------------------------------
        # 8. Logging defaults
        # -----------------------------------------------------------------
        self.LOG_LEVEL = logging.INFO
        self.LOG_FORMAT = (
            "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"
        )

    # -----------------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------------

    def ensure_directories(self):
        """Create all project directories if they do not already exist."""
        dirs_to_create = [
            self.XML_PATH,
            self.SUPPLEMENTARY_PATH,
            self.ATTACHMENTS_PATH,
            self.GROUND_TRUTH_PATH,
            self.GOLDEN_GT_PATH,
            self.ASSAY_GEPA_OUTPUT,
            self.ASSAY_COT_OUTPUT,
            self.ACCESSION_OUTPUT_PATH,
            self.VALIDATION_SPLITS_DIR,
            self.LOG_PATH,
            self.MISSING_PMCID_LOG,
        ]
        for d in dirs_to_create:
            os.makedirs(d, exist_ok=True)

    def summary(self) -> str:
        """Return a human-readable summary of the active configuration."""
        ncbi_status = "SET" if self.NCBI_API_KEY else "NOT SET"
        anthropic_status = "SET" if self.ANTHROPIC_API_KEY else "NOT SET"
        aws_status = "SET" if self.AWS_ACCESS_KEY_ID else "NOT SET"

        return (
            f"{'=' * 60}\n"
            f"AI6129 Configuration Summary\n"
            f"{'=' * 60}\n"
            f"  Base directory   : {self.DRIVE_BASE}\n"
            f"  XML articles     : {self.XML_PATH}\n"
            f"  Ground truth     : {self.GROUND_TRUTH_PATH}\n"
            f"  Golden GT        : {self.GOLDEN_GT_PATH}\n"
            f"  Supplementary    : {self.SUPPLEMENTARY_PATH}\n"
            f"  Attachments      : {self.ATTACHMENTS_PATH}\n"
            f"  Assay GEPA out   : {self.ASSAY_GEPA_OUTPUT}\n"
            f"  Assay CoT out    : {self.ASSAY_COT_OUTPUT}\n"
            f"  Logs             : {self.LOG_PATH}\n"
            f"  Validation splits: {self.VALIDATION_SPLITS_FILE}\n"
            f"{'=' * 60}\n"
            f"  NCBI API key     : {ncbi_status}\n"
            f"  Anthropic API key: {anthropic_status}\n"
            f"  AWS credentials  : {aws_status}\n"
            f"  AWS region       : {self.AWS_REGION_NAME}\n"
            f"{'=' * 60}"
        )


# ===========================================================================
# Module-level singleton
# ===========================================================================
# Import and use as:  from config import cfg
cfg = Config()


# ===========================================================================
# Quick self-test
# ===========================================================================
if __name__ == "__main__":
    print(cfg.summary())
