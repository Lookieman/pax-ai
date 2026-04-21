r"""
screen_xmls.py
--------------
Screens PubMed Central XML articles for candidate selection across pathogens.
Produces a ranked CSV summarising key signals (tables, supplements, keyword hits)
to support manual selection of articles for cross-pathogen transfer testing.

Supported pathogens: hepae (Hepatitis A/E), listeria, salmonella

Usage:
    python screen_xmls.py --xml-dir <path> --output <csv> --pathogen <type>

Examples:
    python screen_xmls.py --xml-dir C:/proj/pax-ai-working/hep/articles --pathogen hepae
    python screen_xmls.py --xml-dir C:/proj/pax-ai-working/listeria/articles --pathogen listeria
"""

import argparse
import csv
import os
import sys
from xml.etree import ElementTree as ET


# --- Configuration -----------------------------------------------------------

# Keywords shared across all pathogen types
_BASE_KEYWORDS = [  #changed_090426
    "PCR",
    "sequencing",
    "genotyp",
    "isolate",
    "strain",
    "phylogenetic",
    "WGS",
    "whole genome",
]

# Pathogen-specific keyword extensions
_HEPAE_KEYWORDS = [  #changed_090426
    "RT-PCR",
    "qPCR",
    "real-time PCR",
    "nested PCR",
    "ELISA",
    "serotyp",
    "viral load",
    "Ct value",
    "cycle threshold",
    "IgM",
    "IgG",
    "RNA",
    "amplification",
]

_LISTERIA_KEYWORDS = [  #changed_090426
    "MLST",
    "cgMLST",
    "wgMLST",
    "PFGE",
    "pulsotype",
    "serotyp",
    "AST",
    "antimicrobial susceptibility",
    "MIC",
    "minimum inhibitory concentration",
    "AMR",
    "antimicrobial resistance",
    "resistance gene",
    "virulence",
    "hlyA",
    "inlA",
    "inlB",
    "prfA",
    "lineage",
    "clonal complex",
    "sequence type",
    "biofilm",
    "food isolate",
    "clinical isolate",
    "environmental isolate",
]

_SALMONELLA_KEYWORDS = [  #changed_090426
    "MLST",
    "cgMLST",
    "wgMLST",
    "PFGE",
    "pulsotype",
    "serotyp",
    "serovar",
    "AST",
    "antimicrobial susceptibility",
    "MIC",
    "minimum inhibitory concentration",
    "AMR",
    "antimicrobial resistance",
    "resistance gene",
    "virulence",
    "plasmid",
    "sequence type",
    "phage typ",
]

PATHOGEN_KEYWORDS = {  #changed_090426
    "hepae": _BASE_KEYWORDS + _HEPAE_KEYWORDS,
    "listeria": _BASE_KEYWORDS + _LISTERIA_KEYWORDS,
    "salmonella": _BASE_KEYWORDS + _SALMONELLA_KEYWORDS,
}

SUPPORTED_PATHOGENS = list(PATHOGEN_KEYWORDS.keys())  #changed_090426

REVIEW_INDICATORS = [
    "systematic review",
    "meta-analysis",
    "meta analysis",
    "scoping review",
    "literature review",
    "narrative review",
]

CSV_HEADERS = [
    "pmcid",
    "title",
    "article_type",
    "is_review",
    "table_count",
    "supp_count",
    "keyword_hit_count",
    "top_keywords",
    "isolate_in_table_header",
    "body_char_count",
]


# --- Helper functions --------------------------------------------------------

def extract_text_recursive(element):
    """Extract all text content from an XML element and its children."""
    parts = []
    if element is None:
        return ""
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(extract_text_recursive(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


def get_pmcid(root):
    """Extract PMCID from article-meta/article-id elements."""
    pmcid = ""
    for aid in root.iter("article-id"):
        if aid.get("pub-id-type") == "pmc":
            pmcid = (aid.text or "").strip()
            break
    return pmcid


def get_title(root):
    """Extract article title."""
    title_el = root.find(".//article-title")
    if title_el is not None:
        return extract_text_recursive(title_el).strip()
    return ""


def get_article_type(root):
    """Extract article-type attribute from the <article> element."""
    article_el = root.find(".//article")
    if article_el is not None:
        return article_el.get("article-type", "")
    # If root itself is the <article> element
    return root.get("article-type", "")


def check_is_review(title, body_text):
    """Check if the article is likely a review/meta-analysis."""
    combined = (title + " " + body_text).lower()
    for indicator in REVIEW_INDICATORS:
        if indicator in combined:
            return True
    return False


def count_tables(root):
    """Count <table-wrap> elements in the article."""
    return len(list(root.iter("table-wrap")))


def count_supplements(root):
    """Count <supplementary-material> elements."""
    return len(list(root.iter("supplementary-material")))


def get_body_text(root):
    """Extract full body text for keyword searching."""
    body = root.find(".//body")
    if body is not None:
        return extract_text_recursive(body)
    return ""


def count_keyword_hits(body_text, keywords):  #changed_090426
    """Count distinct keyword matches and return matched keywords."""
    body_lower = body_text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in body_lower:
            matched.append(kw)
    return len(matched), matched


def check_isolate_in_table_headers(root):
    """Check if 'isolate' or 'strain' appears in any table header cell."""
    target_terms = ["isolate", "strain"]
    for th in root.iter("th"):
        cell_text = extract_text_recursive(th).lower()
        for term in target_terms:
            if term in cell_text:
                return True
    return False


def screen_single_xml(filepath, keywords):  #changed_090426
    """Screen a single XML file and return a dict of screening signals."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    pmcid = get_pmcid(root)
    title = get_title(root)
    article_type = get_article_type(root)
    body_text = get_body_text(root)
    table_count = count_tables(root)
    supp_count = count_supplements(root)
    keyword_hit_count, matched_keywords = count_keyword_hits(body_text, keywords)  #changed_090426
    isolate_in_header = check_isolate_in_table_headers(root)
    is_review = check_is_review(title, body_text)
    body_char_count = len(body_text)

    row = {
        "pmcid": pmcid if pmcid else os.path.basename(filepath),
        "title": title,
        "article_type": article_type,
        "is_review": is_review,
        "table_count": table_count,
        "supp_count": supp_count,
        "keyword_hit_count": keyword_hit_count,
        "top_keywords": "; ".join(matched_keywords),
        "isolate_in_table_header": isolate_in_header,
        "body_char_count": body_char_count,
    }
    return row


# --- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Screen PMC XMLs for candidate selection across pathogens."  #changed_090426
    )
    parser.add_argument(
        "--xml-dir",
        required=True,
        help="Path to folder containing PMC XML files.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: <pathogen>_screening.csv).",  #changed_090426
    )
    parser.add_argument(  #changed_090426
        "--pathogen",
        required=True,
        choices=SUPPORTED_PATHOGENS,
        help=f"Pathogen type. Choices: {', '.join(SUPPORTED_PATHOGENS)}",
    )
    args = parser.parse_args()

    xml_dir = args.xml_dir
    pathogen = args.pathogen  #changed_090426
    output_path = args.output if args.output else f"{pathogen}_screening.csv"  #changed_090426
    keywords = PATHOGEN_KEYWORDS[pathogen]  #changed_090426

    print(f"Pathogen: {pathogen} ({len(keywords)} keywords)")  #changed_090426

    if not os.path.isdir(xml_dir):
        print(f"ERROR: Directory not found: {xml_dir}")
        sys.exit(1)

    xml_files = [
        f for f in os.listdir(xml_dir)
        if f.lower().endswith(".xml")
    ]
    xml_files.sort()

    if not xml_files:
        print(f"ERROR: No XML files found in {xml_dir}")
        sys.exit(1)

    print(f"Screening {len(xml_files)} XML files in {xml_dir} ...")

    results = []
    errors = []

    for filename in xml_files:
        filepath = os.path.join(xml_dir, filename)
        try:
            row = screen_single_xml(filepath, keywords)  #changed_090426
            results.append(row)
        except ET.ParseError as e:
            errors.append((filename, str(e)))
            print(f"  SKIP (parse error): {filename}")

    # Sort: keyword hits descending, then table count descending
    results.sort(
        key=lambda r: (r["keyword_hit_count"], r["table_count"]),
        reverse=True,
    )

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done. Wrote {len(results)} rows to {output_path}")
    if errors:
        print(f"Skipped {len(errors)} files due to parse errors:")
        for fn, err in errors:
            print(f"  {fn}: {err}")

    # Print top 20 summary to console
    print("\n--- Top 20 candidates ---")
    print(f"{'PMCID':<14} {'Tables':>6} {'Supps':>5} {'KW':>3} {'Review':>6}  Title")
    print("-" * 90)
    for row in results[:20]:
        review_flag = "YES" if row["is_review"] else ""
        title_trunc = row["title"][:50]
        print(
            f"{row['pmcid']:<14} {row['table_count']:>6} "
            f"{row['supp_count']:>5} {row['keyword_hit_count']:>3} "
            f"{review_flag:>6}  {title_trunc}"
        )


if __name__ == "__main__":
    main()
