# GenBank/INSDC Accession Number Format Reference

**Source:** NCBI GenBank Accession Prefix Database  
**URL:** https://www.ncbi.nlm.nih.gov/genbank/acc_prefix/  
**Last Updated:** October 2025

## Overview

INSDC (International Nucleotide Sequence Database Collaboration) members—NCBI, EBI, and DDBJ—use standardized accession number formats to identify sequence records. This document provides a comprehensive reference for all accession number patterns.

## Understanding Accession Format Notation

The format notation uses a pattern: **PREFIX + DIGITS**

- **1+5** = 1 letter + 5 digits (Example: M12345)
- **2+6** = 2 letters + 6 digits (Example: AB123456)
- **3+5** = 3 letters + 5 digits (Example: AAA12345)
- **3+7** = 3 letters + 7 digits (Example: AAA1234567)
- **4+8** = 4 letters + 8 digits (Example: AAAA12345678)
- **5+6** = 5 letters + 6 digits (Example: AAAAA123456)
- **5+7** = 5 letters + 7 digits (Example: AAAAA1234567)
- **6+9** = 6 letters + 9 digits (Example: AAAAAA123456789)

**"or more"** indicates the digit count can exceed the base number.

## Key Terminology

- **EST:** Expressed Sequence Tag
- **GSS:** Genome Survey Sequence
- **HTG:** High-Throughput Genomic sequences
- **WGS:** Whole Genome Shotgun
- **TSA:** Transcriptome Shotgun Assembly
- **TLS:** Targeted Locus Study
- **TPA:** Third Party Annotation
- **CON:** Constructed sequences (scaffolds)
- **SRA:** Sequence Read Archive
- **MGA:** Mass sequence for Genome Annotation

## Single Letter Prefixes (1+5 format)

| Prefix | INSDC Partner | Sequence Type | Format |
|--------|---------------|---------------|--------|
| A | EBI | Patent | 1+5 |
| B | NCBI | GSS (previously DDBJ) | 1+5 |
| C | DDBJ | EST | 1+5 |
| D | DDBJ | Direct submissions | 1+5 |
| E | DDBJ | Patent | 1+5 |
| F | EBI | EST | 1+5 |
| G | NCBI | STS | 1+5 |
| H | NCBI | EST | 1+5 |
| I | NCBI | Patent | 1+5 |
| J | NCBI | LANL Direct submissions | 1+5 |
| K | NCBI | LANL Direct submissions | 1+5 |
| L | NCBI | LANL Direct submissions | 1+5 |
| M | NCBI | LANL Direct submissions | 1+5 |
| N | NCBI | EST | 1+5 |
| R | NCBI | EST | 1+5 |
| S | NCBI | Journal Scanning | 1+5 |
| T | NCBI | EST | 1+5 |
| U | NCBI | Direct submissions | 1+5 |
| V | EBI | Direct submissions | 1+5 |
| W | NCBI | EST (previously EBI) | 1+5 |
| X | EBI | Direct submissions | 1+5 |
| Y | EBI | Direct submissions | 1+5 |
| Z | EBI | Direct submissions | 1+5 |

## Two Letter Prefixes (2+6 format)

### EST (Expressed Sequence Tags)

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AA, AT, AU, AV, AW | Various | EST sequences |
| BB, BJ, BP, BW, BY | DDBJ | EST sequences |
| BE, BF, BG, BI, BM, BQ, BU | NCBI | EST sequences |
| CA, CB, CD, CF, CK, CN, CO | NCBI | EST sequences |
| CV, CX, DA, DB, DC, DK | DDBJ/NCBI | EST sequences |
| DN, DR, DT, DV, DW, DY | NCBI | EST sequences |
| EB, EC, EE, EG, EH, EL | NCBI | EST sequences |
| ES, EV, EW, EX, EY | NCBI | EST sequences |
| FC, FD, FE, FF, FG, FK, FL | NCBI | EST sequences |
| FS, FY, GD, GE, GH, GO | DDBJ/NCBI | EST sequences |
| GR, GT, GW, JG, JK, JZ | NCBI | EST sequences |
| LU, OH | DDBJ | EST sequences |

### GSS (Genome Survey Sequences)

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AG, AQ, AZ, BH, BZ | Various | GSS sequences |
| CC, CE, CG, CL, CW, CZ | NCBI | GSS sequences |
| DE, DH, DU, DX | DDBJ/NCBI | GSS sequences |
| ED, EI, EJ, EK, ER, ET | NCBI | GSS sequences |
| FH, FI, FT, GA, GS | Various | GSS sequences |
| JJ, JM, JS, JY, KG, KO, KS, MJ | NCBI | GSS sequences |
| LB | DDBJ | GSS sequences |

### Direct Submissions

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AB | DDBJ | Direct submissions |
| AF, AY, DQ | NCBI | Direct submissions |
| AJ, AM, HE, HF, HG, HH, HI | EBI | Direct submissions |
| EF, EU, JF, JN, JQ, JX | NCBI | Direct submissions |
| FM, FN, FO, FP, FQ, FR | EBI | Direct submissions |
| GQ, GU, KC, KF, KJ, KM, KP, KR, KT, KU, KX, KY | NCBI | Direct submissions |
| LC | DDBJ | Direct submissions |
| LK, LL, LM, LN, LO, LR, LS, LT | EBI | Direct submissions |
| MF, MG, MH, MK, MN, MT, MW, MZ | NCBI | Direct submissions |
| OA, OB, OC, OD, OE | EBI | Direct submissions |
| OK, OL, OM, ON, OP, OQ, OR | NCBI | Direct submissions |
| OU, OV, OW, OX, OY, OZ | EBI | Direct submissions |
| PP, PQ, PV, PX | NCBI | Direct submissions |

### Genome Projects

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AE | NCBI | Genome projects |
| AL | EBI | Genome projects |
| AP, BS | DDBJ | Genome projects |
| BX | EBI | Genome projects |
| CP | NCBI | Genome projects |
| CR, CT, CU | EBI | Genome projects |

### Patent Sequences

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AR, AX | NCBI/EBI | Patent sequences |
| BD, DD, DI, DJ, DL, DM, DZ | DDBJ/NCBI | Patent sequences |
| EA, FB, GC, GP, GV, GX, GY, GZ | Various | Patent sequences |
| HA, HB, HC, HD, HZ | EBI/DDBJ | Patent sequences |
| JA, JB, JC, JD, JE | EBI | Patent sequences |
| KH, LF, LG, LV, LX, LY, LZ | Various | Patent sequences |
| MA, MB, MC, MD, ME | DDBJ | Patent sequences |
| MI, MM, MO, MV, MX, MY | NCBI | Patent sequences |
| MP, MQ, MR, MS | EBI | Patent sequences |
| OF, OG, OI, OJ, OO, OS, OT | DDBJ/NCBI | Patent sequences |
| PA, PB, PC, PD, PE, PG, PH, PI, PJ, PK, PL, PM, PN, PO, PR, PT, PU, PW | Various | Patent sequences |
| QK, QL, QM, QN, QO, QP, QQ | EBI/DDBJ | Patent sequences |
| FU, FV, FW, FZ, GB, LP, LQ | Various | Patent sequences |
| GM, GN | EBI | Patent sequences |

### TSA (Transcriptome Shotgun Assembly)

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| EZ | NCBI | TSA sequences |
| FX | DDBJ | TSA sequences |
| JI, JL, JO, JP, JR, JT, JU, JV, JW | NCBI | TSA sequences |
| KA, LA, LE, LH, LI, LJ | Various | TSA sequences |

### Scaffold/CON (Constructed Sequences)

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AN, BA, CH, CM, DF, DG, DP, DS, EM, EN, EP, EQ, FA, GG, GJ, GK, GL | Various | Scaffold/CON sequences |
| JH, KB, KD, KE, KI, KK, KL, KN, KQ, KV, KZ, LD, ML, MU, PS | NCBI | Scaffold/CON sequences |

### HTG (High-Throughput Genomic)

| Prefix | INSDC Partner | Notes |
|--------|---------------|-------|
| AC | NCBI | HTG sequences |
| AK | DDBJ | HTC (High-Throughput cDNA) |

### Other Specific Types

| Prefix | INSDC Partner | Sequence Type | Notes |
|--------|---------------|---------------|-------|
| AH | NCBI | Direct submissions segsets | 2+6 |
| AI, AS | NCBI | Other projects | 2+6 |
| BC | NCBI | cDNA project | 2+6 |
| BK | NCBI | TPA | 2+6 |
| BL, GJ, GK | NCBI | TPA CON | 2+6 |
| BN, BR | EBI/DDBJ | TPA | 2+6 |
| BT | NCBI | FLI_cDNA | 2+6 |
| BV, GF | NCBI | STS | 2+6 |
| CY | NCBI | Influenza Virus Genome | 2+6 |

## Three Letter Prefixes (Protein)

### Standard Protein Format (3+5 or 3+7)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| AAA-AZZ | NCBI | Protein | 3+5 and 3+7 |
| BAA-BZZ | DDBJ | Protein | 3+5 and 3+7 |
| CAA-CZZ | EBI | Protein | 3+5 and 3+7 |
| DAA-DZZ | NCBI | TPA or TPA WGS protein | 3+5 and 3+7 |
| EAA-EZZ | NCBI | WGS protein | 3+5 and 3+7 |
| FAA-FZZ | DDBJ | TPA protein | 3+5 |
| GAA-GZZ | DDBJ | WGS protein | 3+5 |
| HAA-HZZ | NCBI | WGS/TSA TPA protein | 3+5 and 3+7 |
| IAA-IZZ | DDBJ | TPA WGS protein | 3+5 |
| JAA-JZZ | NCBI | TSA protein | 3+5 |
| KAA-KZZ | NCBI | WGS protein | 3+5 and 3+7 |
| LAA-LZZ | DDBJ | TSA/TLS protein | 3+5 |
| MAA-MZZ | NCBI | WGS/TSA protein | 3+5 and 3+7 |
| NAA-NZZ | NCBI | WGS/TSA protein | 3+5 |
| OAA-OZZ | NCBI | WGS protein | 3+5 |
| PAA-PZZ | NCBI | WGS protein | 3+5 |
| QAA-QZZ | NCBI | Protein | 3+5 |
| RAA-RZZ | NCBI | WGS protein | 3+5 |
| SAA-SZZ | EBI | Protein | 3+5 |
| TAA-TZZ | NCBI | WGS protein | 3+5 |
| UAA-UZZ | NCBI | Protein | 3+5 |
| VAA-VZZ | EBI | Protein | 3+5 |
| WAA-WZZ | NCBI | Protein | 3+5 |
| XAA-XZZ | NCBI | Protein | 3+5 |
| YAA-YZZ | NCBI | Protein | 3+5 |
| ZAA-ZZZ | DDBJ | Protein | 3+7 |

### SRA (Sequence Read Archive) Prefixes (3+6 or more)

| Prefix | INSDC Partner | Sequence Type | Format |
|--------|---------------|---------------|--------|
| DRA | DDBJ | SRA submissions | 3+6 or more |
| DRP | DDBJ | SRA sample | 3+6 or more |
| DRR | DDBJ | SRA runs | 3+6 or more |
| DRX | DDBJ | SRA experiment | 3+6 or more |
| DRZ | DDBJ | SRA analysis object | 3+6 or more |
| ERA | EBI | SRA submissions | 3+6 or more |
| ERP | EBI | SRA sample | 3+6 or more |
| ERR | EBI | SRA runs | 3+6 or more |
| ERX | EBI | SRA experiment | 3+6 or more |
| ERZ | EBI | SRA analysis object | 3+6 or more |
| SRA | NCBI | SRA submissions | 3+6 or more |
| SRP | NCBI | SRA sample | 3+6 or more |
| SRR | NCBI | SRA runs | 3+6 or more |
| SRX | NCBI | SRA experiment | 3+6 or more |
| SRZ | NCBI | SRA analysis object | 3+6 or more |

## Four Letter Prefixes (WGS/TSA/TLS)

### WGS (Whole Genome Shotgun) Format (4+8 or more)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| AAAA-AZZZ | NCBI | WGS | 4+8 or more |
| BAAA-BZZZ | DDBJ | WGS | 4+8 or more |
| CAAA-CZZZ | EBI | WGS | 4+8 or more |
| DAAA-DZZZ | NCBI | WGS/TSA/TLS TPA | 4+8 or more |
| EAAA-EZZZ | DDBJ | WGS TPA | 4+8 or more |
| FAAA-FZZZ | EBI | WGS | 4+8 or more |
| JAAA-JZZZ | NCBI | WGS | 4+8 or more |
| LAAA-LZZZ | NCBI | WGS | 4+8 or more |
| MAAA-MZZZ | NCBI | WGS | 4+8 or more |
| NAAA-NZZZ | NCBI | WGS | 4+8 or more |
| OAAA-OZZZ | EBI | WGS | 4+8 or more |
| PAAA-PZZZ | NCBI | WGS | 4+8 or more |
| QAAA-QZZZ | NCBI | WGS | 4+8 or more |
| RAAA-RZZZ | NCBI | WGS | 4+8 or more |
| SAAA-SZZZ | NCBI | WGS | 4+8 or more |
| UAAA-UZZZ | EBI | WGS | 4+8 or more |
| VAAA-VZZZ | NCBI | WGS | 4+8 or more |
| WAAA-WZZZ | NCBI | WGS | 4+8 or more |
| XAAA-XZZZ | NCBI | WGS | 4+8 or more |

### TSA (Transcriptome Shotgun Assembly) Format (4+8 or more)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| GAAA-GZZZ | NCBI | TSA | 4+8 or more |
| HAAA-HZZZ | EBI | TSA | 4+8 or more |
| IAAA-IZZZ | DDBJ | TSA | 4+8 or more |

### TLS (Targeted Locus Study) Format (4+8 or more)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| KAAA-KZZZ | NCBI | TLS | 4+8 or more |
| TAAA-TZZZ | DDBJ | TLS | 4+8 or more |

### TPA (Third Party Annotation) Format (4+8 or more)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| YAAA-YZZZ | DDBJ | TSA TPA | 4+8 or more |
| ZAAA-ZZZZ | DDBJ | TLS TPA | 4+8 or more |

## Five Letter Prefixes (MGA and BioProject)

### MGA (Mass sequence for Genome Annotation) Format (5+7)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| AAAAA-AZZZZ | DDBJ | MGA | 5+7 |

### BioProject Identifiers

| Prefix | INSDC Partner | Sequence Type | Format |
|--------|---------------|---------------|--------|
| PRJDA | DDBJ via NCBI | BioProject | 5+5 |
| PRJDB | DDBJ | BioProject | 5+6 or more |
| PRJEA | EBI via NCBI | BioProject | 5+5 |
| PRJEB | EBI | BioProject | 5+6 or more |
| PRJNA | NCBI | BioProject | 5+6 or more |

## Six Letter Prefixes (WGS Extended)

### WGS Extended Format (6+9 or more)

| Prefix Range | INSDC Partner | Sequence Type | Format |
|--------------|---------------|---------------|--------|
| AAAAAA-AZZZZZ | NCBI | WGS | 6+9 or more |
| BAAAAA-BZZZZZ | DDBJ | WGS | 6+9 or more |
| CAAAAA-CZZZZZ | EBI | WGS | 6+9 or more |
| DAAAAA-DZZZZZ | NCBI | WGS/TSA/TLS TPA | 6+9 or more |
| JAAAAA-JZZZZZ | NCBI | WGS | 6+9 or more |

## BioSample Identifiers

| Prefix | INSDC Partner | Sequence Type | Format |
|--------|---------------|---------------|--------|
| SAMD | DDBJ | BioSample | 4-5+6 or more |
| SAME | EBI | BioSample | 4-5+6 or more |
| SAMN | NCBI | BioSample | 4-5+6 or more |

## Version Numbers

Many accession numbers include version numbers to track updates:

**Format:** `ACCESSION.VERSION`

**Examples:**
- AB123456.1 (version 1)
- AB123456.2 (version 2, updated sequence)
- NM_001234567.3 (RefSeq with version 3)

## RefSeq Accession Patterns

RefSeq (NCBI Reference Sequence) accessions use a special format with underscores:

**Format:** `PREFIX_DIGITS`

### Common RefSeq Prefixes:

| Prefix | Type | Description | Example |
|--------|------|-------------|---------|
| NC_ | Chromosome | Complete genomic molecules | NC_000001 |
| NG_ | Genomic | Incomplete genomic region | NG_012345 |
| NM_ | mRNA | Messenger RNA | NM_001234567 |
| NP_ | Protein | Protein sequences | NP_001234567 |
| NR_ | RNA | Non-coding RNA | NR_012345 |
| NT_ | Contig | Genomic contig | NT_012345 |
| NW_ | Contig | WGS genomic contig | NW_012345 |
| NZ_ | Contig | WGS genomic contig from incomplete genome | NZ_AAAA01000001 |
| XM_ | mRNA | Model mRNA (predicted) | XM_001234567 |
| XP_ | Protein | Model protein (predicted) | XP_001234567 |
| XR_ | RNA | Model non-coding RNA | XR_012345 |
| YP_ | Protein | Protein (non-redundant) | YP_001234567 |
| ZP_ | Protein | Protein (annotated on NZ_ contigs) | ZP_01234567 |

## Special Cases and Notes

### Not Used Prefixes

Some prefixes are reserved but not currently used:
- DO (NCBI, 2+6) - not used
- EO (NCBI) - not used
- GI (NCBI) - not used

### Format Variations

1. **Ranges:** When seeing "AAA-AZZ", this means all three-letter combinations from AAA through AZZ (e.g., AAA, AAB, AAC, ... AZZ)

2. **"or more":** Indicates minimum digit count, but can be longer (e.g., "4+8 or more" means at least 4 letters + 8 digits, but could be 4+9, 4+10, etc.)

3. **Multiple Formats:** Some prefixes support multiple formats (e.g., "3+5 and 3+7" means both are valid)

```

## Common False Positives to Avoid

Not all letter-digit combinations are accession numbers:
- Gene symbols (e.g., TP53, BRCA1)
- Chemical formulas (e.g., H2O, CO2)
- Model numbers (e.g., PCR123)
- Catalog numbers (e.g., CAT12345)
- Random alphanumeric codes without matching patterns

**Key Distinguishers:**
- Accessions follow strict format rules
- Usually appear in specific contexts (methods, data availability)
- Often accompanied by database names (GenBank, RefSeq, etc.)

---

**Document prepared for DSPy context usage in automated accession number extraction from scientific literature.**
