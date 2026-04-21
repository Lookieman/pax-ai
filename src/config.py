"""
config.py
=========
Centralised configuration for the AI6129 Pathogen Tracking project.
** AICORE BRANCH ** — paths adjusted for work laptop with SAP AI Core.

Changes from main branch:
- DRIVE_BASE defaults to C:\\proj\\pax-ai-working (data on work laptop)
- CODE_BASE defaults to C:\\proj\\pax-ai\\src (code on work laptop)
- Added AI Core credential loading (service key, deployment endpoints)
- Added resolve_model() helper for AI Core endpoint resolution
- Added load_service_key_if_exists() for startup credential loading

Usage:
    from config import cfg

    # Access paths
    xml_folder = cfg.XML_PATH
    gt_folder  = cfg.GROUND_TRUTH_PATH

    # AI Core model resolution
    endpoint_url, model_name = cfg.resolve_model("claude-4.5-sonnet")

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Branch: aicore
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

    # Hard-coded fallback (work laptop)                                        
    _DEFAULT_BASE = r"C:\proj\pax-ai-working"                                  
    _CODE_BASE = r"C:\proj\pax-ai\src"                                         

    def __init__(self, base_dir: str = None):
        # -----------------------------------------------------------------
        # 1. Resolve DRIVE_BASE
        # -----------------------------------------------------------------
        self.DRIVE_BASE = base_dir or os.environ.get(
            "PUBMED_BASE_DIR", self._DEFAULT_BASE
        )

        # -----------------------------------------------------------------
        # 2. Directory paths (adjusted for work laptop layout)             
        # -----------------------------------------------------------------

        # Data acquisition
        self.XML_PATH = os.path.join(self.DRIVE_BASE, "xml")
        self.SUPPLEMENTARY_PATH = os.path.join(self.DRIVE_BASE, "supplementary")
        self.ATTACHMENTS_PATH = os.path.join(self.DRIVE_BASE, "attachments")

        # Ground truth                                                         
        self.GROUND_TRUTH_PATH = os.path.join(self.DRIVE_BASE, "gt")           
        self.GOLDEN_GT_PATH = os.path.join(self.GROUND_TRUTH_PATH, "golden")   # nested under gt/
        self.GOLDEN_GT_INPUT_PATH = os.path.join(
            self.DRIVE_BASE, "design", "golden"
        )
        self.SUPP_GT_PATH = os.path.join(
            self.GROUND_TRUTH_PATH, "supp"
        )
        self.SUPP_GOLDEN_GT_PATH = os.path.join(
            self.GOLDEN_GT_PATH, "supp"
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
        self.GEPA_SPLITS_FILE = os.path.join(
            self.VALIDATION_SPLITS_DIR,
            "assay_gepa_splits_v5.json",
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
        # 3. SAP AI Core configuration                                     
        # -----------------------------------------------------------------
        self.AICORE_DIR = os.path.join(                                        
            self._CODE_BASE, "aicore"                                          
        )                                                                      
        self.DEPLOYMENT_ENDPOINT_FILE = os.path.join(                          
            self._CODE_BASE, "deployment_endpoints.json"                       
        )                                                                      
        self.SERVICE_KEY_FILE = os.environ.get(                                
            "AICORE_SERVICE_KEY",                                              
            ""                                                                 
        )                                                                      

        # -----------------------------------------------------------------
        # 4. API keys (from environment) — retained for compatibility
        # -----------------------------------------------------------------
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        self.NCBI_API_KEY = os.environ.get("NCBI_API_KEY",
                                           os.environ.get("ENTREZ_API_KEY", ""))
        self.NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
        self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY",
                                             os.environ.get("GOOGLE_API_KEY", ""))

        # AWS Bedrock (retained for compatibility)
        self.AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME",
                                              "ap-southeast-1")

        # -----------------------------------------------------------------
        # 5. NCBI / E-utilities constants
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
        # 6. DSPy model strings (AI Core deployment names)                 
        # -----------------------------------------------------------------
        self.DSPY_MODEL_STRINGS = {                                            
            "claude-4.5-haiku": "anthropic--claude-4.5-haiku",                 
            "claude-4.5-sonnet": "anthropic--claude-4.5-sonnet",
            "claude-4.6-sonnet": "anthropic--claude-4.6-sonnet",               
            "claude-4.5-opus": "anthropic--claude-4.5-opus",                   
            "claude-4.6-opus": "anthropic--claude-4.6-opus",
        }                                                                      

        self.MODEL_PRICING = {
            "claude-4.5-haiku":  {"input": 1.00, "output": 5.00},             
            "claude-4.5-sonnet": {"input": 3.00, "output": 15.00},
            "claude-4.5-opus":   {"input": 15.00, "output": 75.00},
            "claude-4.6-sonnet": {"input": 3.00, "output": 15.00},            
            "claude-4.6-opus":   {"input": 5.00, "output": 25.00},            
        }

        # -----------------------------------------------------------------
        # 7. Pathogen search configurations
        # -----------------------------------------------------------------
        self.PATHOGENS = {
            # "hepatitis_a": {
            #     "name": "Hepatitis A",
            #     "mesh": "Hepatitis A",
            #     "term": "Hepatitis A",
            # },
            # "hepatitis_e": {
            #     "name": "Hepatitis E",
            #     "mesh": "Hepatitis E",
            #     "term": "Hepatitis E",
            # },
            "Listeria": {
                "name": "Listeria monocytogenes",
                "mesh": "Listeria monocytogenes",
                "term": "Listeria monocytogenes",
            },
        }

        # -----------------------------------------------------------------
        # 8. Golden GT converter constants
        # -----------------------------------------------------------------
        self.SALMONELLA_FILE = (
            "salmonella_working_document.xlsx"
        )
        self.ECOLI_ISOLATES_SUFFIX = "Isolates_with_linking.xlsx"
        self.ECOLI_OTHERS_SUFFIX = "others.xlsx"

        # -----------------------------------------------------------------
        # 9. Logging defaults
        # -----------------------------------------------------------------
        self.LOG_LEVEL = logging.INFO
        self.LOG_FORMAT = (
            "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"
        )

    # -----------------------------------------------------------------------
    # AI Core helpers                                                      
    # -----------------------------------------------------------------------

    def resolve_model(self, model_key: str) -> str:                             #changed_020426
        """Resolve a model key to the AI Core deployment name.                 #changed_020426
                                                                               #changed_020426
        Args:                                                                  #changed_020426
            model_key: Key from DSPY_MODEL_STRINGS or direct AI Core name.     #changed_020426
                                                                               #changed_020426
        Returns:                                                               #changed_020426
            AI Core model name (e.g. 'anthropic--claude-4.5-sonnet').          #changed_020426
        """                                                                    #changed_020426
        return self.DSPY_MODEL_STRINGS.get(model_key, model_key)               #changed_020426

    def load_service_key_if_exists(self):                                      #changed
        """Load AI Core credentials if path is configured.                     #changed_020426
                                                                               #changed_020426
        Checks SERVICE_KEY_FILE (from env or config) and sets up the           #changed_020426
        gen_ai_hub SDK credentials. Silent no-op if path is empty or           #changed_020426
        file does not exist.                                                   #changed_020426
        """                                                                    
        if not self.SERVICE_KEY_FILE:                                           
            return                                                             
        from pathlib import Path                                               
        if not Path(self.SERVICE_KEY_FILE).exists():                           
            logging.warning(                                                   
                "Service key file not found: %s", self.SERVICE_KEY_FILE        
            )                                                                  
            return                                                             
        from aicore.aicore_lm import set_service_key                           #changed_020426
        set_service_key(self.SERVICE_KEY_FILE)                                 #changed_020426
        logging.info("AI Core credentials loaded from %s",                     
                     self.SERVICE_KEY_FILE)                                     

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
            self.SUPP_GT_PATH,
            self.SUPP_GOLDEN_GT_PATH,
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
        aicore_status = "SET" if self.SERVICE_KEY_FILE else "NOT SET"           

        return (
            f"{'=' * 60}\n"
            f"AI6129 Configuration Summary (AICORE BRANCH)\n"
            f"{'=' * 60}\n"
            f"  Data directory   : {self.DRIVE_BASE}\n"                        
            f"  Code directory   : {self._CODE_BASE}\n"                        
            f"  XML articles     : {self.XML_PATH}\n"
            f"  Ground truth     : {self.GROUND_TRUTH_PATH}\n"
            f"  Golden GT        : {self.GOLDEN_GT_PATH}\n"
            f"  Supp GT          : {self.SUPP_GT_PATH}\n"
            f"  Supp Golden GT   : {self.SUPP_GOLDEN_GT_PATH}\n"
            f"  Supplementary    : {self.SUPPLEMENTARY_PATH}\n"
            f"  Attachments      : {self.ATTACHMENTS_PATH}\n"
            f"  Assay GEPA out   : {self.ASSAY_GEPA_OUTPUT}\n"
            f"  Assay CoT out    : {self.ASSAY_COT_OUTPUT}\n"
            f"  Logs             : {self.LOG_PATH}\n"
            f"  GEPA splits      : {self.GEPA_SPLITS_FILE}\n"                 
            f"  Deployment endpts: {self.DEPLOYMENT_ENDPOINT_FILE}\n"          
            f"{'=' * 60}\n"
            f"  NCBI API key     : {ncbi_status}\n"
            f"  Anthropic API key: {anthropic_status}\n"
            f"  AI Core svc key  : {aicore_status}\n"                          
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
