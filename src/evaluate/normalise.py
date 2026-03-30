"""
normalise.py
============
Field and value normalisation for v4 evaluation framework.

This module implements the UPDATED evaluation framework documented in
DD-2026-012 and DD-2026-015. Changes from v3:
- Case-insensitive field name matching
- Field-specific value normalisers (serotype, MLST, AST, AMR)
- Category-aware GT flattening (preserves IWL/IWOL/NIOAI structure)

The v3 diagnostic notebook used a deliberately simple normaliser to keep
the diagnostic comparator frozen. This module replaces it for all v4+
evaluation runs.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ===========================================================================
# Field normalisation
# ===========================================================================

FIELD_ALIASES = {
    # v3 aliases (retained)
    "serovar": "serotype",
    "ast": "ast_data",
    "amr_genes": "amr",
    "plasmids": "plasmid",
    "virulence": "virulence_genes",
    # v4 additions: common LLM casing variations                               #changed
    "serogroup": "serotype",
    "antimicrobial_resistance": "amr",
    "resistance_genes": "amr",
    "virulence_factors": "virulence_genes",
    "phagetype": "phage_type",
    "phage": "phage_type",
    "sequence_type": "mlst",
    "st": "mlst",
}

VALID_ASSAY_FIELDS = {
    "serotype", "mlst", "cgmlst", "ast_data", "amr", "plasmid",
    "virulence_genes", "pfge", "spi", "toxin", "phage_type", "snp",
}


def normalise_field(field_name: str) -> str:
    """Normalise an assay field name to its canonical lowercase form.

    Applies case-insensitive matching and alias resolution.

    Args:
        field_name: Raw field name from GT or extraction.

    Returns:
        Canonical lowercase field name.
    """
    lowered = field_name.lower().strip()                                       #changed: always lowercase first
    resolved = FIELD_ALIASES.get(lowered, lowered)
    return resolved


# ===========================================================================
# Value normalisation - field-specific dispatchers
# ===========================================================================

def normalise_value(value: Any, field_name: str = "") -> str:
    """Normalise a value using field-specific logic.

    Routes to the appropriate normaliser based on the (already normalised)
    field name.  Falls back to generic normalisation for unknown fields.

    Args:
        value: Raw value from GT or extraction (str, list, dict, etc.).
        field_name: Normalised field name (e.g. 'serotype', 'ast_data').

    Returns:
        Normalised string representation for comparison.
    """
    if value is None:
        return ""

    if isinstance(value, list) and not value:
        return ""

    if isinstance(value, dict) and not value:
        return ""

    if field_name == "serotype":
        return _normalise_serotype(value)
    if field_name == "mlst":
        return _normalise_mlst(value)
    if field_name == "ast_data":
        return _normalise_ast(value)
    if field_name == "amr":
        return _normalise_amr(value)

    return _normalise_generic(value)


# ---------------------------------------------------------------------------
# Serotype normaliser
# ---------------------------------------------------------------------------

# Prefixes to strip (order matters: longest first)
_SEROTYPE_PREFIXES = [
    r"salmonella\s+enterica\s+(?:subsp\.\s+enterica\s+)?(?:serovar|ser\.?)\s+",
    r"salmonella\s+(?:serovar|ser\.?)\s+",
    r"salmonella\s+(?:enterica\s+)?",
    r"s\.\s+",
]
_SEROTYPE_PREFIX_RE = re.compile(
    r"^(?:" + "|".join(_SEROTYPE_PREFIXES) + r")",
    re.IGNORECASE,
)


def _normalise_serotype(value: Any) -> str:
    """Strip Salmonella prefixes and normalise serotype values.              #changed: new function

    Examples:
        'Salmonella Typhimurium'   -> 'typhimurium'
        'S. Enteritidis'           -> 'enteritidis'
        'ser. Kentucky'            -> 'kentucky'
        ['Typhimurium', 'Kentucky'] -> 'kentucky|typhimurium'
    """
    if isinstance(value, list):
        parts = sorted([_normalise_serotype(v) for v in value if v])
        return "|".join(p for p in parts if p)

    s = str(value).strip()
    s = _SEROTYPE_PREFIX_RE.sub("", s)
    s = s.strip().lower()
    return s


# ---------------------------------------------------------------------------
# MLST normaliser
# ---------------------------------------------------------------------------

_MLST_RE = re.compile(r"^(?:st[- ]?)(\d+)$", re.IGNORECASE)


def _normalise_mlst(value: Any) -> str:
    """Normalise MLST values to 'st<number>' format.                        #changed: new function

    Examples:
        'ST34'    -> 'st34'
        'ST-34'   -> 'st34'
        '34'      -> 'st34'
        ['ST34']  -> 'st34'
    """
    if isinstance(value, list):
        parts = sorted([_normalise_mlst(v) for v in value if v])
        return "|".join(p for p in parts if p)

    s = str(value).strip()
    match = _MLST_RE.match(s)
    if match:
        return f"st{match.group(1)}"

    # If it is just a number, add st prefix
    if s.isdigit():
        return f"st{s}"

    # Fallback: lowercase, strip hyphens
    return s.lower().replace("-", "").replace(" ", "")


# ---------------------------------------------------------------------------
# AST normaliser
# ---------------------------------------------------------------------------

_AST_INTERP_ALIASES = {
    "resistant": "r",
    "susceptible": "s",
    "sensitive": "s",
    "intermediate": "i",
    "not determined": "nd",
    "nd": "nd",
}


def _find_key_ci(d: Dict, target: str) -> Optional[str]:                      #changed: new helper
    """Find a key in a dict using case-insensitive matching.                    #changed

    Args:                                                                      #changed
        d: Dictionary to search.                                               #changed
        target: Lowercase key name to find.                                    #changed

    Returns:                                                                   #changed
        The actual key string if found, else None.                             #changed
    """                                                                        #changed
    for key in d:                                                              #changed
        if str(key).lower().strip() == target:                                 #changed
            return key                                                         #changed
    return None                                                                #changed


def _extract_antibiotics_list(abx_list: Any, pairs: List) -> None:            #changed: new helper
    """Extract drug:interpretation pairs from a GT Antibiotics list.            #changed

    Handles the GT envelope format where each antibiotic is:                   #changed
        {"Name": "ampicillin", "MIC": ">=32", "Interpretation": "R"}           #changed

    Appends normalised 'drug:interp' strings to the pairs list in place.       #changed

    Args:                                                                      #changed
        abx_list: The value of the 'Antibiotics' key (expected: list of dicts).#changed
        pairs: List to append normalised pairs to.                             #changed
    """                                                                        #changed
    if not isinstance(abx_list, list):                                         #changed
        return                                                                 #changed
    for abx in abx_list:                                                       #changed
        if not isinstance(abx, dict):                                          #changed
            continue                                                           #changed
        # Case-insensitive key lookup for Name and Interpretation              #changed
        name_key = _find_key_ci(abx, "name")                                  #changed
        interp_key = _find_key_ci(abx, "interpretation")                      #changed
        drug = str(abx.get(name_key, "")).strip().lower() if name_key else ""  #changed
        raw_interp = str(abx.get(interp_key, "")).strip().lower() if interp_key else ""  #changed
        interp = _AST_INTERP_ALIASES.get(raw_interp, raw_interp)              #changed
        if drug:                                                               #changed
            pairs.append(f"{drug}:{interp}")                                   #changed


def _normalise_ast(value: Any) -> str:
    """Flatten AST structures to sorted 'drug:interpretation' pairs.        #changed

    Handles multiple GT/extraction formats:
    - GT envelope: [{"Serotype": "...", "Antibiotics": [{"Name": "...",      #changed
                     "MIC": "...", "Interpretation": "R"}, ...]}]            #changed
    - Dict: {"Ampicillin": "R", "Tetracycline": "S"}
    - Dict with nested MIC: {"Ampicillin": {"mic": ">=32", "interpretation": "R"}}
    - String: "AMP-R, TET-S" (fallback)
    - List: ["AMP-R", "TET-S"]

    Returns:
        Pipe-separated sorted string, e.g. 'ampicillin:r|tetracycline:s'.
    """
    pairs = []

    if isinstance(value, dict):
        # Check if this is a GT envelope dict with 'Antibiotics' key         #changed
        abx_key = _find_key_ci(value, "antibiotics")                         #changed
        if abx_key is not None:                                              #changed
            _extract_antibiotics_list(value[abx_key], pairs)                 #changed
        else:                                                                #changed
            for drug, result in value.items():
                drug_norm = drug.strip().lower()
                interp = ""

                if isinstance(result, dict):
                    # Nested structure: extract interpretation
                    raw_interp = result.get("interpretation",
                                 result.get("Interpretation",                #changed: case variation
                                 result.get("interp",
                                 result.get("result", ""))))
                    interp = str(raw_interp).strip().lower()
                elif isinstance(result, str):
                    interp = result.strip().lower()
                else:
                    interp = str(result).strip().lower()

                interp = _AST_INTERP_ALIASES.get(interp, interp)
                pairs.append(f"{drug_norm}:{interp}")

    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                # Try "DRUG-INTERP" format
                parts = item.rsplit("-", 1)
                if len(parts) == 2:
                    drug_norm = parts[0].strip().lower()
                    interp = _AST_INTERP_ALIASES.get(
                        parts[1].strip().lower(), parts[1].strip().lower()
                    )
                    pairs.append(f"{drug_norm}:{interp}")
                else:
                    pairs.append(item.strip().lower())
            elif isinstance(item, dict):
                # Check for GT envelope format first                         #changed
                abx_key = _find_key_ci(item, "antibiotics")                  #changed
                if abx_key is not None:                                      #changed
                    _extract_antibiotics_list(item[abx_key], pairs)          #changed
                else:                                                        #changed
                    # Flat dict item: recurse                                #changed
                    sub = _normalise_ast(item)                               #changed
                    if sub:                                                   #changed
                        pairs.append(sub)                                    #changed

    elif isinstance(value, str):
        # Comma-separated string: "AMP-R, TET-S"
        for segment in value.split(","):
            segment = segment.strip()
            if not segment:
                continue
            parts = segment.rsplit("-", 1)
            if len(parts) == 2:
                drug_norm = parts[0].strip().lower()
                interp = _AST_INTERP_ALIASES.get(
                    parts[1].strip().lower(), parts[1].strip().lower()
                )
                pairs.append(f"{drug_norm}:{interp}")
            else:
                pairs.append(segment.lower())

    pairs.sort()
    return "|".join(pairs)


# ---------------------------------------------------------------------------
# AMR gene normaliser
# ---------------------------------------------------------------------------

def _normalise_amr(value: Any) -> str:
    """Normalise AMR gene names for comparison.                             #changed: new function

    Collapses underscores and hyphens to enable matching of
    'blaTEM-1B' vs 'bla_TEM-1B' vs 'blatem1b'.

    Examples:
        'blaTEM-1B'       -> 'blatem1b'
        'aac(6\\')-Ib'    -> 'aac(6\\')ib'
        ['blaTEM-1B']     -> 'blatem1b'
    """
    if isinstance(value, list):
        parts = sorted([_normalise_amr(v) for v in value if v])
        return "|".join(p for p in parts if p)

    s = str(value).strip().lower()
    # Remove hyphens and underscores (but keep parentheses for gene families)
    s = s.replace("-", "").replace("_", "").replace(" ", "")
    return s


# ---------------------------------------------------------------------------
# Generic normaliser (fallback)
# ---------------------------------------------------------------------------

def _normalise_generic(value: Any) -> str:
    """Generic value normalisation for fields without specific logic.

    Retained from v3 with minor cleanup.

    Args:
        value: Any value (str, list, dict, number).

    Returns:
        Normalised lowercase string.
    """
    if value is None:
        return ""

    if isinstance(value, list):
        parts = sorted([_normalise_generic(v) for v in value if v])
        return "|".join(p for p in parts if p)

    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True).lower()

    s = str(value).lower().strip()
    # Remove parenthetical annotations (e.g. "(predicted)")
    s = re.sub(r"\s*\([^)]*\)", "", s)
    # Collapse separators
    s = s.replace("-", "").replace("_", "").replace(" ", "")
    return s


# ===========================================================================
# GT / Extraction flattening (category-aware)
# ===========================================================================

def flatten_by_category(data: Dict) -> Dict:
    """Flatten a GT or extraction dict preserving the 3-category structure.

    Args:
        data: Dictionary with the v4 3-category keys (or GT JSON structure).

    Returns:
        Dictionary with keys:
            category (str): IWL, IWOL, NIOAI, IWL+IWOL, or EMPTY
            iwl_flat (dict): {isolate_id: {norm_field: (orig_value, norm_value)}}
            iwol_ids (list): [isolate_id, ...]
            nioai_flat (dict): {norm_field: (orig_value, norm_value)}
    """
    iwl_flat = {}
    iwol_ids = []
    nioai_flat = {}

    # --- IWL ---                                                              #changed
    # Keys to skip when iterating isolate dicts (non-assay metadata)           #changed
    _IWL_SKIP_KEYS = {                                                         #changed
        "isolate_id", "clean_text", "title", "abstract",                       #changed
        "merge_accession_number", "pmcid",                                     #changed
    }                                                                          #changed
    iwl_raw = data.get("isolates_with_linking", [])                            #changed: default to list

    if isinstance(iwl_raw, list):                                              #changed: handle list-of-dicts (GT format)
        for item in iwl_raw:                                                   #changed
            if not isinstance(item, dict):                                     #changed
                continue                                                       #changed
            iso_id = str(item.get("isolate_id", "")).strip()                   #changed
            if not iso_id:                                                     #changed
                logger.warning("IWL item missing isolate_id, skipped")         #changed
                continue                                                       #changed
            iso_fields = {}                                                    #changed
            for field, value in item.items():                                  #changed
                if field in _IWL_SKIP_KEYS:                                    #changed
                    continue                                                   #changed
                if value is None:                                              #changed
                    continue                                                   #changed
                if isinstance(value, list) and not value:                      #changed
                    continue                                                   #changed
                if isinstance(value, dict) and not value:                      #changed
                    continue                                                   #changed
                nf = normalise_field(field)                                    #changed
                if nf not in VALID_ASSAY_FIELDS:                              #changed
                    continue                                                   #changed
                nv = normalise_value(value, field_name=nf)                     #changed
                if nv:                                                         #changed
                    iso_fields[nf] = (value, nv)                              #changed
            if iso_fields:                                                     #changed
                iwl_flat[iso_id] = iso_fields                                 #changed

    elif isinstance(iwl_raw, dict):                                            #changed: keep dict format as fallback
        for iso_id, assays in iwl_raw.items():
            if not isinstance(assays, dict):
                continue
            iso_fields = {}
            for field, value in assays.items():
                if value is None:
                    continue
                if isinstance(value, list) and not value:
                    continue
                if isinstance(value, dict) and not value:                      #changed
                    continue                                                   #changed
                nf = normalise_field(field)
                if nf not in VALID_ASSAY_FIELDS:                              #changed
                    continue                                                   #changed
                nv = normalise_value(value, field_name=nf)
                if nv:
                    iso_fields[nf] = (value, nv)
            if iso_fields:
                iwl_flat[iso_id] = iso_fields

    # --- IWOL ---
    iwol_raw = data.get("isolate_without_linking", [])
    if isinstance(iwol_raw, list):
        for item in iwol_raw:
            if isinstance(item, str) and item.strip():
                iwol_ids.append(item.strip())
            elif isinstance(item, dict):
                # Some GTs store IWOL as list of dicts with isolate_id key
                iso_id = item.get("isolate_id", "")
                if iso_id:
                    iwol_ids.append(str(iso_id).strip())

    # --- NIOAI ---
    nioai_raw = data.get("no_isolates_only_assayinformation", {})
    if isinstance(nioai_raw, dict):
        for field, value in nioai_raw.items():
            if value is None:
                continue
            if isinstance(value, list) and not value:
                continue
            if isinstance(value, dict) and not value:
                continue
            nf = normalise_field(field)
            nv = normalise_value(value, field_name=nf)
            if nv:
                nioai_flat[nf] = (value, nv)

    # --- Determine category ---
    category = _determine_category(iwl_flat, iwol_ids, nioai_flat)

    return {
        "category": category,
        "iwl_flat": iwl_flat,
        "iwol_ids": iwol_ids,
        "nioai_flat": nioai_flat,
    }


def _determine_category(
    iwl: Dict, iwol: List, nioai: Dict
) -> str:
    """Infer category from which sections contain data.

    Args:
        iwl: Flattened IWL dict.
        iwol: List of IWOL isolate IDs.
        nioai: Flattened NIOAI dict.

    Returns:
        Category string.
    """
    has_iwl = bool(iwl)
    has_iwol = bool(iwol)
    has_nioai = bool(nioai)

    if has_iwl and has_iwol:
        return "IWL+IWOL"
    if has_iwl:
        return "IWL"
    if has_iwol:
        return "IWOL"
    if has_nioai:
        return "NIOAI"
    return "EMPTY"
