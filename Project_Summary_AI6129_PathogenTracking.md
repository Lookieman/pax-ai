# AI6129 Project Summary: AI-Enabled Pathogen Tracking System
## Project Overview

**Project Title:** AI-Enabled Pathogen Tracking System for Food Safety Monitoring  
**Client:** Singapore Food Agency (SFA)  
**Timeline:** August 2025 - April 2026  
**Key Deliverables:**
- Final code implementation: 15 March 2026
- First draft of report: April 2026

**Project Goal:** 

My Masters project is focused on improving on the current automated tool that uses a BERT transformer to extract assay information based on a specific pathogen for Singapore Food Authority(SFA). Previous usage of LLM did not provide good accuracy in terms of information extraction.

I am specifically focusing on the following methods:
a. extraction of usage of XML full articles using NCBI's E-utilities API instead of using pdf
b. usage of LLM models for information extraction
c. usage of prompt programming and prompt optimization via DSPY and GEPA respectively

to ultimately improve on the accuracy and precision of the extraction

The experiments also aims to answer the following questions:
a. Can LLM and usage of DSPY and GEPA improve on the accuracy score from the initial version?
b. Explore how much ground truth is needed for GEPA prompt optimization training for assay extraction
c. Explore which models that SFA is looking to use will provide the best performance for pathogen information extraction.
d. Whether the improved prompts work on articles for different pathogens
---

## Project Timeline & Phases

### Phase 1: Exploration & Design (August - September 2025)

**Initial Scope Definition**
- Originally explored Listeria pathogen as test case
- Established foundational understanding of NCBI E-utilities API
- Defined classification scheme:
  - Label 1: Articles with assay and metadata information
  - Label 2: Articles with prevalence information useful for extraction
  - Label 3: Irrelevant articles

**Key Technical Decisions:**
- Adopted 2-3 week exploration strategy for API familiarisation
- Decided to use DSPy instead of manual prompt engineering
- Established rate limiting compliance (3 requests/second without API key, 10 with key)
- Implemented delta extraction for periodic updates using timestamp tracking

**Initial Data Extraction:**
- Successfully downloaded ~650 PubMed articles about Listeria (January-June 2025)
- Stored in JSON format with abstracts, titles, and metadata
- Identified cross-pathogen transfer learning potential using existing labelled datasets (E.coli, Salmonella, Campylobacter)

---

### Phase 2: PubMed Article Downloader Development (September - October 2025)

#### Version 1 (v1): Basic Implementation
**Date:** Late August 2025  
**Activities:**
- Implemented basic PubMed search using Entrez API
- Retrieved article counts and metadata (PMID, Title)
- Added language filtering (English) and date range support
- Implemented basic rate limiting and error handling

**Technical Issues Resolved:**
- Type errors with None values in XML parsing
- Added comprehensive None checks in functions:
  - `extract_total_count()`
  - `extract_pmid_list()`
  - `extract_webenv()`
  - `extract_query_key()`
  - `parse_articles_xml()`

#### Version 2 (v2): Enhanced Functionality
**Date:** Early October 2025  
**Key Changes:**
- Switched primary identifier from PMID to PMCID
- Added abstract extraction capability
- Implemented PDF download functionality (later removed)
- Enhanced search query construction with field targeting
- Added monthly scheduling capability
- Implemented file compression for files >1MB

**Search Query Structure:**
```
((PathogenName[Title] OR PathogenName[Abstract] OR PathogenName[Methods - Key Terms]) 
OR (PathogenName[MeSH Terms] OR PathogenName[All Fields]) 
NOT ((review[All Fields] OR review literature as topic[MeSH Terms] OR review[All Fields]) 
NOT Overview[All Fields]))
```

**Critical Learnings:**
- Investigated `open_access[filter]` parameter
- Discovered it restricts results to free full-text content
- Decided against using filter to avoid excluding paywalled but relevant articles

**Technical Issues Resolved:**
- Google Drive mounting conflicts with logging initialisation
- Undefined logger variables in functions
- DataFrame type errors ("string indices must be integers")
- Proper logger initialisation patterns
- Type checking for DataFrames and dictionaries

**New Features:**
- Interactive mode for stakeholder month selection
- Batch mode for automated processing
- Display article counts prominently in interactive mode
- Comprehensive logging in batch mode

#### Version 3 (v3): NCBI Compliance & Full-Text XML
**Date:** Early October 2025  
**Major Architectural Changes:**
- Implemented PMID-to-PMCID conversion using NCBI's elink service
- Switched from PubMed abstracts to PMC full-text XML
- Removed PDF download functionality (NCBI policy compliance)
- Added comprehensive tracking for articles without PMC versions

**New Functions:**
- `convert_pmid_to_pmcid()` - PMID to PMCID conversion
- `fetch_pmc_fulltext_xml()` - Full-text XML retrieval
- `track_missing_pmcid()` - Track articles without PMC availability

**Code Review Identified 23 Critical Bugs:**
- Function name typos (pmicd vs pmcid)
- Missing variable definitions
- Wrong API endpoints (elink vs efetch)
- Outdated v2 tracking column structures
- Incorrect function signatures
- Variable name mismatches in logging
- Syntax errors (missing parentheses, wrong pandas concatenation)
- Malformed try-except blocks

#### Version 3a (v3a): Alternative Download Methods
**Date:** Mid-October 2025  
**Enhancement Goal:** Test multiple download approaches

**Added Download Methods:**
1. E-utilities (existing)
2. AWS S3 service via HTTPS
3. FTP service from NCBI PMC

**Implementation:**
- Separate interactive menu options
- Same file directory structure with method-specific subfolders
- Enhanced tracking to record download method and source URLs
- New functions for AWS S3 and FTP downloads with tar.gz extraction

**Critical Empirical Finding:**
Tested on June 2025 Hepatitis A data:
- **E-utilities:** 27 successful downloads
- **AWS S3:** 0 downloads (404 errors)
- **FTP:** 0 downloads (404 errors)

**Root Cause Analysis:**
- AWS and FTP only serve PMC Open Access Subset (~40% of PMC)
- E-utilities accesses full PMC collection
- Hepatitis A articles published in subscription journals deposited via NIH requirements
- 0% Open Access rate for test dataset

**Decision:** Reverted to v3 (E-utilities only) as optimal approach for project needs

#### Version 3.1 (v3.1): Supplementary File Downloads
**Date:** December 2025  
**Enhancement Goal:** Download supplementary materials alongside XML articles

**New Features:**
- Automatic supplementary file download after XML retrieval
- Support for multiple file types (PDF, Excel, images)
- Per-article supplementary folder structure
- Integration with OA file list for package locations

**Implementation Results:**
- Successfully processed 227 ground truth documents
- Downloaded 1,335 supplementary files total
- 100% success rate for articles in OA subset

---

### Phase 3: DSPy Implementation & Classification (October 2025)

#### Article Classification with DSPy
**Activities:**
- Designed `ArticleClassificationSignature` for DSPy
- Implemented few-shot predictor using cross-pathogen examples
- Started with title and abstract classification
- Used chain-of-thought reasoning for model decision transparency
- Initial testing on 50-article sample from Listeria dataset

**Transfer Learning Validation:**
- Confirmed cross-pathogen transfer learning viability
- Classification focuses on methodology and study types, not pathogen-specific content
- Existing labelled datasets (E.coli, Salmonella, Campylobacter) valuable for few-shot examples

#### GenBank Accession Number Extraction
**Date:** Late October 2025  
**Objective:** Extract GenBank accession numbers from scientific articles

**Development Process:**
1. Created comprehensive NCBI accession format reference (200+ lines)
2. Organised by prefix length (1-letter through 6-letter)
3. Documented sequence types (EST, GSS, WGS, TSA, protein, etc.)
4. Included INSDC partners (NCBI, EBI, DDBJ)
5. Added validation rules, RefSeq patterns, version numbering
6. Documented common false positives to avoid

**Implementation Approach:**
- Used DSPy for accession extraction
- Created `AccessionExtractionSignature` class
- Integrated NCBI format rules as context
- Implemented both single-file and folder processing
- Added progress tracking and comprehensive error handling

**Google Colab Integration:**
- Developed `ColabAIWrapper` for DSPy integration
- Supports Google Colab built-in models:
  - google/gemini-2.0-flash-lite
  - google/gemini-2.0-flash
- Eliminates need for external API keys
- Leverages Colab Pro+ subscription (1800 compute units)

**Technical Challenges & Solutions:**
1. File path errors - resolved by proper `setup_colab_environment()` calling
2. API compatibility issues - Colab AI doesn't accept `temperature` and `model` parameters
3. Quality issues - duplicates and format examples appearing in results
4. Solution: Added explicit constraints in signature class docstring
5. False positive validation - identified non-GenBank identifiers (e.g., journal DOIs)

---

### Phase 4: Multimodal Extraction Design (January 2025)

#### Design Decision: Multimodal Accession and Assay Extraction

**Date:** 22 January 2026  
**Decision ID:** DD-2026-001  
**Status:** Approved for Implementation

**Problem Statement:**
During evaluation of low-recall accession extraction cases, it was identified that some full XML articles contain accession numbers and assay information embedded within figures (e.g., phylogenetic trees, data tables rendered as images). The XML `<graphic>` element contains only a reference to the image file (via `xlink:href`), not the image data itself.

**Example Case:** PMC7738724 (Salmonella shelter dogs study)
- Figure 1 contains a phylogenetic tree with 27 SRA accession numbers (SRR format)
- Also contains assay information: Serotype, MLST profiles, AMR genes
- This information is NOT present in the XML text body
- XML reference: `<graphic xlink:href="VMS3-6-975-g001.jpg"/>`

**Decision:**
Implement multimodal extraction capability using the `attachments` library to process figures and supplementary files alongside XML text extraction.

**Rationale:**
1. **Completeness:** Extracting only from XML text would yield lower recall than PDF-based extraction for articles with figure-embedded data
2. **Research Contribution:** Demonstrates feasibility of DSPy/GEPA for multimodal biomedical information extraction
3. **Practical Value:** Supplementary files (PDFs, Excel) often contain critical assay data not in main text
4. **Cost-Benefit:** For 227 ground truth documents, vision API costs are acceptable for demonstrating feasibility

**Technical Approach:**

1. **Library Selection:** `attachments` library (https://maximerivest.github.io/attachments/)
   - Native DSPy integration via `from attachments.dspy import Attachments`
   - Supports images (PNG, JPG, GIF), PDFs, Excel, PowerPoint
   - Automatic base64 encoding for vision models
   - Compatible with Claude and OpenAI vision APIs

2. **Architecture:**
   - Parallel extraction paths: XML text + multimodal attachments
   - Separate DSPy signature for multimodal content
   - Source tracking for audit trail (which accessions came from which source)
   - Merged and deduplicated final output

3. **New DSPy Signature:**
```python
class MultimodalAccessionExtractor(dspy.Signature):
    """Extract accessions from figures, tables, and supplementary files."""
    attachment: Attachments = dspy.InputField()
    format_rules: str = dspy.InputField()
    context_hint: str = dspy.InputField()
    accessions: list[str] = dspy.OutputField()
    reasoning: str = dspy.OutputField()
```

4. **Folder Structure:**
```
AI6129/
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ attachments/           # Article figures
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ PMC{id}/
Ã¢â€â€š       Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ {figure}.jpg
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ supplementary/         # Downloaded supp files
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ PMC{id}/
Ã¢â€â€š       Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ supp_table.xlsx
Ã¢â€â€š       Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ supp_data.pdf
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ xml/                   # Full-text XML
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ PMC{id}_{date}.xml
```

**Model Requirements:**
- Vision-capable model required (Claude Sonnet 3.5+, Claude Haiku 3.5, GPT-4V)
- Higher token costs than text-only extraction
- Estimated 5-10x cost increase per figure processed

**Scope Boundaries:**
- Phase 1: Test on PMC7738724 figure as proof of concept
- Phase 2: Extend to all 227 ground truth documents with figures
- Phase 3: Include supplementary Excel/PDF processing
- Future: Cost-benefit analysis for SFA to decide production deployment

**Success Criteria:**
- Successfully extract SRA accessions from PMC7738724 Figure 1
- Achieve >80% recall on figure-embedded accessions
- Document extraction source in audit trail
- Demonstrate GEPA optimisation capability on multimodal signatures

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Skip figure extraction | Simpler, lower cost | Lower recall than PDF approach | Rejected |
| OCR preprocessing | Cheaper per image | Lower accuracy (70-85%), complex pipeline | Rejected |
| Manual annotation | High accuracy | Not scalable, defeats automation goal | Rejected |
| Query NCBI BioProject | Reliable for some data | Doesn't capture all figure content | Partial use |
| Vision API (selected) | High accuracy, native DSPy support | Higher cost | Selected |

**Implementation Priority:** Medium
- Not blocking main pipeline development
- Valuable for demonstrating framework capabilities
- Can be added incrementally after text extraction is stable

**Dependencies:**
- PubMed Downloader v3.1 (supplementary file download) - Complete
- Attachments library installation
- Vision-capable model access (Claude API)
- Folder structure setup in Google Drive

---

#### Design Decision: Unified Assay Extraction Signature for Cross-Pathogen Support

**Date:** 24 January 2026  
**Decision ID:** DD-2026-002  
**Status:** Approved for Implementation

**Problem Statement:**
The existing `AssayExtractionSignature` was designed exclusively for bacterial pathogens (Salmonella, E. coli, Campylobacter). The current assay types (MLST, AST, SPI, AMR, Plasmid, SNP, Virulence_Genes) are not applicable to the target Hepatitis A and E datasets. Additionally, several common bacterial assays were missing from the original signature.

**Gap Analysis:**

| Current Assay | Applicable to Hepatitis? | Notes |
|---------------|--------------------------|-------|
| MLST | No | Bacterial typing method |
| AST | No | Antibiotics not relevant for viruses |
| SPI | No | Salmonella-specific |
| AMR | No | Antimicrobial resistance is bacterial |
| Plasmid | No | Viruses lack plasmids |
| SNP | Yes | Viral mutations applicable |
| Virulence_Genes | Partial | Viral proteins differ from bacterial genes |

**Decision:**
Create a unified `AssayExtractionSignature` that supports both bacterial and viral pathogens through explicit categorisation in the docstring, enabling cross-pathogen transfer learning whilst maintaining a single signature architecture.

**Rationale:**
1. **Cross-Pathogen Transfer Learning:** Project goal requires prompts that generalise across pathogen types
2. **Simplicity:** Single signature avoids routing logic complexity
3. **Future-Proofing:** Supports potential expansion to other pathogens (Norovirus, Listeria, etc.)
4. **LLM Context:** Explicit grouping provides sufficient context for the model to prioritise relevant assays
5. **Ground Truth Compatibility:** Bacterial assays still evaluable against Salmonella ground truth

**Assay Types Added:**

*Bacterial (missing from original):*
| Assay | Description | Justification |
|-------|-------------|---------------|
| cgMLST | Core genome MLST | Increasingly common in WGS studies |
| Serotype | O:H antigen typing | Very high frequency; notable omission |
| PFGE | Pulsed-Field Gel Electrophoresis | Legacy method in historical studies |
| Toxin | Toxin genes (stx1, stx2) | Critical for STEC characterisation |
| Phage_Type | Bacteriophage typing | Present in older Salmonella literature |

*Viral (new category):*
| Assay | Description | Justification |
|-------|-------------|---------------|
| Genotype | HAV: I-VII; HEV: 1-8 | Primary viral classification |
| Subgenotype | e.g., IA, IB, 3a, 3c | Epidemiological tracing |
| Viral_Load | Copies/mL, IU/mL | Common clinical measurement |
| Sequencing_Region | VP1/P2A, ORF1, ORF2 | Standard typing targets |
| Phylogenetic_Clade | Cluster assignments | Links to figure-based analysis |
| Serology | IgM/IgG markers | Diagnostic confirmation |

*Universal (renamed/retained):*
| Assay | Change | Justification |
|-------|--------|---------------|
| SNP | Retained | Applicable to both bacteria and viruses |
| Virulence_Factors | Renamed from Virulence_Genes | Broader term covering proteins and genes |

**Updated Signature:**
```python
class AssayExtractionSignature(dspy.Signature):
    """
    Extract assay information from a biomedical article for specified isolates.
    
    BACTERIAL ASSAYS (Salmonella, E. coli, Campylobacter, Listeria, etc.):
    - MLST: Multi-Locus Sequence Typing (sequence types, allele profiles)
    - cgMLST: Core genome MLST (extended typing with hundreds of loci)
    - AST: Antimicrobial Susceptibility Testing (MIC values, interpretations)
    - AMR: Antimicrobial Resistance genes (gene names, mechanisms)
    - Serotype: Serological typing (O:H antigens, serovar names)
    - Plasmid: Plasmid typing (incompatibility groups, replicon types)
    - PFGE: Pulsed-Field Gel Electrophoresis (pattern designations)
    - SPI: Salmonella Pathogenicity Islands (SPI-1 through SPI-5)
    - Toxin: Toxin genes (stx1, stx2, enterotoxins, etc.)
    - Phage_Type: Bacteriophage typing results
    
    VIRAL ASSAYS (Hepatitis A, Hepatitis E, Norovirus, etc.):
    - Genotype: Viral genotype classification (e.g., HAV genotype I, HEV genotype 3)
    - Subgenotype: Viral subgenotype (e.g., IA, IB, 3a, 3c)
    - Viral_Load: Quantitative viral RNA/DNA (copies/mL, IU/mL)
    - Sequencing_Region: Genomic region sequenced (VP1/P2A, ORF1, ORF2)
    - Phylogenetic_Clade: Cluster or clade assignment from phylogenetic analysis
    - Serology: Serological markers (IgM, IgG, antibody titres)
    
    UNIVERSAL ASSAYS (applicable to both):
    - SNP: Single Nucleotide Polymorphisms (positions, mutations)
    - Virulence_Factors: Virulence genes or proteins detected
    
    Return JSON mapping isolate IDs to their assay results.
    Only include assays explicitly reported in the article.
    Use null for assays mentioned but with no value reported.
    """
    
    article_text: str = dspy.InputField(
        desc="Full text of the biomedical research article in XML format"
    )
    isolate_ids: str = dspy.InputField(
        desc="Comma-separated list of isolate identifiers to extract assays for"
    )
    assay_info: str = dspy.OutputField(
        desc="JSON object mapping each isolate ID to its assay results. "
             "Format: {isolate_id: {assay_type: value, ...}, ...}"
    )
```

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Separate bacterial/viral signatures | Cleaner separation | Requires routing logic, breaks transfer learning | Rejected |
| Add pathogen_type input field | Explicit pathogen context | Risk of misclassification propagating | Rejected |
| Minimal extension (3 viral types only) | Simpler | Not future-proof for other pathogens | Rejected |
| Unified signature (selected) | Single architecture, LLM infers context | Longer docstring | Selected |

**Validation Approach:**
1. Bacterial assays validated against existing Salmonella ground truth (227 documents)
2. Viral assays validated qualitatively on small Hepatitis sample (10-15 articles)
3. GEPA optimisation uses bacterial ground truth; viral extraction benefits from transferred reasoning patterns

**Impact on Existing Pipeline:**
- No architectural changes required
- Existing evaluation code compatible (additional assay types ignored if not present)
- Ground truth schema unchanged (new assays simply not present in bacterial data)

**Success Criteria:**
- Maintain baseline F1 on bacterial assay extraction (â‰¥78.5%)
- Demonstrate extraction of Genotype, Subgenotype, and Sequencing_Region from Hepatitis articles
- No regression in GEPA optimisation performance

**Implementation Priority:** High
- Required before Hepatitis A/E validation experiments
- Blocks cross-pathogen transfer learning demonstration

**Dependencies:**
- Existing AssayExtractionSignature implementation - Complete
- Hepatitis A/E test corpus - Available (27 articles)
- GEPA optimisation infrastructure - In progress

---

#### Design Decision: GEPA-Optimised Data Stratification

**Date:** 25 January 202  
**Decision ID:** DD-2026-003  
**Status:** Approved for Implementation

**Problem Statement:**
During initial GEPA optimisation experiments using the stratified data splits, GEPA issued a warning:

```
Using 165 examples for tracking Pareto scores. You can consider using a smaller 
sample of the valset to allow GEPA to explore more diverse solutions within the 
same budget. GEPA requires you to provide the smallest valset that is just large 
enough to match your downstream task distribution, while providing as large 
trainset as possible.
```

The original stratification (assay_tadp_nested_splits.ipynb) created splits with:
- 10% training (18 samples) / 90% validation (165 samples)
- 20% training (37 samples) / 80% validation (146 samples)
- 30% training (55 samples) / 70% validation (128 samples)

This inverts GEPA's expected ratios: GEPA requires **large training sets** for diverse prompt exploration and **small validation sets** for efficient Pareto score tracking.

**Root Cause Analysis:**

| GEPA Component | Purpose | Size Requirement |
|----------------|---------|------------------|
| Training Set | Generate candidate prompts, explore solution space | Large (more data = more diverse prompts) |
| Validation Set | Track Pareto scores, evaluate candidates | Small (every candidate evaluated on all samples) |

The original design treated the training percentages as the primary variable, with validation as the remainder. This created the inverted ratio.

**Decision:**
Redesign the stratification to use a **fixed, small validation set** with **variable training sizes**, ensuring GEPA can explore diverse solutions within the same compute budget.

**New Split Structure:**

```
Total: 227 documents
â”œâ”€â”€ Holdout (20%): ~45 samples (unchanged - for final evaluation)
â””â”€â”€ Working Set (80%): ~182 samples
    â”œâ”€â”€ Validation (Fixed): 35 samples (stratified, representative)
    â””â”€â”€ Training Pool: ~147 samples
        â”œâ”€â”€ 10% Experiment: ~18 samples training + 35 validation
        â”œâ”€â”€ 20% Experiment: ~37 samples training + 35 validation
        â””â”€â”€ 30% Experiment: ~55 samples training + 35 validation
```

**Rationale:**
1. **GEPA Compliance:** Follows GEPA's documented requirements for optimal exploration
2. **Fair Comparison:** Same validation set across all experiments eliminates confounding variance
3. **Statistical Validity:** 35 validation samples (~8-9 per quartile) sufficient to represent TADP distribution
4. **Compute Efficiency:** Smaller validation set allows GEPA to evaluate more candidate prompts
5. **Research Question Alignment:** Still answers RQ2 (ground truth data requirements) by varying training size

**Validation Set Size Justification:**

| Factor | Consideration |
|--------|---------------|
| Quartile coverage | ~8-9 samples per quartile (4 quartiles Ã— 8-9 = 32-36) |
| Distribution matching | 35 samples can represent TADP distribution adequately |
| GEPA guidance | "Smallest that matches downstream task distribution" |
| Statistical power | Sufficient for Pareto score tracking |

**Expected Experiment Configurations:**

| Config | Training | Validation | Train:Val Ratio |
|--------|----------|------------|-----------------|
| 10% | ~18 | 35 | 0.51:1 |
| 20% | ~37 | 35 | 1.06:1 |
| 30% | ~55 | 35 | 1.57:1 |

**Implementation Changes:**

1. New notebook: `assay_tadp_gepa_optimised_splits.ipynb`
2. Output files renamed to: `assay_tadp_gepa_optimised_splits.json/.csv`
3. New field `training_pool` added to track available training samples
4. `validation_set` now fixed size rather than computed as remainder

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Keep original splits | No code changes | Suboptimal GEPA exploration | Rejected |
| Scale validation proportionally | Larger training experiments get larger validation | Unfair comparison across experiments | Rejected |
| Fixed validation (selected) | GEPA-optimal, fair comparison | Requires re-stratification | Selected |
| Very small validation (20 samples) | Maximum exploration | May not represent distribution | Rejected |

**Impact on Research Questions:**

- **RQ2 (Ground truth requirements):** Still answerable - training size varies while validation is constant
- **Comparison validity:** Improved - same validation set ensures fair comparison
- **GEPA efficiency:** Improved - more diverse solutions explored per compute budget

**Migration Notes:**

- Previous split file: `assay_tadp_nested_splits.json` (archived)
- New split file: `assay_tadp_gepa_optimised_splits.json`
- Any existing experiments using old splits should be re-run with new splits for valid comparison

**Success Criteria:**
- GEPA no longer issues validation set size warning
- Training:Validation ratio >= 0.5:1 for all experiments
- Nested structure (10% âŠ‚ 20% âŠ‚ 30%) maintained
- Quartile distribution in validation matches overall distribution

---
# Design Decision: DD-2026-004 - GEPA Stage 0 Pilot Implementation

**Date:** 26 January 2026  
**Author:** Luqman  
**Status:** Approved  
**Related to:** RQ2 (Ground truth requirements), RQ3 (Model comparison)

---

## Context

Implementation of GEPA-based prompt optimisation for assay extraction requires several architectural and methodological decisions before proceeding with experiments.

---

## Decisions Made

### DD-2026-001a: Single-Module Architecture for Stage 0

**Decision:** Use a single `AssayExtractor` module with `ChainOfThought` for the pilot phase, rather than a multi-module pipeline.

**Rationale:**
- Establishes baseline behaviour before adding complexity
- Simpler debugging and iteration
- GEPA can optimise single signatures effectively
- Multi-module approach can be implemented in Stage 1 if needed

**Alternative Considered:** Two-stage pipeline (isolate extraction â†’ assay extraction)

---

### DD-2026-001b: Uncertain Positive (UP) Classification

**Decision:** Implement three-tier classification for extracted assays:
- **True Positive (TP):** Extracted matches ground truth
- **False Positive (FP):** Extracted not in article text AND not in ground truth (hallucination)
- **Uncertain Positive (UP):** Extracted IS in article text but NOT in ground truth

**Rationale:**
- Addresses known ground truth gaps discovered during accession extraction
- Distinguishes true model errors (hallucinations) from potential GT incompleteness
- Provides more nuanced evaluation

**Metric Reporting:**
1. **Conservative F1:** Treats UP as FP (lower bound)
2. **Primary F1:** Excludes UP from calculation (recommended)
3. **Optimistic F1:** Treats UP as TP (upper bound)

---

### DD-2026-001c: Rate Limiting Strategy for GEPA

**Decision:** Use conservative parallelisation with `num_threads=2` and `auto="light"` budget.

**Rationale:**
- GEPA's internal optimisation loop bypasses custom rate limiting
- Low thread count naturally limits concurrent API calls
- Light budget sufficient for pilot validation
- Prevents rate limit errors during optimisation

**Production Scaling:** For formal experiments, increase to `num_threads=4` and `auto="medium"` or `auto="heavy"`.

---

### DD-2026-001d: Separate Notebooks for Optimisation and Inference

**Decision:** Maintain separate notebooks:
1. `gepa_assay_extraction_stage0_pilot.ipynb` - GEPA optimisation
2. `assay_extraction_inference.ipynb` (to be created) - Test set evaluation

**Rationale:**
- Separation of concerns
- Inference notebook CAN use custom token-based rate limiting
- Different checkpointing requirements
- Cost control during development

---

### DD-2026-001e: Model Configuration

**Decision:**
- **Extraction Model:** Claude Haiku 4.5 (`anthropic/claude-haiku-4-5-20251001`)
- **Reflection Model:** Claude Sonnet 4 (`anthropic/claude-sonnet-4-20250514`)

**Rationale:**
- Haiku 4.5 is cost-effective for high-volume extraction calls
- Sonnet 4 provides higher capability for GEPA's reflection and prompt evolution
- Matches existing accession extraction baseline configuration

---

## Files Generated

| File | Purpose |
|------|---------|
| `gepa_assay_extraction_stage0_pilot.ipynb` | Main GEPA optimisation notebook |
| `{experiment_id}_optimised_program.json` | Saved DSPy optimised program |
| `{experiment_id}_results.json` | Experiment metrics and configuration |
| `{experiment_id}_gepa_log.txt` | Detailed iteration and feedback log |

---

## Experimental Design

### Training Splits (TADP-Stratified)
- **10% Split:** 18 documents
- **20% Split:** 37 documents  
- **30% Split:** 54 documents

### Validation Set
- 35 documents (fixed across all experiments)

### Holdout Set
- 45 documents (reserved for final evaluation)

---

## Success Criteria for Stage 0

1. âœ… Notebook executes without errors
2. â³ Baseline F1 established on validation set
3. â³ GEPA optimisation completes for 10% split
4. â³ Measurable improvement (any positive delta)
5. â³ All iterations and feedback logged

---

## Next Steps After Stage 0

1. Analyse results across 10%/20%/30% splits
2. Determine optimal training data size (RQ2)
3. Create inference notebook for test set evaluation
4. Extend to Hepatitis A/E for cross-pathogen validation (RQ4)
5. Transition to AWS Bedrock Singapore for compliance experiments (RQ3)

---

## Appendix: Corrected Assay Type Lists

```python
BACTERIAL_ASSAY_TYPES = [
    "serotype", "mlst", "cgmlst", "spi", "ast_data",
    "amr", "plasmid", "pfge", "toxin", "phage_type",
    "snp", "virulence_genes"
]

VIRAL_ASSAY_TYPES = [
    "genotype", "subgenotype", "viral_load",
    "sequencing_region", "phylogenetic_clade", "serology"
]

UNIVERSAL_ASSAY_TYPES = ["snp", "virulence_factors"]
```

---

---

# Design Decision: DD-2026-007 - Golden GT Diagnostic Assessment and Remediation

**Date:** 1 March 2026  
**Author:** Luqman  
**Status:** In Progress  
**Related to:** RQ2 (Ground truth requirements), GEPA evaluation framework  
**Blocking:** All GEPA optimisation and final evaluation experiments

---

## Context

The golden test set (45 manually-labelled records: 35 Salmonella + 10 E. coli) serves as the final evaluation benchmark for GEPA-optimised prompts. Before proceeding with any optimisation experiments, the golden GT must be validated to ensure it provides a reliable evaluation yardstick. A diagnostic analysis was run using the unchanged baseline DSPy CoT signature (from DD-2026-004) against all 45 golden records.

---

## Diagnostic Findings

**Headline:** Mean primary F1 = 0.047 across 45 records. Only 2/45 records scored above F1 $\geq$ 0.3. 78% of GT isolate IDs not found in article text. The golden set has inherited the same structural quality issues as the original 227 GT.

### Five Problem Patterns Identified

**Pattern 1: Accession numbers counted as assay data (23/45 records)**

The Excel-to-JSON converter includes `accession_numbers` and `merge_accession_number` as GT fields. The assay extraction signature does not (and should not) extract accession numbers --- that is a separate pipeline stage (Stage 1). Every accession entry in GT generates a false negative.

Impact: Records with accession fields have mean F1 = 0.010 vs 0.085 for those without.

Affected PMCIDs: PMC4881965, PMC4892500, PMC4932652, PMC5033494, PMC5047355, PMC5799193, PMC6026178, PMC6097345, PMC6218967, PMC6262260, PMC6412060, PMC6449608, PMC6605661, PMC6667439, PMC6700665, PMC7064254, PMC7240076, PMC7598458, PMC7947892, PMC8175864, PMC9228531, PMC9641423, PMC9643863.

**Pattern 2: GT annotates different fields than LLM extracts (field coverage mismatch)**

Some GT records only contain metadata fields (isolate\_source, isolate\_country) but no assay fields. The LLM correctly extracts assay data (AMR, AST, virulence genes) but gets zero TP because the GT has no assay annotations to match against.

Key example: PMC2409344 --- 19/19 isolate IDs match exactly, LLM extracts valid AMR/AST/virulence data, but F1 = 0.000 because GT only annotated source and country.

Metadata-only records identified: PMC2409344, PMC2718522, PMC6097345.

**Pattern 3: GT isolate IDs not matching extractable identifiers**

Three sub-patterns:
- *Numeric row IDs:* PMC7273606 uses GT IDs "1", "2", "3" (Excel row numbers) instead of actual strain codes (S615, S616, CS16064). The article Table 1 uses "Case no." which the annotator adopted literally.
- *Unicode dash mismatch:* PMC4932652 has GT IDs with en-dash (U+2013, e.g. "XJ10--14") but the LLM extracts standard hyphen (U+002D, "XJ10-14"). Same issue in PMC7783345. Introduced during Excel-to-JSON conversion.
- *Supplementary filename as ID:* PMC4881965 uses "pone.0156212.s001.xlsx" as isolate ID instead of actual strain numbers from the supplementary table.

**Pattern 4: GT data sourced from supplementary materials not in article XML (21 records with >80% IDs not in text)**

Records where GT annotations derive from supplementary tables or external databases. The article XML contains none of this data, making text-based extraction impossible.

Fully supplementary (100% IDs not in text): PMC5799193, PMC7064254, PMC8175864, PMC6700665, PMC8478212, PMC9228531, PMC6026178, PMC6412060, PMC5025531, PMC7947892, PMC4881965, PMC6218967.

**Pattern 5: Output token limit causing extraction failure (2 records)**

PMC5033494 (128 isolates, 588 GT items) and PMC6667439 (43 isolates, 421 GT items) produce zero extracted output despite isolate IDs being present in article text. Root cause: the `max_tokens=8192` limit on the LM is insufficient for articles with many isolates. The complete JSON output would require 30,000--60,000 tokens, so the output is truncated mid-JSON and the parser returns an empty dict. This is an extraction limitation, not a GT quality problem.

Verification method: inspect raw LLM output in Colab --- if it ends mid-JSON without a closing brace, output truncation is confirmed.

---

## Decisions Made

### DD-2026-007a: Remove accession fields from golden GT converter

**Decision:** Modify `golden_gt_converter.py` to exclude `accession_numbers` and `merge_accession_number` from the isolate dictionary. Accession extraction is evaluated separately in Stage 1.

**Rationale:** These fields inflate FN count by thousands and depress F1 scores across 23/45 records. They belong to a different pipeline stage.

**Implementation:** Remove the two conditional blocks that add `accession_list` and `accession_merge` to the isolate dict in the converter.

### DD-2026-007b: Add Unicode dash normalisation to converter

**Decision:** Normalise en-dash (U+2013), em-dash (U+2014), and figure-dash (U+2012) to standard ASCII hyphen (U+002D) in isolate IDs during Excel-to-JSON conversion.

**Rationale:** Excel introduces Unicode dashes that prevent ID matching during evaluation. Affects PMC4932652 (5 IDs) and PMC7783345 (7 IDs).

**Implementation:** Single normalisation line after reading isolate\_id from Excel:
```python
isolate_id = isolate_id.replace('\u2013', '-').replace('\u2014', '-').replace('\u2012', '-')
```

### DD-2026-007c: Manual GT corrections (3 records)

| PMCID | Issue | Action |
|-------|-------|--------|
| PMC4881965 | Supplementary filename as isolate ID | Replace with actual strain numbers from supplementary table |
| PMC7273606 | Case study row numbers as isolate IDs | Replace "1"-"8" with actual strain codes (S615, S616, CS16064, etc.) from article |
| PMC4932652 | Unicode dash mismatch | Handled by DD-2026-007b converter fix |

### DD-2026-007d: Set aside supplementary-only records for holdout

**Decision:** Set aside records where GT data is entirely from supplementary materials (not extractable from article XML) into a separate holdout set for future supplementary text extraction validation.

**Records set aside (13):**

| PMCID | GT Isolates | % Not in Text | Reason |
|-------|-------------|---------------|--------|
| PMC5799193 | 196 | 100% | Supplementary-sourced |
| PMC7064254 | 202 | 100% | Supplementary-sourced |
| PMC8175864 | 298 | 100% | Supplementary-sourced |
| PMC6700665 | 126 | 100% | Supplementary-sourced |
| PMC8478212 | 77 | 100% | Supplementary-sourced |
| PMC9228531 | 73 | 100% | Supplementary-sourced |
| PMC6026178 | 59 | 100% | Supplementary-sourced |
| PMC6412060 | 31 | 100% | Supplementary-sourced |
| PMC5025531 | 27 | 100% | Supplementary-sourced |
| PMC7947892 | 12 | 100% | Supplementary-sourced |
| PMC6218967 | 190 | 97% | Effectively supplementary |
| PMC2718522 | 10 | 100% | Metadata-only GT + supplementary |
| PMC7590148 | 41 | 100% | Supplementary PDF data |

### DD-2026-007e: Enrich metadata-only GT records

**Decision:** For PMC2409344, add assay annotations (AMR, AST, virulence genes) to the Excel GT to match what is extractable from the article. This record has 19/19 ID match and the LLM demonstrably extracts valid data --- the GT is incomplete, not wrong.

**Note:** PMC2718522 and PMC6097345 are also metadata-only but have 0% IDs in text (supplementary-sourced), so they are set aside under DD-2026-007d instead.

### DD-2026-007f: Retain E. coli records with empty "others" sheets

**Decision:** The 8 E. coli PMCIDs with empty `isolate_without_linking` and `no_isolates_only_assayinformation` sheets are NOT archived. These records genuinely only have `isolates_with_linking` data and include the two best-performing golden records (PMC2694269 F1=0.410, PMC1278947 F1=0.300).

PMCIDs retained: PMC1278947, PMC2409344, PMC2694269, PMC2725854, PMC2873750, PMC2874370, PMC2958529, PMC3020606.

Converter must handle empty "others" sheets gracefully (generate empty sections, not malformed JSON).

### DD-2026-007g: Document output token limit for high-isolate articles

**Decision:** PMC5033494 (128 isolates) and PMC6667439 (43 isolates) are retained in the golden set but flagged as output-token-limited. These are genuine extraction challenges, not GT quality problems. Potential mitigations for future work: increase `max_tokens`, implement batched extraction, or apply article sectioning.

---

## Expected Impact After Remediation

| Metric | Before | Expected After |
|--------|--------|----------------|
| Records evaluable | ~2/45 usable | ~25-30/45 usable |
| Accession FN inflation | ~15,600 FN items | Eliminated |
| Unicode ID mismatches | PMC4932652, PMC7783345 | Fixed |
| Set-aside (supplementary) | 0 | 13 records |
| Metadata-only records | 3 records (F1=0) | 1 enriched, 2 set aside |

---

## Action Sequence

1. **Immediate:** Fix converter (remove accession fields, add Unicode normalisation)
2. **Immediate:** Manual corrections for PMC4881965, PMC7273606
3. **Immediate:** Move 13 supplementary-only Excel files to archive
4. **Short-term:** Enrich PMC2409344 GT with assay annotations
5. **Short-term:** Regenerate all golden JSONs and re-run diagnostic
6. **Short-term:** Verify output truncation for PMC5033494, PMC6667439 in Colab
7. **Then:** Proceed to new 89 diagnostic and GEPA optimisation experiments

---

## Files

| File | Location | Purpose |
|------|----------|---------|
| golden\_gt\_converter.py | AI6129/design/golden/ | Converter (to be updated) |
| gt\_diagnostic\_report.json | AI6129/assay/gt\_diagnostic\_analysis/golden/ | Full diagnostic output |
| gt\_diagnostic\_summary.csv | AI6129/assay/gt\_diagnostic\_analysis/golden/ | Per-document summary |
| gt\_diagnostic\_analysis\_v2.ipynb | AI6129/assay/gt\_diagnostic\_analysis/ | Diagnostic notebook |

---

# Design Decision: DD-2026-011 - Prefix 90 Remaining Records Classification

**Decision ID:** DD-2026-011  
**Date:** 17 March 2026  
**Context:** After Phase 1 classification (DD-2026-010) classified 41/90 prefix records, 49 records remained unmapped. Luqman completed manual review of all 49 records, mapping isolate codes and assay data locations. The majority (36) were `major_gt_update` --- articles with genuine isolate/assay data but completely empty GT (0 isolates, 0 items).

**Decision:** Exclude all 37 records classified as `SET_ASIDE_MAJOR_GT` (36 original `major_gt_update` + PMC8749661 reclassified from `over_extraction`). These require GT *construction*, not *correction*, which is infeasible within the project timeline. Explicitly include 4 user-selected records (PMC7200987, PMC6312689, PMC8947133, PMC9530323) for training/validation.

**Rationale:**

1. **GT construction vs correction:** Every other remediation category (metadata contamination, Unicode mismatches, converter bugs, ID scheme mismatches) involves correcting *existing* GT entries. These 37 records have no GT at all. Manually building 20--339 isolate entries per record with associated assay data is a creation exercise, not a correction.
2. **Supplementary overlap:** At least 16/37 records have data wholly or partially in supplementary files. Even with populated GT, many would be SET\_ASIDE\_SUPP.
3. **Extraction validation:** 14/37 records have oF1 > 0.7, providing independent evidence that the LLM pipeline correctly extracts data the annotator never captured. This is documented as a positive finding for the report.
4. **Timeline constraint:** With code finalisation past and report due end of March, GT construction for 37 records is not viable.

**New status:** `SET_ASIDE_MAJOR_GT` --- GT completely empty, requires full construction (not correction). Added to PMCID Master Tracker and Action Register status definitions.

**Outcome:**

| Category | Count |
|----------|-------|
| SET\_ASIDE\_MAJOR\_GT | 37 |
| EXCLUDED | 4 |
| SET\_ASIDE\_SUPP | 3 |
| User-included (PENDING\_GT\_POPULATION) | 2 |
| User-included (ACTIVE, no\_isolates) | 2 |
| ACTIVE (no\_isolates) | 1 |
| **Total classified** | **49** |

**Final corpus status (all 242 records, zero UNDIAGNOSED):**

| Pool | Count |
|------|-------|
| Evaluable now (ACTIVE + CONVERTER\_FIX + MANUAL\_FIX) | 129 |
| Evaluable after GT work (PENDING\_GT\_POP + PENDING\_REVIEW) | 13 |
| Total potentially evaluable | 142 |
| Excluded (all SET\_ASIDE\_* + EXCLUDED) | 58 |
| Supplementary holdout | 42 |

---

# Design Decision: DD-2026-012 - Experiment Execution Strategy and Baseline Comparison

**Decision ID:** DD-2026-012  
**Date:** 18 March 2026  
**Context:** With all 242 records classified, GT fixes in progress across all three sets (golden, new 89, prefix 90), and the evaluation framework being updated (serotype prefix stripping, AST flattening, AMR gene normalisation), a clear experimental sequence is needed to produce the three-point comparison for the report: pre-fix scores, post-fix baseline, and GEPA-optimised result.

**Decision:** Skip any intermediate v3 re-run on fixed prefix 90 records. Instead, run a single clean v4 baseline on all ~129 evaluable records using corrected GT and the updated evaluation framework. This v4 run becomes the definitive pre-GEPA baseline.

**Rationale:**

1. The v2/v3 diagnostic scores already document the pre-fix state across all three sets (golden, new 89, prefix 90). Re-running the prefix 90 with corrected GT but the old evaluation framework adds a data point on a curve already characterised --- it does not tell us anything new.
2. GEPA optimisation will use the updated evaluation framework internally (field-specific comparators for serotype, MLST, AST, AMR). The baseline must use the identical framework; otherwise the pre/post comparison is invalid.
3. Running v4 on the full corpus (not just holdout) ensures consistency: GEPA training uses the same scoring, GEPA validation uses the same scoring, and the holdout comparison uses the same scoring.
4. The full-corpus v4 results provide per-record breakdowns for the report --- showing which issue categories improved most from the evaluation framework update and what the realistic ceiling looks like before optimisation.

**Execution sequence:**

1. Apply GT fixes to prefix 90 evaluable records (in progress)
2. Finalise evaluation framework updates (serotype prefix, AST flattening, AMR normalisation)
3. Run v4 unoptimised CoT on all ~129 evaluable records --- clean baseline
4. Run GEPA optimisation using training pool + validation set (100% training first, then 30%)
5. Run GEPA-optimised inference on holdout
6. Compare: v4 holdout baseline vs GEPA holdout (RQ1); 100% vs 30% training (RQ2)

**Report narrative (three-point comparison):**

| Stage | What it shows | Source |
|-------|--------------|--------|
| Pre-fix (v2/v3 diagnostic) | Low F1 was an evaluation artefact, not model failure | Already exists |
| Post-fix + updated eval (v4) | True model capability with clean GT and fair evaluation | New single run on full corpus |
| Post-GEPA | GEPA improvement over true baseline | Holdout only |

**Pre-fix vs post-fix delta** is obtained by comparing existing v2/v3 scores against v4 scores for the same records. No separate re-run needed.

---

# Design Decision: DD-2026-013 - Holdout Supplementation Protocol

**Decision ID:** DD-2026-013  
**Date:** 18 March 2026  
**Context:** The golden test set yields n=22 evaluable records after set-asides. This is insufficient for confident F1 comparisons between the unoptimised baseline and GEPA-optimised result.

### Problem Statement

With per-record F1 standard deviation of approximately 0.25 (observed in v3 diagnostic), the 95% confidence interval on mean F1 at n=22 is:

$$CI = \pm \frac{1.96 \times \sigma}{\sqrt{n}} = \pm \frac{1.96 \times 0.25}{\sqrt{22}} \approx \pm 0.10$$

An improvement of less than 0.10 F1 points cannot be distinguished from sampling noise. Supplementing the holdout to n$\approx$32 narrows this to $\pm$0.087, while n$\approx$35 yields $\pm$0.083. For a Design/Implementation capstone, this is an acceptable margin.

### Decision

Supplement the 22 golden holdout records with 8--13 high-quality non-golden records selected using model-independent criteria. Target holdout of 30--35 records.

### Selection Criteria (Model-Independent)

All three criteria must be met. They are properties of the GT annotation and article content, not of any model output.

**Criterion 1: GT-to-article alignment.**  
All GT isolate IDs must be confirmed present in the article XML text. Operationally: the `IDs_in_Text` metric (from the v3 diagnostic) must be 100%, or for NO\_ISOLATE\_ID records, GT must contain only `NO_ISOLATE_ID` as the identifier (which is trivially "in text" since it is a synthetic marker).

*Justification:* Records where GT IDs are absent from the article text are unreliable evaluation targets regardless of which model is used. A holdout record must have a GT that an article-only extraction pipeline could, in principle, reproduce.

**Criterion 2: GT substantiveness.**  
The GT must contain at least 2 distinct assay field types beyond `isolate_id` (e.g., serotype + AST, or MLST + AMR, or serotype + virulence\_genes).

*Justification:* Records with only a single assay field (e.g., serotype alone) do not exercise the extraction pipeline meaningfully. The holdout should test the model's ability to extract structured multi-field assay profiles, which is the core task.

**Criterion 3: Not a reclassified NO\_ISOLATE\_ID record.**  
Records that were reclassified from fabricated IDs (serovar names, antigenic formulae, MLST types) to `NO_ISOLATE_ID` during diagnostic remediation are excluded from holdout supplementation.

*Justification:* NO\_ISOLATE\_ID records have fundamentally different evaluation dynamics --- document-level matching rather than isolate-level matching. Including them alongside isolate-level records in the holdout conflates two evaluation regimes. These records remain valuable in the training pool where GEPA can learn from them.

### Tie-Breaking (If Eligible Pool > Required Supplement)

If more records meet all three criteria than are needed, select by TADP quartile stratification to match the difficulty distribution of the golden set. This ensures the supplementary records are not biased towards easy or hard articles.

### Constraints

- Supplementary holdout records must be removed from both training and validation pools before any GEPA run.
- The report must clearly identify which holdout records are golden (original) and which are supplementary, and present results both ways (golden-only and full holdout) for transparency.

### Selection Results (18 March 2026)

**Eligible pool:** 107 non-golden evaluable records screened. 19 excluded by C3 (NO\_ISOLATE\_ID). 6 failed C1 (< 100% IDs in text). 31 lack IDs\_in\_text data (need confirmation against GT files). 51 passed C1. Of those 51, C2 was confirmed for 18 (8 New 89 with GT\_iso $\geq$ 2 and oF1 $\geq$ 0.4; 10 prefix 90 with known assay types). 3 prefix 90 records failed C2 (single assay type only).

**Selected supplement (11 records):**

| PMCID | Source | Quartile | GT Isolates | oF1 | Assay Types | Selection Basis |
|-------|--------|----------|-------------|-----|-------------|----------------|
| PMC9146225 | New 89 | Q3 | 2 | 0.954 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC7478631 | New 89 | Q3 | 2 | 0.767 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC9148033 | New 89 | Q4 | 6 | 0.766 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC7748489 | New 89 | Q3 | 2 | 0.541 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC9323645 | New 89 | Q4 | 2 | 0.522 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC8913728 | New 89 | Q4 | 14 | 0.496 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC9610186 | New 89 | Q4 | 4 | 0.488 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC5145817 | New 89 | Q3 | 4 | 0.413 | $\geq$2 (confirmed by oF1) | Tier 1 |
| PMC8430385 | Prefix 90 | Q2 | 2 | -- | serotype, plasmid | Tier 3 (Q2 balance) |
| PMC9433600 | Prefix 90 | Q2 | 1 | -- | serotype, ast\_data | Tier 3 (Q2 balance) |
| PMC8969412 | Prefix 90 | Q4 | 2 | -- | amr, ast\_data, mlst, plasmid, serotype | Tier 3 (richest GT) |

**Tier explanation:**

- *Tier 1:* New 89 records with C1 = 100%, GT\_iso $\geq$ 2, oF1 $\geq$ 0.4. Multi-assay GT is near-certain when a record with 2+ isolates achieves oF1 > 0.4 --- this requires matching across multiple field types. All 8 eligible Tier 1 records selected.
- *Tier 3:* Prefix 90 records with C1 = 100% and C2 confirmed from Action Register (assay types verified against article content). 3 selected for quartile balance: 2 from Q2 (under-represented in golden set) and 1 with the richest GT (5 assay types). Prefix 90 oF1 values are not shown because the v3 diagnostic used pre-fix GT; these will be established by the v4 baseline run.

**Holdout quartile distribution:**

| Quartile | Golden | Supplement | Combined | % |
|----------|--------|-----------|----------|---|
| Q1 | 0 | 0 | 0 | 0% |
| Q2 | 4 | 2 | 6 | 18% |
| Q3 | 7 | 4 | 11 | 33% |
| Q4 | 9 | 5 | 14 | 42% |
| Unassigned | 2 | 0 | 2 | 6% |
| **Total** | **22** | **11** | **33** | |

**Confidence interval improvement:**

$$n=22: CI = \pm 0.104 \quad \longrightarrow \quad n=33: CI = \pm 0.085$$

**Remaining pool after holdout:**

| Pool | Records |
|------|---------|
| Holdout | 33 |
| Available for training + validation | 96 |
| Suggested validation | ~18 |
| Training (100%) | ~78 |
| Training (30%) | ~23 |

**Optional expansion:** 31 records with unknown IDs\_in\_text data remain. If IDs\_in\_text is confirmed during v4 baseline processing, up to 3 additional records may be added. Priority candidates: PMC6986767 (oF1=0.919, Q4, `acceptable`), PMC6430326 (oF1=0.745, Q4, `acceptable`), PMC9670943 (oF1=0.571, Q4, `acceptable`). These 3 are classified as `acceptable` in the diagnostic --- the highest GT quality tier.

---

# Design Decision: DD-2026-014 - GEPA Training Split Strategy

**Decision ID:** DD-2026-014  
**Date:** 18 March 2026  
**Context:** The original plan (DD-2026-003) specified training-size experiments at 10%, 20%, 30%, and 100% of the training pool to assess how much ground truth is needed for effective GEPA optimisation (sub-goal 2). With 2 weeks remaining for experiments, the full four-point analysis carries timeline risk.

**Decision:** Run 100% training first, then 30%. Add 10% only if time permits.

**Rationale:**

1. The 100% run answers the primary research goal (can GEPA improve extraction?) and provides the best-case GEPA result.
2. A single additional run at 30% gives a concrete two-point answer to the training-size question. If 30% performs close to 100%, GEPA is data-efficient. If there is a substantial drop, the training pool size matters --- either finding is informative.
3. The 30% run is faster than 100% (smaller training pool = fewer GEPA iterations), so the marginal time cost is manageable.
4. Cost is not a binding constraint (budget capped at 500 SGD, well within range for 2--3 GEPA runs on Bedrock).
5. In the report, frame as: "We investigated two training pool sizes (30% and 100%) to assess data efficiency. A full learning curve across additional splits is identified as future work."

**Approximate pool sizes (per DD-2026-013 holdout selection):**

| Pool | 100% Training | 30% Training |
|------|--------------|-------------|
| Holdout | 33 | 33 |
| Validation | ~18 | ~18 |
| Training | ~78 | ~23 |

---

# Design Decision: DD-2026-015 - v4 Modular Codebase Architecture and Evaluation Framework

**Decision ID:** DD-2026-015  
**Date:** 23 March 2026  
**Context:** The v3 diagnostic notebook was a monolithic Colab notebook combining extraction, evaluation, diagnostic classification, and reporting in a single file. Moving to v4 requires: (a) migrating from Colab to VSCode/local execution, (b) implementing the updated evaluation framework (serotype prefix stripping, AST flattening, AMR normalisation, case-insensitive field matching), (c) adding SFA's 3-category output structure (IWL/IWOL/NIOAI), and (d) ensuring the evaluation logic is importable by GEPA during optimisation.

**Decision:** Restructure the v4 codebase into a modular Python package under `C:\projects\pax-ai\src\` with three packages (`extract/`, `evaluate/`, `optimise/`) plus a top-level runner script.

**Note:** The `optimise/` package was originally named `gepa/` but was renamed to avoid a namespace collision with DSPy's bundled `gepa` package (DSPy internally does `from gepa import GEPAResult`, which resolves to the local directory instead of the installed package when `src/` is on `sys.path`).

**Rationale:**

1. **GEPA compatibility is the forcing function.** GEPA requires a metric function with the signature `metric(example, prediction) -> float`. This function must be importable as a clean Python callable. If extraction and evaluation logic remain in a monolithic script, GEPA cannot import just the metric without executing the entire pipeline. Separating `evaluate/metric.py` as a thin wrapper around `evaluate/scorer.py` gives GEPA exactly the interface it needs.
2. **Identical evaluation across all runs.** The v4 baseline, GEPA optimisation (internal scoring), and holdout evaluation must use the same evaluation logic. A shared `evaluate/` package guarantees this. Copy-pasting evaluation code into separate scripts creates divergence risk --- and the entire thesis narrative (three-point comparison) depends on scoring consistency.
3. **Diagnostic logic is dropped.** The v3 diagnostic classification functions (`classify_issue`, `detect_id_pattern`, `DocumentDiagnostic` dataclass) served GT quality triage and are not needed for v4 extraction evaluation. Carrying them forward adds maintenance cost with no benefit. The v3 notebook remains as a historical artefact.
4. **UP metric is dropped.** The "Unmatched but Present in text" metric was a diagnostic artefact for identifying GT gaps. For v4 evaluation onwards, standard TP/FP/FN/F1 metrics are used.
5. **3-category output schema.** The DSPy signature now instructs the LLM to classify each article into one of three SFA categories (IWL, IWOL, NIOAI) and output structured JSON with all three sections present (populated section + empty placeholders with correct types: `{}` for dicts, `[]` for lists). This mirrors the GT structure and enables per-category F1 scoring.

**Codebase structure:**

```
C:\projects\pax-ai\
  src\
    config.py                    # Existing singleton (no changes)
    run_baseline.py              # v4 entry point: CLI args, orchestrates extract+evaluate
    run_holdout_eval.py          # Future: post-GEPA holdout evaluation

    extract\
      __init__.py
      signatures.py              # AssayExtractionSignature (v4, 3-category output)
      extractor.py               # AssayExtractor DSPy module + JSON parsing
      article_loader.py          # XML text extraction, GT loading, PMCID list parsing

    evaluate\
      __init__.py
      normalise.py               # Field/value normalisation (updated framework), GT flattening
      scorer.py                  # Category-specific scoring (IWL/IWOL/NIOAI), RecordResult
      metric.py                  # GEPA-compatible metric wrapper
      report.py                  # CSV, JSON, console output generation

    optimise\
      __init__.py                # Placeholder for GEPA optimisation code
```

**Key changes from v3:**

| Component | v3 State | v4 State | Reason |
|-----------|----------|----------|--------|
| Signature output | Flat `{isolate_id: {assay: value}}` | 3-category JSON with `category` field | SFA requirement; per-category evaluation |
| Field normalisation | Single generic function | Field-specific dispatchers (serotype, MLST, AST, AMR) | Updated evaluation framework (Action Register 2.1) |
| Scoring | Single `compare_and_score` with UP metric | Three functions: `score_iwl`, `score_iwol`, `score_nioai` | Per-category F1; UP dropped |
| Diagnostic | `classify_issue`, `detect_id_pattern`, `DocumentDiagnostic` | Dropped | Diagnostic-only; not needed for evaluation |
| Execution | Colab notebook with `RUN_PHASE_A`/`RUN_PHASE_B` flags | CLI script with `--pmcid-list`, `--model`, `--dry-run` | VSCode/local execution |
| Output | `diagnostic_results.json`, `gt_diagnostic_summary.csv` | `v4_per_record_results.csv`, `v4_category_summary.json`, `v4_results.json` | Clean evaluation outputs |

**Output location:** `G:\My Drive\AI6129\assay\gt_diagnostic_analysis\v4_baseline\` (consistent with v1--v3 output hierarchy).

**Data flow:**

```
run_baseline.py
  --> FOR each PMCID:
        article_loader.load_article_text()   --> article_text
        article_loader.load_ground_truth()   --> gt_dict
        extractor.extract(article_text)      --> ext_dict (3-category)
        scorer.score_record(gt_dict, ext_dict) --> RecordResult
  --> report.generate_report(all_results)
```

**GEPA integration (future):**

```
optimise/run_gepa.py
  --> IMPORTS evaluate.metric.assay_metric   (calls scorer internally)
  --> IMPORTS extract.signatures             (signature to optimise)
  --> IMPORTS extract.extractor              (module to run)
  --> GEPA optimises signature prompt
```

**Alternatives considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Keep monolithic notebook, adapt for VSCode | Minimal refactoring | GEPA cannot import metric; evaluation divergence risk | Rejected |
| Four packages (extract, evaluate, diag, gepa) | Preserves diagnostic capability | diag/ adds maintenance cost with no v4 benefit | Rejected (diag/ dropped) |
| Two packages (pipeline, evaluate) | Simpler structure | Conflates extraction and GEPA concerns | Rejected |
| Selected: three packages (extract, evaluate, gepa) | Clean separation; GEPA imports evaluate.metric; ~625 lines total | Slightly more files than monolithic | Selected |

---

# Design Decision: DD-2026-016 - Supplementary / Multimodal Extraction Module

**Decision ID:** DD-2026-016  
**Date:** 24 March 2026  
**Context:** The 42 supplementary set-aside records contain assay data in supplementary files (Excel spreadsheets, PDFs, Word documents) and article figures rather than in the XML article body. Article-only extraction produces zero recall on these records. Demonstrating multimodal extraction capability is a stated project goal (DD-2026-001) and provides a baseline for future GEPA optimisation of the supplementary pathway.

**Decision:** Add supplementary extraction capability within the existing `extract/` package using the `attachments` library for multimodal file processing. The LLM receives both article text and supplementary content as inputs. Evaluation reuses the identical `evaluate/` pipeline without modification.

**Rationale:**

1. **Same output format:** The supplementary extractor produces the same 3-category JSON (IWL/IWOL/NIOAI) as the article extractor. No evaluation changes needed.
2. **Same DSPy pattern:** Uses ChainOfThought with a new signature that has two input fields (`article_text` + `supplementary_content`) instead of one. This is a signature variant, not a separate subsystem.
3. **Separate evaluation:** Supplementary records are evaluated independently from article-only records, providing a distinct multimodal baseline in the report.
4. **`attachments` library integration:** File content is converted to text via `str(Attachments(...))`, which handles Excel tables, PDF text, DOCX content, and image descriptions natively. The text representation is passed as a string input field to the DSPy signature.

**New / modified files:**

| File | Action | Purpose |
|------|--------|---------|
| `extract/supp_loader.py` | New | Discover supp/attachment files per PMCID; load via `attachments` library |
| `extract/signatures.py` | Modified | Added `SupplementaryAssayExtractionSignature` (two input fields) |
| `extract/extractor.py` | Modified | Added `SupplementaryAssayExtractor` DSPy module |
| `run_supp_baseline.py` | New | CLI entry point for supplementary extraction runs |
| `evaluate/*` | Unchanged | Identical scorer, metric, and report modules reused |

**Data flow:**

```
run_supp_baseline.py
  --> FOR each PMCID:
        article_loader.load_article_text()    --> article_text
        supp_loader.discover_supp_files()     --> [file_paths]
        supp_loader.load_attachments(paths)   --> Attachments object
        str(attachments_obj)                  --> supplementary_content (text)
        extractor.extract(article_text,
                          supplementary_content) --> ext_dict (3-category)
        article_loader.load_ground_truth()    --> gt_dict (from supp GT dir)
        scorer.score_record(gt_dict, ext_dict) --> RecordResult
  --> report.generate_report(all_results)
```

**GT and file locations:**

| Resource | Non-golden path | Golden path |
|----------|----------------|-------------|
| Supp GT | `ground_truth/supp/` | `ground_truth/golden/supp/` |
| Supp files | `supplementary/PMC{id}/` | Same |
| Figure images | `attachments/PMC{id}/` | Same |
| XML articles | `xml/` | `xml/golden/` |

**Output location:** `G:\My Drive\AI6129\assay\gt_diagnostic_analysis\v4_supp_baseline\`

**Scope:** Initially the 42 supplementary set-aside records, potentially expanded with enriched set-aside-major-gt records. This is a separate evaluation from the article-only v4 baseline, reported independently in the thesis to demonstrate multimodal extraction capability.

**Dependencies:** `pip install attachments[office]` (for xlsx/docx support)

---

# Design Decision: DD-2026-018 - GEPA Main Run Design

**Decision ID:** DD-2026-018  
**Date:** 28 March 2026  
**Context:** With the v4 baseline complete (mean F1 = 0.364 on Haiku; Sonnet baseline in progress), the GEPA optimisation run is the next step. This DD documents the dataset splits, GEPA configuration, feedback metric design, and cost estimation for the productive GEPA runs. Supersedes the earlier pilot design (DD-2026-003/DD-2026-004) with updated record counts (149 evaluable, post-v4 GT corrections) and refined parameters.

## 1. Dataset Splits

**Total evaluable records:** 149 (110 IWL, 37 NIOAI, 1 IWOL, 1 IWL+IWOL)

### 1.1 Holdout Test Set (31 records)

Composed of the golden GT (20 IWL) plus supplements selected per DD-2026-013 (10 IWL + 1 NIOAI).

| Sub-pool | Count | Categories |
|----------|-------|------------|
| Golden | 20 | 20 IWL |
| Supplement (DD-2026-013) | 11 | 10 IWL + 1 NIOAI |
| **Holdout total** | **31** | **30 IWL + 1 NIOAI** |

IWOL is not represented in the holdout. The corpus contains only 1 pure IWOL and 1 hybrid record --- neither provides a statistically meaningful holdout sample. IWOL evaluation is reported qualitatively as a stated limitation.

### 1.2 Validation Set (18 records)

Selected from the 117 training-evaluable pool plus 1 restored record (PMC7083327, formerly set-aside, now NIOAI). Selection criteria: span the v3 oF1 difficulty range, vary isolate counts, include multiple diagnostic categories, and avoid records documented in v4 diagnostic troubleshoot notes (those stay in training for GEPA to learn from).

**IWL (12 records) --- 2 per oF1 bin:**

| Bin | PMCID | v3 oF1 | Isolates | Diagnostic |
|-----|-------|--------|----------|------------|
| B1 (0.00--0.20) | PMC9409446 | 0.000 | 1 | honest\_failure |
| B1 | PMC9137667 | 0.077 | 2 | id\_is\_mlst |
| B2 (0.20--0.35) | PMC9353134 | 0.242 | 21 | eval\_normalisation |
| B2 | PMC4866840 | 0.316 | 2 | eval\_normalisation |
| B3 (0.35--0.50) | PMC8698551 | 0.439 | 8 | eval\_normalisation |
| B3 | PMC9035464 | 0.471 | 1 | eval\_normalisation |
| B4 (0.50--0.65) | PMC8784875 | 0.533 | 11 | eval\_normalisation |
| B4 | PMC6307136 | 0.649 | 5 | eval\_normalisation |
| B5 (0.65--0.80) | PMC9216381 | 0.696 | 3 | eval\_normalisation |
| B5 | PMC6430326 | 0.745 | 4 | acceptable |
| B6 (0.80+) | PMC7581672 | 0.846 | 0 | over\_extraction |
| B6 | PMC6986767 | 0.919 | 7 | acceptable |

**NIOAI (5 records):**

| PMCID | v3 oF1 | Diagnostic |
|-------|--------|------------|
| PMC7460271 | 0.000 | eval\_normalisation |
| PMC4939201 | 0.200 | id\_is\_serotype |
| PMC5832104 | 0.364 | eval\_normalisation |
| PMC6925778 | 0.444 | eval\_normalisation |
| PMC8947133 | 0.799 | no\_isolates\_only\_assayinformation |

**IWL+IWOL hybrid (1 record):**

| PMCID | v3 oF1 | Rationale |
|-------|--------|-----------|
| PMC8512087 | 0.667 | Only hybrid record; GT corrected during v4 diagnostics; exercises IWOL classification pathway |

### 1.3 Training Pool

| Experiment | Training | Validation | Holdout | Train:Val Ratio |
|------------|----------|------------|---------|-----------------|
| 100% | 100 | 18 | 31 | 5.6:1 |
| 30% | ~30 | 18 | 31 | 1.7:1 |

Training category breakdown (100%): 68 IWL, 31 NIOAI, 1 IWOL.

### 1.4 oF1 Caveat

The oF1 values used for bin stratification are from the v3 diagnostic (pre-fix GT, pre-fix evaluation framework). After v4 scores are available for all records, a sanity check should confirm the 18 validation records still span the difficulty range. If a large cluster collapsed into the same v4 score band, one record may be swapped.

## 2. GEPA Configuration

**Platform:** Anthropic API (not AWS Bedrock). Bedrock is reserved for the Nova Pro compliance demonstration per the model comparison plan.

**Model selection (depends on v4 baseline results):**

| Role | Most likely model | Rationale |
|------|------------------|-----------|
| Student (extraction) | Claude Sonnet 4 | Higher v4 baseline expected; production-grade |
| Reflection LM | Claude Opus | Highest capability for prompt evolution |

The student model is whichever of Haiku/Sonnet scores higher on the v4 baseline. The reflection model is the next tier up.

**GEPA parameters:**

```
optimizer = dspy.GEPA(
    metric                    = gepa_feedback_metric,
    max_full_evals            = 60,             # productive; 5 for smoke test
    num_threads               = 4,              # conservative for API rate limits
    seed                      = 42,             # reproducibility
    track_stats               = True,           # detailed_results for report
    track_best_outputs        = True,           # best_outputs_valset for analysis
    log_dir                   = "gepa_logs/{experiment_id}",
    reflection_minibatch_size = 3,
    reflection_lm             = opus_lm,
    use_merge                 = True,           # combine complementary strategies
    failure_score             = 0.0,
    perfect_score             = 1.0
)
```

**Budget rationale:** `max_full_evals` chosen over `auto` for direct, predictable cost control. Each full eval = 18 validation extractions. Recommended values:

| Purpose | max\_full\_evals |
|---------|-----------------|
| Smoke test | 5 |
| Light test | 15 |
| Productive run | 60 |
| Extended (if budget allows) | 100 |

## 3. Feedback Metric Design

**Approach:** Two-tier rule-based feedback with XML cross-reference. No LLM judge.

**Tier 1 --- GT comparison (existing evaluation framework):**
Per-field F1 decomposition (serotype, MLST, AST, AMR, virulence\_genes, plasmid), category mismatch detection, missing/extra item enumeration.

**Tier 2 --- XML cross-reference (new):**
Cross-references the article XML structure against the extraction output to diagnose *why* something was missed, not just *what* was missed. Five specific detectors:

| Detector | Trigger | Feedback produced |
|----------|---------|-------------------|
| Table extraction gap | GT isolate codes missing from extraction but present in XML `<table>` elements | "Isolate codes X, Y appear in article tables but were not extracted" |
| Linking failure | Extraction has isolates in IWOL and assay data in NIOAI, but GT expects IWL | "Model extracted both isolate codes and assay data but did not link them per-isolate" |
| Antigenic formula | GT serotype matches antigenic formula pattern (digits, colons, dashes) and extraction missed it | "Antigenic formula notation (e.g., 4,5,12:i:-) IS a serotype value" |
| Population-level scope | Extraction contains percentages or proportions in per-isolate fields | "Extracted population-level statistics instead of per-isolate data" |
| Extraneous fields | Extraction contains fields outside target schema | "Fields like clade, conjugation\_efficiency are not part of the target schema" |

**Return format:** `dspy.Prediction(score=overall_f1, feedback=concatenated_feedback_text)`

**Rationale for no LLM judge:** The evaluation framework already identifies the exact failure modes. Adding an LLM judge approximately doubles cost per GEPA iteration and introduces non-determinism. If, after inspecting the first productive run's optimised prompts, the rule-based feedback proves insufficient for specific failure patterns, a targeted LLM judge can be added for the 30% run.

## 4. Cost Estimation (Anthropic API)

Assumes Sonnet 4 as student, Opus as reflection.

| Component | Input tokens | Output tokens | Input rate (USD/MTok) | Output rate (USD/MTok) | Per-call cost |
|-----------|-------------|---------------|----------------------|------------------------|---------------|
| Extraction (Sonnet) | ~12,000 | ~2,000 | \$3.00 | \$15.00 | ~\$0.066 |
| Reflection (Opus) | ~8,000 | ~3,000 | \$15.00 | \$75.00 | ~\$0.345 |

| max\_full\_evals | Est. USD | Est. SGD |
|-----------------|----------|----------|
| 5 (smoke test) | ~\$9 | ~\$12 |
| 15 (light) | ~\$26 | ~\$35 |
| 60 (productive) | ~\$104 | ~\$140 |
| 100 (extended) | ~\$173 | ~\$234 |

**Both productive runs (100% + 30% at max\_full\_evals=60):** ~\$208 USD / ~\$280 SGD. Well within the 500 SGD budget cap.

## 5. Execution Sequence

1. Confirm v4 Sonnet baseline results → select student model
2. Generate validation and training split files from master tracker
3. Smoke test (max\_full\_evals=5) → verify pipeline, feedback format, log output
4. Productive run: 100% training, max\_full\_evals=60
5. Save optimised programme + detailed\_results
6. Productive run: 30% training, max\_full\_evals=60
7. Run GEPA-optimised inference on holdout (both 100% and 30% programmes)
8. Compare: v4 holdout baseline vs GEPA holdout (RQ1); 100% vs 30% training (RQ2)
9. Statistical evaluation: Wilcoxon signed-rank, bootstrap CI, McNemar's (category), per-field breakdown

## 6. Statistical Evaluation Plan

Supersedes the original McNemar's-only plan from the November 2025 experimental design. The primary outcome variable is now continuous per-record F1 (not binary exact-match), requiring different statistical tests.

### 6.1 Primary Test: Wilcoxon Signed-Rank

Non-parametric paired test for continuous outcomes. Tests whether the median per-record F1 difference between two conditions is significantly different from zero. Chosen over paired t-test because F1 distributions are bounded [0, 1] and typically skewed; Wilcoxon makes no normality assumption. A paired t-test is reported alongside as a sensitivity check.

**Effect size:** Matched-pairs rank-biserial correlation ($r$):

$$r = \frac{W_{+} - W_{-}}{W_{+} + W_{-}}$$

where $W_{+}$ is the sum of positive ranks and $W_{-}$ the sum of negative ranks. Interpretation: small ($r$ < 0.3), medium (0.3--0.5), large (> 0.5).

### 6.2 Complementary: Bootstrap 95% Confidence Interval

Non-parametric CI on the mean F1 difference ($\Delta$F1). More informative than a p-value alone --- shows the magnitude of improvement with uncertainty bounds.

Procedure: compute per-record $d_i = F1_{GEPA}(i) - F1_{baseline}(i)$ for $i = 1..31$; resample $d$ with replacement $B = 10{,}000$ times; compute mean of each resample; take the 2.5th and 97.5th percentiles as the 95% CI.

### 6.3 Retained: McNemar's Exact Test (Category Classification)

McNemar's test is appropriate for the binary paired outcome "did the model classify this article into the correct category (IWL/IWOL/NIOAI)?" With $n = 31$, the exact version is used (not the chi-squared approximation) since the expected number of discordant pairs may be small.

### 6.4 Multiple Comparison Correction: Holm-Bonferroni

| Research Question | Comparisons | $n$ for correction |
|------------------|-------------|-------------------|
| RQ1 + RQ2 | Baseline vs GEPA-100%, GEPA-100% vs GEPA-30% | 2 |
| RQ3 | Haiku vs Sonnet, Haiku vs Nova, Sonnet vs Nova | 3 |

For $n = 2$ at $\alpha = 0.05$: first (smallest) p-value compared to 0.025, second to 0.05. For $n = 3$: compared to 0.0167, 0.025, 0.05 sequentially.

### 6.5 Planned Comparisons Summary

| Comparison | Test | Outcome Variable | Effect Size | CI |
|------------|------|------------------|-------------|-----|
| Baseline vs GEPA-100% (RQ1) | Wilcoxon signed-rank | Per-record F1 | Rank-biserial $r$ | Bootstrap 95% on $\Delta$F1 |
| GEPA-100% vs GEPA-30% (RQ2) | Wilcoxon signed-rank | Per-record F1 | Rank-biserial $r$ | Bootstrap 95% on $\Delta$F1 |
| Model comparisons (RQ3) | Wilcoxon signed-rank (pairwise) | Per-record F1 | Rank-biserial $r$ | Bootstrap 95% per pair |
| Category accuracy (all RQs) | McNemar's exact | Binary correct/incorrect | Odds ratio | Report contingency table |

### 6.6 Descriptive Statistics (No Hypothesis Test)

- Per-field F1 breakdown: serotype, MLST, AST, AMR, virulence\_genes, plasmid --- baseline vs GEPA
- F1 distribution summaries: mean, median, IQR, min, max per condition
- Per-category (IWL vs NIOAI) F1 breakdown

## 7. GEPA Outputs for Reporting

With `track_stats=True` and `track_best_outputs=True`, GEPA produces the following data beyond the holdout inference results:

### 7.1 From `detailed_results` (DspyGEPAResult)

| Attribute | Content | Report Use |
|-----------|---------|------------|
| `val_aggregate_scores` | Aggregate validation score per Pareto candidate | Convergence curve: score vs iteration |
| `highest_score_achieved_per_val_task` | Best F1 per validation record across all candidates | Per-record ceiling analysis |
| `best_outputs_valset` | Best extraction output per validation record | Qualitative error analysis |
| Per-iteration individual valset scores | Per-record scores at each iteration | Heatmap: records $\times$ iterations |

### 7.2 From `log_dir`

| Content | Report Use |
|---------|------------|
| All candidate programmes (JSON) | Prompt evolution: initial vs intermediate vs final |
| Per-iteration reflection traces | Qualitative: what did GEPA diagnose and propose? |
| Pareto frontier membership per iteration | Frontier size plot over iterations |
| Checkpoint files | Operational (resume); not for reporting |

### 7.3 From the Optimised Programme

| Output | Access | Report Use |
|--------|--------|------------|
| Evolved prompt text | `optimised_program.predictors()[0].signature.instructions` | Key exhibit: show domain-specific instructions GEPA added |
| Saved programme | `optimised_program.save("path.json")` | Reproducibility archive |

### 7.4 Planned Visualisations

**From GEPA optimisation process:**

1. **Score convergence curve:** validation aggregate score vs iteration/metric calls. Shows convergence, plateau, or continued improvement.
2. **Pareto frontier size over iterations:** number of non-dominated candidates vs iteration. Growing = finding complementary strategies; stable = refining.
3. **Per-validation-record improvement heatmap:** 18 records $\times$ iterations, coloured by F1.

**From holdout inference:**

4. **Paired F1 scatter plot:** baseline F1 (x) vs GEPA F1 (y) per holdout record. Points above diagonal = improved.
5. **Per-field F1 grouped bar chart:** serotype, MLST, AST, AMR, virulence\_genes, plasmid --- baseline vs GEPA.
6. **Category confusion matrices (before/after):** 3$\times$3 predicted vs GT, for baseline and GEPA.
7. **F1 distribution box/violin plot:** side-by-side for baseline, GEPA-100%, GEPA-30%.

## 8. Alternatives Considered

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| `auto` budget | Simple | Opaque cost; no direct control | Rejected in favour of `max_full_evals` |
| LLM-as-judge feedback | Richer diagnosis for subtle errors | ~2x cost, non-deterministic, unnecessary for structured GT comparison | Rejected for initial run; reconsider if needed |
| Larger validation set (35) | Better Pareto tracking | Higher compute per iteration; depletes training pool | Rejected; 18 sufficient with stratification |
| IWOL in holdout | Category coverage | Only 1 record; not statistically meaningful; removes GEPA training example | Rejected; noted as limitation |

---

# Design Decision: DD-2026-019 - Loose (Containment) F1 Metric

**Decision ID:** DD-2026-019  
**Date:** 29 March 2026  
**Context:** The v4 evaluation framework uses exact match after normalisation. This penalises LLM extractions that correctly identify an entity but include additional context (e.g. "Dysenteriae serotype 1" vs GT "dysenteriae 1", or "pSD1\_197 (182,726 bp); contains TTSS..." vs GT "pSD1\_197"). These are formatting mismatches, not content errors. Supervising professor and research fellow identified this as an over-penalisation that conflates two distinct failure modes: wrong entity vs correct entity with verbose format.

**Decision:** Add a supplementary "loose F1" metric alongside the existing strict F1. The loose metric uses token-level containment matching as a second pass on strict false positives and false negatives. Both metrics are always reported together; the strict F1 remains primary.

## 1. Matching Rule

After normalisation, if all tokens of the shorter normalised value appear in the token set of the longer normalised value, treat the pair as a match.

Token-level (not character substring) to prevent false matches: "st1" does not match "st10" because the token sets are disjoint.

**Examples:**

| GT normalised | Extraction normalised | Token check | Match? |
|---------------|----------------------|-------------|--------|
| dysenteriae 1 | dysenteriae serotype 1 | \{dysenteriae, 1\} $\subseteq$ \{dysenteriae, serotype, 1\} | Yes |
| psd1197 | psd1197 (182726 bp) contains ttss... | \{psd1197\} $\subseteq$ \{psd1197, (182726, bp), ...\} | Yes |
| st1 | st10 | \{st1\} $\not\subseteq$ \{st10\} | No |
| typhimurium | enteritidis | \{typhimurium\} $\not\subseteq$ \{enteritidis\} | No |

## 2. Implementation

Changes are localised to `evaluate/scorer.py` and `optimise/feedback_metric.py`.

**In `scorer.py`:**

1. Add `_is_loose_match(gt_norm, ext_norm)` function (~15 lines).
2. In `_score_iwl()` and `_score_nioai()`: after strict matching, run a second pass on unmatched FP/FN pairs. If a strict FP loose-matches a strict FN on the same field, reclassify both as a loose TP.
3. Add `loose_tp`, `loose_fp`, `loose_fn`, `loose_f1` fields to `RecordResult`.

**In `feedback_metric.py`:**

Add a FORMAT NOTE feedback when loose\_tp > strict\_tp, informing GEPA that the entity was found but the format was verbose.

## 3. Reporting

| Metric | Definition | Role |
|--------|-----------|------|
| Strict F1 | Exact match after normalisation | Primary metric; comparability |
| Loose F1 | Strict + containment recovery | Supplementary; entity-level correctness |
| $\Delta$ (Loose $-$ Strict) | Formatting tax | Quantifies recoverable gap |

Both are reported in all evaluation outputs. The strict F1 is used as the GEPA optimisation score. The loose F1 is informational.

## 4. Alternatives Considered

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Character substring | Simple | False matches (ST1 in ST10) | Rejected |
| Edit distance threshold | Handles typos | Arbitrary threshold; expensive | Rejected |
| Token containment (selected) | Precise; fast; handles over-specification | Does not handle rewordings | Selected |
| Replace strict F1 entirely | Simpler reporting | Loses comparability with v4 baseline | Rejected |

---


## Design Options & Decision Log

### Completed Decisions

| ID | Date | Decision | Rationale | Status |
|----|------|----------|-----------|--------|
| DD-001 | Sep 2025 | Use DSPy over manual prompting | Declarative programming, GEPA compatibility | Implemented |
| DD-002 | Oct 2025 | XML over PDF extraction | 94% vs 12% table accuracy, structured parsing | Implemented |
| DD-003 | Oct 2025 | E-utilities over AWS/FTP | 100% vs 0% coverage for target corpus | Implemented |
| DD-004 | Nov 2025 | Claude Haiku 3.5 as baseline | Cost-effective, parameter control, SFA approved | Implemented |
| DD-005 | Nov 2025 | Range expansion for accessions | MH548440Ã¢â‚¬â€œMH548519 = 80 accessions, not 2 | Implemented |
| DD-006 | Dec 2025 | Supplementary file download | Critical assay data in supp materials | Implemented |
| DD-2026-001 | Jan 2026 | Multimodal extraction | Figure-embedded accessions/assays | Approved |
| DD-2026-002 | Jan 2026 | Unified assay signature | Cross-pathogen (bacterial + viral) support | Approved |
| DD-2026-003 | Jan 2026 | gepa-optimised data stratification | Fixed validation set | Approved |
| DD-2026-003 | Jan 2026 | gepa Stage 0 Pilot Implementation | Decision on how to run Stage 0 | Approved |
| DD-2026-007 | Mar 2026 | Golden GT diagnostic and remediation | 45 golden records assessed; 5 structural problems identified; 13 set aside | In Progress |
| DD-2026-008 | Mar 2026 | New 89 diagnostic and metadata stripping | 89 records assessed; 12 excluded, 77 evaluable. Metadata fields stripped, Unicode normalised, 8 MANUAL\_FIX applied | Complete |
| DD-2026-009 | Mar 2026 | GEPA split strategy | Full golden GT as holdout test, 15--20 curated non-golden as GEPA validation, remainder as training pool | Approved |
| DD-2026-010 | Mar 2026 | Prefix 90 diagnostic (Phase 1) | 41/90 records classified: 5 empty, 3 set-aside, 8 no\_isolates, 7 pending GT, 15 format mismatch, 2 pending review, 1 ID correction | Complete |
| DD-2026-011 | Mar 2026 | Prefix 90 remaining records (Phase 2) | 49/90 remaining classified: 37 SET\_ASIDE\_MAJOR\_GT (empty GT, requires construction), 4 excluded, 3 supp, 4 user-included, 1 active. Zero UNDIAGNOSED remain. | Complete |
| DD-2026-012 | Mar 2026 | Experiment execution strategy | Skip intermediate v3 re-run; single v4 baseline on all evaluable with corrected GT + updated eval framework. Three-point comparison: pre-fix → post-fix → post-GEPA. | Approved |
| DD-2026-013 | Mar 2026 | Holdout supplementation protocol | Supplement golden holdout (n=22) with 11 non-golden records. Selection: 100% IDs in text, $\geq$2 assay types, not NO\_ISOLATE\_ID. Final holdout n=33. CI narrowed from $\pm$0.104 to $\pm$0.085. | Complete |
| DD-2026-014 | Mar 2026 | GEPA training split strategy | Run 100% training first, then 30%. Two-point answer to training-size question. 10% only if time permits. | Approved |
| DD-2026-015 | Mar 2026 | v4 modular codebase architecture | Modular Python package: extract/, evaluate/, optimise/. 3-category output (IWL/IWOL/NIOAI), updated eval framework (field-specific normalisers), GEPA-compatible metric. Diagnostic logic and UP metric dropped. VSCode/local execution. Originally `gepa/`, renamed to `optimise/` to avoid namespace collision. | Approved |
| DD-2026-016 | Mar 2026 | Supplementary / multimodal extraction | Added SupplementaryAssayExtractionSignature (article + supp content). Uses attachments library for xlsx/pdf/docx/image processing. Same 3-category output; same evaluation pipeline. Targets 42+ supp set-aside records. | Approved |
| DD-2026-017 | Mar 2026 | v4 baseline IWOL diagnostic and reclassification | 3/4 IWOL records at F1=0.0 investigated. PMC8947133: IWOL$\rightarrow$NIOAI (SRR accessions are not isolate IDs). PMC4944992: SET\_ASIDE\_SUPP (isolate codes from supp PDF only). PMC9754226: EXCLUDED confirmed (cross-section mismatch). Three signature gaps identified: unconstrained output fields, placeholder values, missing CRISPR type. | Complete |
| DD-2026-018 | Mar 2026 | GEPA main run design | 149 records: 31 holdout, 18 validation (stratified), 100 training. Anthropic API (Sonnet student, Opus reflection). `max_full_evals=60`, `seed=42`, `track_stats=True`, `track_best_outputs=True`. Two-tier rule-based feedback. Statistical plan: Wilcoxon signed-rank + bootstrap CI (primary), McNemar's exact (category), Holm-Bonferroni correction. Est. cost \$280 SGD for both runs. | Approved |
| DD-2026-019 | Mar 2026 | Loose (containment) F1 metric | Token-level containment matching as supplementary metric alongside strict F1. Recovers correct-but-verbose extractions. Second pass on strict FP/FN pairs. Strict F1 remains primary and GEPA score. | Approved |

---

## Key Technical Insights

### 1. XML vs PDF for Biomedical Text Mining
- **Critical Finding:** XML provides 94% table extraction accuracy vs 12% for basic PDF tools
- **Reason:** Structured semantic markup (`<table>`, `<th>`, `<td>`) vs visual reconstruction
- **Impact:** Essential for reliable assay information extraction from tables

### 2. E-utilities Access Superiority
- **Critical Finding:** E-utilities accesses full PMC collection; AWS/FTP limited to OA subset
- **Reason:** Subscription journals deposited via NIH requirements not in OA subset
- **Impact:** 0% coverage with AWS/FTP for Hepatitis A test dataset

### 3. DSPy Framework Benefits
- **Declarative Signatures:** Separate logic from prompt engineering
- **GEPA Compatibility:** Enables automatic prompt optimisation
- **Reproducibility:** Consistent prompting across experiments
- Production-validated for information extraction tasks

### 4. Cross-Pathogen Transfer Learning
- Classification schemes focus on methodology, not pathogen specifics
- Enables leveraging existing labelled datasets
- Reduces ground truth data requirements

### 5. Computational Resource Strategy
- API-based models more efficient than local hosting for DSPy
- Proof-of-concept validation critical for institutional resource access
- Compliance requirements (AWS Bedrock Singapore) identified early

### 6. Ground Truth Focus
- High-level patterns more important than detailed assumptions
- Avoid unnecessary entity normalisation if not required
- Question assumptions to prevent scope creep

### 7. Multimodal Extraction Value (NEW)
- **Critical Finding:** Some accessions/assays exist ONLY in figures
- **Implication:** Text-only extraction may have lower recall than PDF for certain articles
- **Solution:** Parallel multimodal extraction using vision-capable models
- **Trade-off:** Higher cost but necessary for comprehensive extraction

### 8. Ground Truth Quality as Evaluation Ceiling (NEW - DD-2026-007)
- **Critical Finding:** Manually-labelled golden test set yielded F1=0.047, predominantly due to structural GT issues, not extraction failure
- **Root causes:** Accession fields in assay GT (23/45 records), supplementary-only data (13/45), Unicode encoding mismatches, incomplete field coverage
- **Implication:** GT quality is the evaluation ceiling; broken GT makes good extraction appear catastrophic
- **Lesson:** Always run GT diagnostic before evaluation experiments; distinguish evaluation artefact from model error
- **Output token limit:** High-isolate articles (128+ isolates) exceed `max_tokens=8192`, causing complete extraction failure via JSON truncation

### 9. v4 Evaluation Framework Bug -- IWL Type Mismatch (NEW - DD-2026-017)
- **Critical Finding:** v4 baseline reported mean F1 = 0.058 across 154 records, with 126/154 (81.8%) classified as EMPTY GT. Investigation revealed the evaluation framework's `flatten_by_category()` function expected `isolates_with_linking` as a dict keyed by isolate ID, but all GT files store it as a list of dicts each containing an `isolate_id` field. The `isinstance(iwl_raw, dict)` check silently skipped all list-format data, producing zero IWL items and cascading every IWL record to `category = EMPTY`.
- **Root cause:** Format assumption mismatch between normaliser code and GT JSON schema. NIOAI (dict) and IWOL (list of strings) branches worked correctly because their GT format matched the code's expectations.
- **Impact:** All E. coli golden records (8), all new89 ACTIVE records, all 25 reconstructed records, and every prefix 90 IWL record read as EMPTY. 99.5% of all false positives (7,542/7,578) originated from EMPTY GT records where the model correctly extracted data but had no GT to score against.
- **Fix:** Added list-of-dicts handling as primary branch with dict-keyed format as fallback. Added `VALID_ASSAY_FIELDS` guard and `_IWL_SKIP_KEYS` exclusion set. All regression tests passed.
- **Lesson:** Always validate evaluation framework output against known-good GT files before interpreting results. A single type-check bug can render an entire evaluation meaningless.

### 10. v4 Baseline IWOL Diagnostic -- Category and Scoring Gaps (NEW - DD-2026-017)
- **Critical Finding:** 3/4 IWOL records scored F1 = 0.0 despite competent extraction. Root causes were structural, not extraction failures:
  - **PMC8947133:** GT used 69 SRR accession numbers (database identifiers, not isolate codes) from supplementary Excel. Zero SRR strings in article XML. LLM correctly classified as NIOAI with rich extraction (24 serotypes, 33 AMR genes, 22 AST profiles). Reclassified IWOL $\rightarrow$ NIOAI.
  - **PMC4944992:** GT isolate codes (1CTxxx) exist only in supplementary PDF dendrogram figure labels. Reclassified to SET\_ASIDE\_SUPP.
  - **PMC9754226:** Model extracted all 11 GT IDs correctly (100% ID recall) but placed them in `isolates_with_linking` instead of `isolate_without_linking`. The IWOL scorer only compares the IWOL section, so cross-section overlap is invisible. Confirmed EXCLUDED.
- **Signature gaps identified:**
  1. **Unconstrained output field names:** The OutputField description does not restrict field names to the listed assay types. The model invented `"crispr"` as a field name. Fix: add explicit whitelist instruction to OutputField desc.
  2. **Placeholder values for absent data:** The model produced `"serotype": "unidentified"` instead of omitting the field or using `[]`. The signature says "use null for assays mentioned but with no value reported" but does not prohibit descriptive placeholders. Fix: add "omit field or use `[]` if not reported; never use placeholder values like unidentified, unknown, or not determined."
  3. **CRISPR not in assay catalogue:** CRISPR-based subtyping is a legitimate molecular method used in food safety surveillance but is not listed in the signature or `VALID_ASSAY_FIELDS`. Noted as future work; not actionable within project timeline.
- **Cross-section scoring limitation:** The current scorer does not attempt cross-section fallback matching (e.g., checking EXT IWL keys against GT IWOL IDs when categories differ). This is a design trade-off: adding fallback matching would help cases like PMC9754226 but could introduce false positives. Noted as future work.

### 11. GT Schema Limitation — NIOAI Population-Level Data Representation (NEW - 28 March 2026)
- **Finding:** The current GT schema assumes NIOAI data is **single-isolate-level**, mirroring IWL's structure (specific R/S/I per antibiotic, specific serovar, specific AMR genes) but without an isolate code. This works correctly for clinical case reports where one unnamed isolate has one definitive AST profile.
- **Limitation:** The schema cannot faithfully represent **population-level reporting**, which is common in epidemiological and surveillance studies. These articles report:
  - AST as **prevalence rates** (e.g., "84% resistant to ampicillin" across 87 isolates), not binary R/S/I per drug
  - AMR gene presence as **fractional** (e.g., $bla_{CTX-M-1}$ in 70/87 isolates)
  - Multiple coexisting resistance **patterns** within a population (e.g., 13 distinct MDR patterns in a single study)
  - PFGE profiles as **cluster distributions** (e.g., 35.6% with XbaI.0126 profile), not per-isolate assignments
- **Impact on evaluation:** The normaliser's `_normalise_ast()` function expects `drug:interpretation` pairs where interpretation is a single R/S/I value. Population-level values like `"R (84%)"` do not normalise cleanly to standard pairs. Neither the GT annotator nor the LLM can faithfully represent this data within the current schema, creating a lose-lose situation: either population data is forced into a per-isolate mould (losing fidelity) or it cannot be represented at all (losing coverage).
- **Discovered via:** PMC7696838 — a study of 87 S. Infantis isolates from Italian broiler meat production. Haiku faithfully extracted all 16 antibiotics with their population-level percentages from Table 1, but the GT had only 5 antibiotics forced into a single R/S profile under fabricated PFGE-pattern "isolate codes" (XbaI.0126, XbaI.2621, XbaI.0125). Both representations are inaccurate under the current schema. Record reclassified to SET\_ASIDE.
- **Recommended future work:** Extend the NIOAI schema with a `population_level` flag that permits:
  - Prevalence-based AST: `"ampicillin": {"R": 84, "I": 0, "S": 16}` (percentage per interpretation)
  - Fractional AMR: `"blaCTX-M-1": {"present": 70, "total": 87}`
  - Population metadata: `"n_isolates": 87`
  - This would enable a prevalence-aware scoring function that compares dominant interpretation or distribution overlap rather than exact R/S/I matching.
- **Report placement:** Chapter 5 (Methodology) — acknowledge as a GT schema design limitation discovered during the diagnostic-first phase. Chapter 7 (Discussion/Future Work) — recommend schema extension for population-level epidemiological studies.

---

## Current Status (March 2026)

### Completed Components
:heavy_check_mark: PubMed Article Downloader (v3.1) - fully functional with supplementary download  
:heavy_check_mark: PMID to PMCID conversion system  
:heavy_check_mark: Full-text XML extraction from PMC  
:heavy_check_mark: Supplementary file download (1,335 files for 227 articles)  
:heavy_check_mark: GenBank accession number extraction with DSPy  
:heavy_check_mark: Accession format reference documentation (200+ lines)  
:heavy_check_mark: Google Colab integration with built-in AI models  
:heavy_check_mark: Presentation delivered successfully  
:heavy_check_mark: Literature references compiled and maintained  
:heavy_check_mark: Cross-pathogen transfer learning validated  
:heavy_check_mark: Ground truth validation (227 documents, 2,681 accessions)  
:heavy_check_mark: Range expansion logic for accession extraction  
:heavy_check_mark: Multimodal extraction design approved  
:heavy_check_mark: Unified assay signature designed (bacterial + viral support)  
:heavy_check_mark: Golden GT diagnostic analysis (DD-2026-007) - 5 problem patterns identified  
:heavy_check_mark: Reconstituted 89-document working set (DD-2026-006) with 26 replacements  

### In Progress / Testing
:hammer: Golden GT remediation (converter fixes, manual corrections, set-aside)  
:hammer: New 89 diagnostic analysis (baseline before signature tweaks)  
:hammer: GEPA optimisation experiments (blocked on golden GT remediation)  
:hammer: DSPy classification pipeline optimisation  
:hammer: Multimodal extraction implementation (PMC7738724 test case)  
:hammer: Error type categorisation for iterative improvement  

### Pending / Future Work
:soon: Final experiments using AWS Bedrock Singapore  
:soon: Full pipeline integration testing  
:soon: Performance optimisation using GEPA  
:soon: Comprehensive validation on Hepatitis A and E datasets  
:soon: Institutional AWS access negotiation via Research Fellow  
:soon: Cost-benefit analysis for multimodal extraction in production  

---

## Data Metrics

### Articles Processed
- **Listeria (test):** ~650 articles (January-June 2025)
- **Hepatitis A (test):** 27 full-text XML articles (June 2025)
- **Ground Truth Dataset:** 227 validated documents
- **Golden Test Set:** 45 manually-labelled records (35 Salmonella + 10 E. coli)
  - Evaluable after remediation: ~25-30 records
  - Set aside (supplementary-only): 13 records
  - Output-token-limited: 2 records (PMC5033494, PMC6667439)
- **Ground Truth Accessions:** 2,681 total (after range expansion)
- **Supplementary Files Downloaded:** 1,335 files
- **Target corpus:** ~1800 documents for final experiments

### Performance Metrics
- **Stage 1 (Isolate ID):** 87% F1 score
- **Stage 2 (Assay Info):** 78.5% F1 score
- **Open Access Rate (Hepatitis A):** 0% in test sample
- **E-utilities Success Rate:** 100% for PMC-available articles
- **Supplementary Download Success:** 100% (227/227 articles)

---

## Documentation & Knowledge Base

### Created Documents
1. PubMed Article Downloader Design Documentation (v1, v2, v3, v3a, v3.1)
2. Literature References & Citations Tracking
3. Accession Number Format Reference (NCBI)
4. Presentation Guide (comprehensive)
5. Technical Comparison: XML vs PDF
6. DSPy Integration Guide for Colab
7. Ground Truth Data Requirements Analysis
8. Alternative Download Methods Evaluation
9. Multimodal Extraction Design Decision (DD-2025-001)
10. Unified Assay Signature Design Decision (DD-2025-002)

### Key Reference Papers
- Agrawal et al. (2025) - GEPA algorithm
- Khattab et al. (2024) - DSPy framework (ICLR)
- Databricks (2024) - GEPA production validation
- Various medical NLP domain applications

### Key Libraries
- DSPy - Declarative prompt programming
- GEPA - Prompt optimisation (bundled with DSPy)
- Attachments - Multimodal content processing for LLMs

---

## Next Steps & Recommendations

### Immediate Priorities (January 2025)

1. **Multimodal Extraction Test**
   - Set up attachments folder structure in Google Drive
   - Place PMC7738724 figure in correct location
   - Implement and test MultimodalAccessionExtractor signature
   - Validate against expected 27 SRA accessions from figure

2. **GEPA Optimisation Experiments**
   - Implement stratified sampling (10%/20%/30% splits)
   - Run baseline vs optimised comparisons
   - Document sample efficiency findings

3. **Ground Truth Refinement**
   - Complete error categorisation
   - Document edge cases for thesis
   - Prepare negative examples

### Code Finalisation (Target: January-February 2026)

- Complete DSPy pipeline implementation
- Integrate multimodal extraction pathway
- Finalise all tracking and logging systems
- Comprehensive error handling and validation
- Documentation for deployment and maintenance
- Performance benchmarking across all stages

### Report Preparation (Target: March 2026)

- Document methodology and technical approach
- Include "alternative methods evaluated" section (v3a findings)
- Present multimodal extraction as novel contribution
- Present performance metrics and validation results
- Discuss limitations and future work
- Emphasise novel contributions (DSPy, GEPA, XML, multimodal)

---

## Stakeholders & Collaboration

### Primary Contact
- **Research Fellow Supervisor:** Technical guidance and institutional resources

### External Interest
- Research doctorate colleague interested in DSPy and GEPA methodology
- Opportunity for knowledge sharing and collaboration

### Academic Accountability
- Professor satisfied with current progress and approach
- Expectation of rigorous methodology and evidence-based claims

---

## Risk Mitigation

### Technical Risks
- **Cascade Effect:** Stage 1 errors propagate to Stage 2
  - *Mitigation:* Optimise Stage 1 first, use section-aware extraction
  
- **Model API Changes:** Colab AI or AWS Bedrock updates
  - *Mitigation:* Maintain API-agnostic DSPy architecture
  
- **Resource Exhaustion:** Compute units or budget limitations
  - *Mitigation:* Efficient API-based approach, institutional support

- **Multimodal Cost Overrun:** Vision API costs exceed budget
  - *Mitigation:* Selective processing, cost tracking, SFA cost-benefit decision

### Compliance Risks
- **NCBI Policy Violations:** Improper API usage
  - *Mitigation:* Strict rate limiting, E-utilities compliance
  
- **Data Residency:** Singapore data centre requirement
  - *Mitigation:* AWS Bedrock Singapore for final experiments

### Schedule Risks
- **Code Deadline:** January 2026
  - *Mitigation:* Phased development, regular progress checks
  
- **Report Deadline:** February 2026
  - *Mitigation:* Continuous documentation, early draft preparation

---

## Last Activity

**Current Focus:** v4 Sonnet baseline run in progress. GEPA main run design finalised (DD-2026-018). All 149 evaluable GT records corrected (v4 diagnostic troubleshoot complete). PMC7083327 restored from set-aside to NIOAI with updated GT (v4 F1=0.25).

**Recent Achievement:** Completed v4 diagnostic troubleshoot across Pattern 1/2/3 records: GT corrections for 30+ PMCIDs (false isolate codes removed, serotypes shortened, missing assay data added, IWL$\rightarrow$NIOAI reclassifications, unicode fixes, structural format corrections). v4 Haiku baseline complete (mean F1=0.364 on 152 records). GEPA main run fully designed: 18-record stratified validation set, two-tier rule-based feedback with XML cross-reference, `max_full_evals=60` budget, Anthropic API with Sonnet/Opus.

**Next Session Goals:**
1. Confirm v4 Sonnet baseline results $\rightarrow$ select GEPA student model
2. Implement the two-tier feedback metric function (Tier 1: GT comparison, Tier 2: XML cross-reference)
3. Generate validation/training split files from master tracker
4. GEPA smoke test (max\_full\_evals=5)
5. GEPA productive run (100% training, max\_full\_evals=60)
6. Report writing

---

## Project Success Indicators

### Technical Success
- Two-stage pipeline achieving >85% F1 on both stages
- Successful GEPA optimisation showing measurable improvement
- Multimodal extraction demonstrating feasibility
- Robust system handling ~1800 documents efficiently
- Reproducible results using AWS Bedrock Singapore

### Academic Success
- Code delivered by February 2026
- Report completed by March 2026
- Novel methodology (DSPy + GEPA + XML + multimodal) clearly demonstrated
- Transparent handling of limitations and evidence-based claims

### Practical Success
- System valuable for SFA food safety monitoring
- Automated pathogen tracking reducing manual literature review
- Scalable approach applicable to other pathogens
- Clear documentation enabling maintenance and extension
- Cost-benefit analysis for multimodal extraction provided to SFA

---

**Document Created:** 19 November 2025  
**Last Updated:** 29 March 2026  
**Project Status:** v4 Sonnet baseline complete (mean F1=0.463). GEPA main run design approved (DD-2026-018). Loose F1 metric approved (DD-2026-019). All GT corrections complete. Next: GEPA smoke test, then productive runs.
