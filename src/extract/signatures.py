"""
signatures.py
=============
DSPy signatures for v4 assay extraction with 3-category SFA output.

Contains two signatures:
1. AssayExtractionSignature  - article text only (DD-2026-015)
2. SupplementaryAssayExtractionSignature - article text + multimodal
   supplementary files via the attachments library (DD-2026-016)

Both signatures produce the same 3-category output format (IWL/IWOL/NIOAI)
and feed into the identical evaluation pipeline.

Author: Luqman (AI6129 Pathogen Tracking Project)
Date:   March 2026
Design Decision: DD-2026-015, DD-2026-016
"""

import dspy

# Deferred import: only needed when supplementary signature is used
# from attachments.dspy import Attachments


class AssayExtractionSignature(dspy.Signature):                                
    """Extract pathogen assay information from a scientific article.

    TASK:
    1. Determine the article's data category:
       - IWL (Isolates With Linking): Specific isolate IDs exist AND assay
         results are linked to those isolate IDs.
       - IWOL (Isolates Without Linking): Specific isolate IDs are mentioned
         but assay data is NOT linked to individual isolates.
       - NIOAI (No Isolates, Only Assay Information): Assay results are
         reported at study/aggregate level with no individual isolate IDs.
    2. Extract all assay information into the corresponding section.

    ISOLATE ID RULES:
    - Use the exact isolate/strain code found in the article (e.g. lab codes
      like 'SA-2019-001', 'DP-213', or strain designations).
    - Do NOT substitute accession numbers (e.g. SAMN12345678), serovar names
      (e.g. 'Typhimurium'), MLST types (e.g. 'ST34'), or regulatory IDs
      when the actual isolate code is absent.
    - If no specific isolate identifiers exist, classify as NIOAI.

    ASSAY TYPES (use lowercase field names):
    serotype, mlst, cgmlst, ast_data, amr, plasmid, virulence_genes,
    pfge, spi, toxin, phage_type, snp

    OUTPUT FORMAT (JSON):
    {
        "category": "IWL" or "IWOL" or "NIOAI",
        "isolates_with_linking": {
            "<isolate_id>": {"<assay_type>": <value>, ...}, ...
        } or {},
        "isolate_without_linking": ["<isolate_id>", ...] or [],
        "no_isolates_only_assayinformation": {
            "<assay_type>": <value>, ...
        } or {}
    }

    RULES:
    - Populate ONLY the section matching the chosen category.
    - Leave non-applicable sections empty: {} for dict sections, [] for list.
    - Use lowercase for all field names.
    - For AST data, use: {"<drug>": "<interpretation>"} where interpretation
      is R (Resistant), I (Intermediate), or S (Susceptible).
      Only extract results from formal susceptibility testing.                         
      Do not infer susceptibility from treatment drug mentions alone.                  
      For aggregate/population-level studies, use the predominant S/I/R                
      interpretation — do not include percentage breakdowns.                           
    - For AMR genes, return as a list: ["blaTEM-1B", "aac(6')-Ib", ...].              
      Only include confirmed resistance genes. Do not include drug class names          
      (e.g. "aminoglycosides") or negative results (e.g. "mcr-1 negative").            
    - For serotype, return the serovar name without 'Salmonella' prefix.               
      Do not append prevalence counts or percentages (e.g. use "Rubislaw"              
      not "Rubislaw (13.3%)").                                                         
    - Always output the complete JSON for ALL isolates. Never truncate,
      summarise, or comment on output size.
    """

    article_text: str = dspy.InputField(
        desc="Full text extracted from a PubMed XML article"
    )
    assay_info: str = dspy.OutputField(
        desc="JSON with category classification and extracted assay data"
    )


# ===========================================================================
# Supplementary / multimodal extraction signature (DD-2026-016)
# ===========================================================================

def _get_attachments_type():                                                   
    """Import and return the Attachments type from attachments.dspy.

    Deferred so that article-only runs do not require the attachments package.
    """
    from attachments.dspy import Attachments
    return Attachments


class SupplementaryAssayExtractionSignature(dspy.Signature):                   
    """Extract pathogen assay information from an article AND its
    supplementary materials (tables, figures, spreadsheets, PDFs).

    You are given TWO sources of information:
    1. article_text: the full text of a PubMed XML article.
    2. supplementary_content: content from supplementary files associated
       with the article (Excel spreadsheets, PDF supplements, figures,
       Word documents). This content may include images of tables,
       phylogenetic trees, or other figures that contain assay data.

    TASK:
    1. Review BOTH the article text and supplementary content.
    2. Determine the data category (IWL, IWOL, or NIOAI) considering
       information from BOTH sources.
    3. Extract ALL assay information found across both sources.
    4. Where data appears in both article and supplementary, prefer the
       more detailed or granular version (supplementary tables typically
       contain per-isolate data that articles only summarise).

    CATEGORY DEFINITIONS:
    - IWL (Isolates With Linking): Specific isolate IDs exist AND assay
      results are linked to those isolate IDs.
    - IWOL (Isolates Without Linking): Specific isolate IDs are mentioned
      but assay data is NOT linked to individual isolates.
    - NIOAI (No Isolates, Only Assay Information): Assay results are
      reported at study/aggregate level with no individual isolate IDs.

    ISOLATE ID RULES:
    - Use the exact isolate/strain code found in the article or
      supplementary materials (e.g. lab codes, strain designations).
    - Do NOT substitute accession numbers, serovar names, MLST types,
      or regulatory IDs when the actual isolate code is absent.
    - If supplementary tables use different IDs from the article text,
      prefer the supplementary table IDs (they are typically more specific).

    ASSAY TYPES (use lowercase field names):
    serotype, mlst, cgmlst, ast_data, amr, plasmid, virulence_genes,
    pfge, spi, toxin, phage_type, snp

    OUTPUT FORMAT (JSON):
    {
        "category": "IWL" or "IWOL" or "NIOAI",
        "isolates_with_linking": {
            "<isolate_id>": {"<assay_type>": <value>, ...}, ...
        } or {},
        "isolate_without_linking": ["<isolate_id>", ...] or [],
        "no_isolates_only_assayinformation": {
            "<assay_type>": <value>, ...
        } or {}
    }

    RULES:
    - Populate ONLY the section matching the chosen category.
    - Leave non-applicable sections empty: {} for dict sections, [] for list.
    - Use lowercase for all field names.
    - For AST data, use: {"<drug>": "<interpretation>"} where interpretation
      is R (Resistant), I (Intermediate), or S (Susceptible).
      Only extract results from formal susceptibility testing.                         
      Do not infer susceptibility from treatment drug mentions alone.                  
      For aggregate/population-level studies, use the predominant S/I/R                
      interpretation — do not include percentage breakdowns.                           
    - For AMR genes, return as a list: ["blaTEM-1B", "aac(6')-Ib", ...].              
      Only include confirmed resistance genes. Do not include drug class names          
      (e.g. "aminoglycosides") or negative results (e.g. "mcr-1 negative").            
    - For serotype, return the serovar name without 'Salmonella' prefix.               
      Do not append prevalence counts or percentages (e.g. use "Rubislaw"              
      not "Rubislaw (13.3%)").                                                         
    """

    article_text: str = dspy.InputField(
        desc="Full text extracted from the PubMed XML article"
    )
    supplementary_content: str = dspy.InputField(                              
        desc=(
            "Content from supplementary files (spreadsheets, PDFs, figures, "
            "Word documents) associated with this article. May include "
            "extracted text from tables and base64-encoded images."
        )
    )
    assay_info: str = dspy.OutputField(
        desc="JSON with category classification and extracted assay data"
    )
