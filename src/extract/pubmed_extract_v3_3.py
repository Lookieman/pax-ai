#!/usr/bin/env python3
"""
PubMed Article Downloader v3.3 - Command-Line Interface

Usage:
  python pubmed_extract_v3_3.py interactive --month June --year 2025
  python pubmed_extract_v3_3.py batch --csv pmcid_list.csv
  python pubmed_extract_v3_3.py scheduled

Requirements:
  - cfg.NCBI_API_KEY environment variable (or pass via --api-key)
  - pip install requests pandas

Version History:
  v3.0  - PMID-to-PMCID conversion, full-text XML from PMC
  v3.1  - Ground-truth download, supplementary file extraction
  v3.3  - CSV-based batch input, argparse CLI, standalone script
  v3.3  - Migrate supplementary download from FTP tarball to AWS S3
          individual file download via HTTPS (no AWS CLI/account needed).
          FTP-based functions retained but deprecated.
          Ref: DD-2026-047, NCBI PMC FTP retirement Aug 2026.
"""

import requests
import xml.etree.ElementTree as ET
import time
import os
import logging
import gzip
import shutil
import pandas as pd
import json
import re
import tarfile
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from ftplib import FTP
from urllib.parse import urlencode
from typing import Dict, List, Optional

# Ensure parent directory (src/) is on the import path  #changed_08042026
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  #changed_08042026

from config import Config  # #changed - centralised configuration

# =============================================================================
# CONFIGURATION (loaded from config.py)
# =============================================================================

cfg = Config()  # #changed - module-level config singleton

# Static constants (not path- or key-dependent)
DATABASE = "pubmed"
RETMODE_XML = "xml"
USE_HISTORY = "y"
PMC_PDF_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"
S3_HTTPS_BASE = "https://pmc-oa-opendata.s3.amazonaws.com"  #changed_10042026


# =============================================================================
# INITIALISATION
# =============================================================================

def initialise_paths(base_dir: str):
    """Re-initialise config with the given base directory."""  #changed
    global cfg
    cfg = Config(base_dir=base_dir)


def initialise_api_key(api_key: str = None):
    """Override NCBI API key if provided via CLI argument."""  #changed
    if api_key:
        cfg.NCBI_API_KEY = api_key

    if not cfg.NCBI_API_KEY:
        logging.warning("No NCBI API key provided. Rate limits will be stricter.")
        logging.warning("Set cfg.NCBI_API_KEY environment variable or use --api-key")


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging():
    os.makedirs(cfg.LOG_PATH, exist_ok=True)
    os.makedirs(cfg.MISSING_PMCID_LOG, exist_ok=True)

    log_filename = f"{cfg.LOG_PATH}/pubmed_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=cfg.LOG_LEVEL,
        format=cfg.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True,
    )
    logging.info(f"Logging initialised. Log file: {log_filename}")
    logging.info("PubMed Article Downloader v3.3 (CLI)")


def check_project_dir():
    try:
        os.makedirs(cfg.XML_PATH, exist_ok=True)
        os.makedirs(cfg.LOG_PATH, exist_ok=True)
        os.makedirs(cfg.MISSING_PMCID_LOG, exist_ok=True)
        logging.info(f"Project directories verified under {cfg.DRIVE_BASE}")
        return True
    except Exception as e:
        logging.error(f"Failed to create project directories: {str(e)}")
        return False


# =============================================================================
# SEARCH QUERY
# =============================================================================

def build_pathogen_search_query(pathogen_key):
    """Build PubMed search query for single pathogen."""
    pathogen = cfg.PATHOGENS[pathogen_key]
    term = pathogen['term']
    mesh = pathogen['mesh']

    full_query = (f'(({term}[Title] OR {term}[Abstract] OR "{term}"[Methods - Key Terms]) '
                  f'OR ({mesh}[MeSH Terms] OR {term}[All Fields]) '
                  f'NOT ((review[All Fields] OR "review literature as topic"[MeSH Terms] OR review[All Fields]) '
                  f'NOT Overview[All Fields]))')

    logging.info(f"Built search query for {pathogen['name']}")
    logging.info(f"Query: {full_query}")

    return full_query


# =============================================================================
# XML FUNCTIONS
# =============================================================================

def fetch_pmc_fulltext_xml(pmcid, retry_count=0):
    try:
        url = construct_pmc_fetch_url(pmcid)
        pmcid_clean = pmcid.replace('PMC', '', 1) if pmcid.startswith('PMC') else pmcid
        logging.info(f"Fetching full text XML for {pmcid_clean}")

        time.sleep(cfg.PMC_RATE_LIMIT_DELAY)
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            xml_content = response.text

            if '<body>' in xml_content or '<abstract>' in xml_content:
                logging.info(f"Successfully retrieved full-text XML for PMC{pmcid_clean}")
                return xml_content
            else:
                logging.warning(f"Response may contain metadata only for PMC{pmcid_clean}")
                return xml_content
        elif response.status_code == 404:
            logging.error(f"Full-text XML not found for PMC{pmcid_clean}")
            return None
        else:
            raise Exception(f"HTTP {response.status_code}")

    except Exception as e:
        pmcid_clean = pmcid.replace('PMC', '', 1) if pmcid.startswith('PMC') else pmcid
        logging.error(f"Failed to fetch full-text for PMC{pmcid_clean}: {str(e)}")

        if retry_count < cfg.MAX_RETRIES:
            logging.info(f"Retrying PMC{pmcid_clean} (attempt {retry_count + 1})")
            time.sleep(cfg.RATE_LIMIT_DELAY * 2)
            return fetch_pmc_fulltext_xml(pmcid, retry_count + 1)

        return None


def save_xml_with_compression(xml_content, identifier, search_date):
    try:
        filename = f"{identifier}_{search_date}.xml"
        filepath = os.path.join(cfg.XML_PATH, filename)

        if os.path.exists(filepath) or os.path.exists(f"{filepath}.gz"):
            logging.info(f"XML for {identifier} already exists - skipping")
            return True

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logging.info(f"Saved XML for {identifier}: {file_size_mb:.2f} MB")

        if file_size_mb > cfg.COMPRESS_THRESHOLD_MB:
            compressed_filepath = f"{filepath}.gz"
            with open(filepath, 'rb') as f_in:
                with gzip.open(compressed_filepath, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            os.remove(filepath)
            compressed_size_mb = os.path.getsize(compressed_filepath) / (1024 * 1024)
            logging.info(f"Compressed XML for {identifier}: {compressed_size_mb:.2f} MB")

        return True

    except Exception as e:
        logging.error(f"Failed to save XML for {identifier}: {str(e)}")
        return False


# =============================================================================
# EXTRACT FUNCTIONS
# =============================================================================

def extract_pmid_list(xml_response):
    root = ET.fromstring(xml_response)
    pmid_list = []
    id_list = root.find('IdList')

    if id_list is not None:
        for id_element in id_list.findall('Id'):
            pmid_list.append(id_element.text)
    return pmid_list


def extract_publication_date(article):
    pub_date = None
    data_element = article.find('.//PubDate')
    if data_element is not None:
        year = data_element.find('.//Year')
        month = data_element.find('.//Month')
        day = data_element.find('.//Day')

        if year is not None:
            pub_date = f"{year.text}"
            if month is not None:
                pub_date += f"-{month.text}"
                if day is not None:
                    pub_date += f"-{day.text}"
    return pub_date


def extract_abstract_text(article):
    abstract = "Abstract not available"
    abstract_element = article.find('.//Abstract')
    if abstract_element is not None:
        abstract_texts = []
        for abstract_text in abstract_element.findall('AbstractText'):
            label = abstract_text.get('Label', '')
            text = abstract_text.text if abstract_text.text is not None else ''

            if label and text:
                abstract_texts.append(f'{label}: {text}')
            elif text:
                abstract_texts.append(text)

        if abstract_texts:
            abstract = ' '.join(abstract_texts)

    return abstract


def extract_total_count(xml_response):
    root = ET.fromstring(xml_response)
    count_element = root.find('Count')

    if count_element is not None and count_element.text is not None:
        return int(count_element.text)
    return 0


# =============================================================================
# PMID-TO-PMCID CONVERSION
# =============================================================================

def convert_pmid_to_pmcid(pmid, retry_count=0):
    try:
        url = construct_elink_url(pmid)

        logging.debug(f"Converting PMID {pmid} to PMCID")
        time.sleep(cfg.RATE_LIMIT_DELAY)

        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logging.warning(f"elink returned HTTP {response.status_code} for PMID {pmid}")
            return None

        root = ET.fromstring(response.text)
        linksetdb = root.find('.//LinkSetDb')

        if linksetdb is None:
            logging.warning(f"No PMC link found for PMID {pmid}")
            return None

        link_id = linksetdb.find('.//Link/Id')
        if link_id is not None and link_id.text:
            pmcid_num = link_id.text
            pmcid = 'PMC' + pmcid_num
            logging.info(f"Converted PMID {pmid} to PMCID {pmcid}")
            return pmcid

        logging.warning(f"No PMCID found in response for PMID {pmid}")
        return None

    except ET.ParseError as e:
        logging.error(f"Failed to parse XML for PMID {pmid}: {str(e)}")
        return None

    except Exception as e:
        logging.error(f"Failed to convert PMID {pmid} to PMCID: {str(e)}")

        if retry_count < cfg.MAX_RETRIES:
            logging.info(f"Retrying PMID {pmid} (attempt {retry_count + 1})")
            time.sleep(cfg.RATE_LIMIT_DELAY * 2)
            return convert_pmid_to_pmcid(pmid, retry_count + 1)
    return None


def batch_convert_pmids_to_pmcids(pmid_list):
    pmid_to_pmcid_map = {}
    missing_pmcid_list = []

    logging.info(f"Starting PMID-to-PMCID conversion for {len(pmid_list)} articles")

    total_pmids = len(pmid_list)

    for i, pmid in enumerate(pmid_list, 1):
        pmcid = convert_pmid_to_pmcid(pmid)

        if pmcid is not None:
            pmid_to_pmcid_map[pmid] = pmcid
        else:
            missing_pmcid_list.append(pmid)
            logging.warning(f"PMID {pmid} has no PMC version")

    success_count = len(pmid_to_pmcid_map)
    success_rate = (success_count / total_pmids * 100) if total_pmids > 0 else 0

    logging.info(f"PMID-to-PMCID conversion completed. {success_count}/{total_pmids} successful ({success_rate:.1f}%)")
    logging.warning(f"Missing PMCIDs: {len(missing_pmcid_list)} articles")

    return pmid_to_pmcid_map, missing_pmcid_list


def track_missing_pmcid(tracking_df, pmid, reason):
    tracking_df = update_tracking_data(
        df=tracking_df,
        pmid=pmid,
        pmcid=None,
        pmcid_status='not_found',
        fulltext_xml_status='not_attempted',
        error_message=reason
    )

    missing_log_file = f"{cfg.MISSING_PMCID_LOG}/missing_pmcids_{datetime.now().strftime('%Y%m%d')}.csv"

    missing_record = {
        'pmid': pmid,
        'reason': reason,
        'date_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if os.path.exists(missing_log_file):
        missing_df = pd.read_csv(missing_log_file)
        missing_df = pd.concat([missing_df, pd.DataFrame([missing_record])], ignore_index=True)
    else:
        missing_df = pd.DataFrame([missing_record])

    missing_df.to_csv(missing_log_file, index=False)
    logging.warning(f"Tracked missing PMCID: PMID {pmid} - {reason}")

    return tracking_df


def generate_download_summary(tracking_df, date_start, date_end):
    summary_file = f"{cfg.LOG_PATH}/summary_{datetime.now().strftime('%Y%m%d')}.txt"

    current_date_str = datetime.now().strftime('%Y-%m-%d')
    current_run = tracking_df[tracking_df['download_date'].str.contains(current_date_str)]

    total_processed = len(current_run)
    pmcids_found = len(current_run[current_run['pmcid_status'] == 'found'])
    pmcids_not_found = len(current_run[current_run['pmcid_status'] == 'not_found'])
    pmcids_fetch_failed = len(current_run[current_run['pmcid_status'] == 'fetch_failed'])

    fulltext_success = len(current_run[current_run['fulltext_xml_status'] == 'success'])
    fulltext_failed = len(current_run[current_run['fulltext_xml_status'] == 'failed'])
    fulltext_not_attempted = len(current_run[current_run['fulltext_xml_status'] == 'not_attempted'])

    conversion_rate = (pmcids_found / total_processed * 100) if total_processed > 0 else 0
    success_rate = (fulltext_success / total_processed * 100) if total_processed > 0 else 0

    summary = f"""
    ===== PUBMED ARTICLE DOWNLOADER v3.3 - SUMMARY REPORT =====
    Date Range: {date_start} to {date_end}
    Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    PMID-TO-PMCID CONVERSION:
    -------------------------
    Total PMIDs Searched: {total_processed}
    PMCIDs Found: {pmcids_found} ({conversion_rate:.1f}%)
    PMCIDs Not Found: {pmcids_not_found}
    Conversion Fetch Failed: {pmcids_fetch_failed}

    FULL-TEXT XML RETRIEVAL:
    ------------------------
    Successful Downloads: {fulltext_success} ({success_rate:.1f}% of found)
    Failed Downloads: {fulltext_failed}
    Not Attempted: {fulltext_not_attempted}

    HISTORICAL DATA:
    ----------------
    Total Records in Database: {len(tracking_df)}
    Total Unique PMCIDs: {len(tracking_df[tracking_df['pmcid'].notna()]['pmcid'].unique())}

    FILES GENERATED:
    ----------------
    Tracking File: {cfg.TRACKING_FILE}
    Missing PMCIDs Log: {cfg.MISSING_PMCID_LOG}/missing_pmcids_{datetime.now().strftime('%Y%m%d')}.csv
    XML Files Directory: {cfg.XML_PATH}

    =========================================================
    """

    with open(summary_file, 'w') as f:
        f.write(summary)

    logging.info(f"Summary report saved to {summary_file}")
    print(summary)


# =============================================================================
# URL CONSTRUCTION
# =============================================================================

def construct_elink_url(pmid):
    params = {
        'dbfrom': 'pubmed',
        'db': 'pmc',
        'linkname': 'pubmed_pmc',
        'id': pmid,
        'retmode': 'xml',
    }
    if cfg.NCBI_API_KEY:
        params['api_key'] = cfg.NCBI_API_KEY
    return cfg.EUTILS_BASE_URL + 'elink.fcgi?' + urlencode(params)


def construct_pmc_fetch_url(pmcid):
    pmcid_clean = pmcid.replace('PMC', '') if pmcid.startswith('PMC') else pmcid
    params = {
        'db': 'pmc',
        'id': pmcid_clean,
        'retmode': 'xml',
    }
    if cfg.NCBI_API_KEY:
        params['api_key'] = cfg.NCBI_API_KEY
    return cfg.EUTILS_BASE_URL + 'efetch.fcgi?' + urlencode(params)


def construct_esearch_url(database, term, mindate, maxdate, datetype, retmax, usehistory):
    params = {
        'db': database,
        'term': term,
        'mindate': mindate,
        'maxdate': maxdate,
        'datetype': datetype,
        'retmax': retmax,
        'usehistory': usehistory,
        'retmode': 'xml',
    }
    if cfg.NCBI_API_KEY:
        params['api_key'] = cfg.NCBI_API_KEY
    return cfg.EUTILS_BASE_URL + 'esearch.fcgi?' + urlencode(params)


def construct_efetch_url(database, pmids, retmode):
    id_string = ','.join(pmids)
    params = {
        'db': database,
        'id': id_string,
        'retmode': retmode,
    }
    if cfg.NCBI_API_KEY:
        params['api_key'] = cfg.NCBI_API_KEY
    return cfg.EUTILS_BASE_URL + 'efetch.fcgi?' + urlencode(params)


def make_http_request(url, retry_count=0):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP request failed: {str(e)}")
        if retry_count < cfg.MAX_RETRIES:
            logging.info(f"Retrying...(attempt {retry_count + 1})")
            time.sleep(cfg.RATE_LIMIT_DELAY * (retry_count + 1))
            return make_http_request(url, retry_count + 1)
        raise


# =============================================================================
# TRACKING DATA
# =============================================================================

def load_tracking_data():
    if os.path.exists(cfg.TRACKING_FILE):
        try:
            df = pd.read_csv(cfg.TRACKING_FILE)
            logging.info(f"Loaded {len(df)} existing records from tracking file")
            return df
        except Exception as e:
            logging.error(f"Failed to load tracking data: {str(e)}")

    df = pd.DataFrame(columns=['pmid', 'pmcid', 'pmcid_status', 'download_date',
                                'fulltext_xml_status', 'error_message'])
    return df


def update_tracking_data(df, pmid, pmcid, pmcid_status, fulltext_xml_status, error_message=None):
    new_record = {
        'pmid': pmid,
        'pmcid': pmcid,
        'pmcid_status': pmcid_status,
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'fulltext_xml_status': fulltext_xml_status,
        'error_message': error_message
    }

    if pmid in df['pmid'].values:
        idx = df[df['pmid'] == pmid].index[0]
        for key, value in new_record.items():
            df.at[idx, key] = value
        logging.debug(f"Updated existing record for PMID {pmid}")
    else:
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        logging.debug(f"Added new record for PMID {pmid}")
    return df


def save_tracking_data(df):
    try:
        df.to_csv(cfg.TRACKING_FILE, index=False)
        logging.info(f"Saved tracking data with {len(df)} records")
    except Exception as e:
        logging.error(f"Failed to save tracking data: {str(e)}")


# =============================================================================
# DATE UTILITIES
# =============================================================================

def get_previous_month_date_range():
    today = datetime.now()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)

    date_start = first_day_previous_month.strftime('%Y/%m/%d')
    date_end = last_day_previous_month.strftime('%Y/%m/%d')

    logging.info(f"Date range for previous month: {date_start} to {date_end}")
    return date_start, date_end


def parse_month_input(month_input, year_input=None):
    """Parse month string and return (date_start, date_end) in YYYY/MM/DD format."""
    month_names = {
        'january': '01', 'jan': '01',
        'february': '02', 'feb': '02',
        'march': '03', 'mar': '03',
        'april': '04', 'apr': '04',
        'may': '05',
        'june': '06', 'jun': '06',
        'july': '07', 'jul': '07',
        'august': '08', 'aug': '08',
        'september': '09', 'sep': '09',
        'october': '10', 'oct': '10',
        'november': '11', 'nov': '11',
        'december': '12', 'dec': '12'
    }

    if year_input is None:
        year = datetime.now().year
    else:
        year = int(year_input)

    month_lower = month_input.lower().strip()

    if month_lower.isdigit():
        month = int(month_lower)
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month number: {month_input}. Must be between 1 and 12")
    else:
        month_str = month_names.get(month_lower)
        if month_str is None:
            raise ValueError(f"Invalid month: {month_input}")
        month = int(month_str)

    if year < 1900 or year > datetime.now().year:
        raise ValueError(f"Invalid year: {year_input}")

    first_day = datetime(year, month, 1)

    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)

    date_start = first_day.strftime('%Y/%m/%d')
    date_end = last_day.strftime('%Y/%m/%d')

    logging.info(f"Parsed {month_input} {year} to range: {date_start} - {date_end}")
    return date_start, date_end


# =============================================================================
# PMCID COLLECTION (v3.3: CSV-based + backward-compatible directory scan)
# =============================================================================

def extract_pmcid_from_filename(filename: str) -> Optional[str]:
    """
    Extract PMC ID from JSON filename.
    Retained for backward compatibility with v3.1 directory scanning.
    """
    pattern = r'(PMC\d+)'
    match = re.search(pattern, filename, re.IGNORECASE)

    if match:
        return match.group(1).upper()

    return None


def collect_pmcids_from_directory(directory: str) -> List[str]:
    """
    Scan directory for JSON files and extract PMCIDs from filenames.
    Retained for backward compatibility with v3.1.
    """
    pmcid_list = []
    files_scanned = 0
    files_with_pmcid = 0

    gt_files = list(Path(directory).glob("*.json"))

    for gt_file in gt_files:
        pmcid = extract_pmcid_from_filename(gt_file.name)
        files_scanned += 1

        if pmcid and pmcid not in pmcid_list:
            pmcid_list.append(pmcid)
            files_with_pmcid += 1
        else:
            logging.error(f"Could not extract PMCID from: {gt_file}")

    logging.info(f"Scanned {files_scanned} files, found {files_with_pmcid} unique PMCIDs")
    return pmcid_list


def load_pmcids_from_csv(csv_path: str) -> List[str]:  #changed - NEW function for v3.3
    """
    Load PMCIDs from a CSV file.

    Supports multiple CSV formats:
      1. Column named 'pmcid' or 'PMCID' (case-insensitive match)
      2. Column named 'pmc_id' or 'PMC_ID' (case-insensitive match)
      3. Falls back to the first column if no matching header found
      4. Single-column CSV with no header (auto-detected if first row looks like a PMCID)

    Each PMCID is normalised to uppercase with 'PMC' prefix.
    Duplicates and blank rows are removed.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of unique, normalised PMCID strings

    Raises:
        FileNotFoundError: If csv_path does not exist
        ValueError: If no valid PMCIDs could be parsed
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logging.info(f"Loading PMCIDs from CSV: {csv_path}")

    # Read the CSV
    df = pd.read_csv(csv_path, dtype=str)

    # Determine which column contains PMCIDs
    pmcid_column = None
    columns_lower = {col.strip().lower(): col for col in df.columns}

    # Priority 1: exact match on known column names
    for candidate in ['pmcid', 'pmc_id', 'pmc id', 'pmcids']:
        if candidate in columns_lower:
            pmcid_column = columns_lower[candidate]
            break

    # Priority 2: check if the first column header itself looks like a PMCID
    #              (indicates a headerless CSV that pandas read the first row as header)
    if pmcid_column is None:
        first_col_name = df.columns[0]
        if re.match(r'^PMC\d+$', first_col_name.strip(), re.IGNORECASE):
            logging.info("Detected headerless CSV - re-reading with no header")
            df = pd.read_csv(csv_path, header=None, dtype=str)
            pmcid_column = 0

    # Priority 3: fall back to first column
    if pmcid_column is None:
        pmcid_column = df.columns[0]
        logging.warning(f"No 'pmcid' column found - using first column: '{pmcid_column}'")

    # Extract and normalise
    raw_values = df[pmcid_column].dropna().astype(str).str.strip()
    raw_values = raw_values[raw_values != '']

    pmcid_list = []
    invalid_count = 0

    for raw in raw_values:
        normalised = raw.upper()

        # Add PMC prefix if missing (e.g. user supplied just the number)
        if normalised.isdigit():
            normalised = f"PMC{normalised}"

        # Validate format
        if re.match(r'^PMC\d+$', normalised):
            if normalised not in pmcid_list:
                pmcid_list.append(normalised)
        else:
            invalid_count += 1
            logging.warning(f"Skipping invalid PMCID value: '{raw}'")

    if not pmcid_list:
        raise ValueError(f"No valid PMCIDs found in {csv_path}")

    logging.info(f"Loaded {len(pmcid_list)} unique PMCIDs from CSV")
    if invalid_count > 0:
        logging.warning(f"Skipped {invalid_count} invalid entries")

    return pmcid_list


# =============================================================================
# OA FILE LIST & SUPPLEMENTARY (DEPRECATED - FTP being retired Aug 2026)
# Retained for backward compatibility. Use S3 functions below instead.
# =============================================================================

def load_oa_file_list(force_refresh: bool = False) -> Optional[Dict[str, str]]:
    """
    Download or load cached oa_file_list.csv.
    Returns: Dictionary mapping PMCID -> FTP path, or None if failed.
    """
    cache_path = Path(cfg.OA_FILE_LIST_LOCAL)
    cache_max_age_days = 7

    if cache_path.is_file() and not force_refresh:
        file_stat = cache_path.stat()
        file_timestamp = file_stat.st_mtime
        file_age = (datetime.now() - datetime.fromtimestamp(file_timestamp)).days

        if file_age < cache_max_age_days:
            logging.info(f"Using cached OA file list (age: {file_age} days)")
        else:
            logging.info(f"Cache is stale ({file_age} days old), downloading fresh copy...")
            force_refresh = True

    if not cache_path.exists() or force_refresh:
        logging.info("Downloading OA file list from NCBI FTP...")

        try:
            response = requests.get(cfg.OA_FILE_LIST_URL, timeout=120)

            if response.status_code == 200:
                Path(cfg.SUPPLEMENTARY_PATH).mkdir(parents=True, exist_ok=True)
                with open(cfg.OA_FILE_LIST_LOCAL, 'w', encoding='utf-8') as f:
                    f.write(response.text)
            else:
                logging.error(f"Failed to download OA file list: HTTP {response.status_code}")
                if not cache_path.exists():
                    return None

        except requests.RequestException as e:
            logging.error(f"Failed to download OA file list: {str(e)}")
            if not cache_path.exists():
                return None
            logging.warning("Using existing cache despite download failure")

    try:
        oa_df = pd.read_csv(cfg.OA_FILE_LIST_LOCAL,
                            skiprows=1,
                            names=['ftp_path', 'citation', 'pmcid', 'timestamp', 'pmid', 'license'],
                            dtype=str,
                            low_memory=False
                            )

        pmcid_to_ftp = {}
        for pmcid, ftp_path in zip(oa_df['pmcid'].values, oa_df['ftp_path'].values):
            pmcid_str = str(pmcid).strip().upper()
            ftp_path_str = str(ftp_path).strip()

            if pmcid_str and ftp_path_str and pmcid_str != 'NAN':
                pmcid_to_ftp[pmcid_str] = ftp_path_str

        return pmcid_to_ftp

    except Exception as e:
        logging.error(f"Failed to parse OA file list: {str(e)}")
        return None


def download_supplementary_package(pmcid: str, ftp_path: str, retry_count=0) -> Dict:
    """Download .tar.gz package from FTP and extract supplementary files only."""

    full_url = cfg.FTP_BASE_URL + ftp_path
    output_dir = f"{cfg.SUPPLEMENTARY_PATH}/{pmcid}"
    temp_tar_path = f"{output_dir}/temp_package.tar.gz"
    max_retries = 3

    result = {
        'status': 'pending',
        'files_extracted': [],
        'manifest': None
    }

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        manifest_path = f"{output_dir}/manifest.json"

        if Path(manifest_path).exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

                if manifest.get('download_status') == 'success':
                    logging.info(f"Skipping {pmcid} - supplementary files already downloaded")
                    result['status'] = "skipped"
                    result['manifest'] = manifest
                    return result

        time.sleep(cfg.FTP_RATE_LIMIT_DELAY)

        logging.info(f"Downloading supplementary package for {pmcid}")
        response = requests.get(full_url, timeout=60, stream=True)

        if response.status_code == 200:
            with open(temp_tar_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            extracted_files = extract_supplementary_from_tar(temp_tar_path, output_dir, pmcid)

            if Path(temp_tar_path).exists():
                os.remove(temp_tar_path)

            if extracted_files is not None:
                manifest = {
                    'pmcid': pmcid,
                    'download_date': datetime.now().strftime('%Y%m%d_%H%M%S'),
                    'download_status': 'success',
                    'ftp_path': ftp_path,
                    'files': extracted_files
                }

                with open(manifest_path, "w", encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)

                result['status'] = 'success'
                result['files_extracted'] = extracted_files
                result['manifest'] = manifest
                logging.info(f"Extracted {len(extracted_files)} supplementary files for {pmcid}")
            else:
                logging.warning(f"Package not found for {pmcid}")
                result['status'] = 'failed'

        elif response.status_code == 404:
            logging.warning(f"Package not found for {pmcid}")
            result['status'] = 'not_found'

        else:
            raise Exception(f"HTTP {response.status_code}")

    except Exception as e:
        logging.error(f"Failed to download supplementary for {pmcid}: {str(e)}")

        if retry_count < max_retries:
            logging.info(f"Retrying {pmcid} (attempt {retry_count + 1})")
            time.sleep(cfg.FTP_RATE_LIMIT_DELAY * 2)
            return download_supplementary_package(pmcid, ftp_path, retry_count + 1)

        result['status'] = 'failed'
        result['error'] = str(e)

    return result


def extract_supplementary_from_tar(tar_path: str, output_dir: str, pmcid: str) -> List:
    """Extract only supplementary files from the tar.gz package."""
    extracted_files = []
    supplementary_extensions = ['.xlsx', '.xls', '.csv', '.docx', '.doc',
                                '.pdf', '.txt', '.zip', '.png', '.jpg',
                                '.jpeg', '.tiff', '.tif', '.eps', '.svg']
    skip_patterns = ['.nxml', '.xml']

    try:
        supp_extension_set = set(supplementary_extensions)

        with tarfile.open(tar_path, 'r:gz') as tar:
            for member in tar.getmembers():
                filename = Path(member.name).name
                file_ext = Path(filename).suffix

                if Path(member.name).is_dir() or not filename:
                    continue

                if file_ext in skip_patterns:
                    logging.debug(f"Skipping XML file: {filename}")
                    continue

                is_supp_extension = file_ext in supp_extension_set
                is_supp_path = "supp" in member.name.lower()

                if is_supp_extension or is_supp_path:
                    safe_filename = sanitise_filename(filename)
                    output_path = Path(output_dir) / safe_filename

                    if output_path.exists():
                        counter = 1
                        stem = output_path.stem
                        suffix = output_path.suffix

                        while output_path.exists():
                            safe_filename = f"{stem}_{counter}{suffix}"
                            output_path = Path(output_dir) / safe_filename
                            counter += 1

                    file_obj = tar.extractfile(member)

                    if file_obj is not None:
                        content = file_obj.read()
                        output_path.write_bytes(content)

                        files_info = {
                            'original_name': filename,
                            'saved_as': safe_filename,
                            'extension': file_ext,
                            'size_bytes': len(content),
                            'path_in_tar': member.name
                        }
                        extracted_files.append(files_info)

                        logging.debug(f"Extracted: {filename} -> {safe_filename}")

            logging.info(f"Extracted {len(extracted_files)} supplementary files for {pmcid}")
    except tarfile.TarError as e:
        logging.error(f"Tar extraction error for {pmcid}: {str(e)}")

    except Exception as e:
        logging.error(f"Failed to extract from tar for {pmcid}: {str(e)}")

    return extracted_files


def sanitise_filename(filename: str) -> str:
    """Ensure filename is safe for filesystem storage."""
    max_length = 200
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]

    base_name = Path(filename).name
    base_name = base_name.replace('\x00', '')

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    safe_name = re.sub(invalid_chars_pattern, '_', base_name)

    safe_name = safe_name.strip(' .')

    safe_path = Path(safe_name)
    name_excl_ext = safe_path.stem
    ext = safe_path.suffix

    if name_excl_ext.upper() in reserved_names:
        safe_name = f"_{name_excl_ext}{ext}"

    if len(safe_name) > max_length:
        safe_path = Path(safe_name)
        name_part = safe_path.stem
        ext_part = safe_path.suffix
        avail_length = max_length - len(ext_part)
        safe_name = name_part[:avail_length] + ext_part

    if not safe_name or safe_name == '':
        safe_name = 'unnamed_file'

    return safe_name


def _resolve_duplicate_path(output_path: Path) -> Path:                        #changed_10042026
    """Return a non-colliding path by appending _1, _2, etc."""                #changed_10042026
    if not output_path.exists():                                               #changed_10042026
        return output_path                                                     #changed_10042026
    counter = 1                                                                #changed_10042026
    stem = output_path.stem                                                    #changed_10042026
    suffix = output_path.suffix                                                #changed_10042026
    while output_path.exists():                                                #changed_10042026
        output_path = output_path.parent / f"{stem}_{counter}{suffix}"         #changed_10042026
        counter += 1                                                           #changed_10042026
    return output_path                                                         #changed_10042026


# =============================================================================
# SUPPLEMENTARY DOWNLOAD VIA AWS S3 (v3.3)                                     #changed_10042026
# Replaces FTP tarball workflow. Uses HTTPS to fetch JSON metadata and
# individual supplementary files from PMC Open Access S3 bucket.
# No AWS account or CLI required.
# =============================================================================

# Pattern for inline figure/table/equation images (not supplementary)
_FIGURE_PATTERN = re.compile(                                                  #changed_10042026
    r'\.(g|t|e)\d+\.(jpg|jpeg|png|gif|tif|tiff)$', re.IGNORECASE              #changed_10042026
)                                                                              #changed_10042026

# Pattern for supplementary file naming (e.g. pone.0202286.s001.xlsx)
_SUPP_NAMING_PATTERN = re.compile(r'\.s\d+\.\w+$', re.IGNORECASE)             #changed_10042026

# Extensions considered supplementary when not matched by figure pattern
_SUPP_EXTENSIONS = {                                                           #changed_10042026
    '.xlsx', '.xls', '.csv', '.docx', '.doc', '.pdf', '.txt',                 #changed_10042026
    '.zip', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.eps', '.svg',         #changed_10042026
    '.pptx', '.ppt', '.tsv', '.gz', '.fasta', '.fna', '.gbk',                #changed_10042026
}                                                                              #changed_10042026


def _is_supplementary_file(filename: str) -> bool:                             #changed_10042026
    """Determine whether a media_url filename is a supplementary file.         #changed_10042026
                                                                               #changed_10042026
    Supplementary files are identified by either:                              #changed_10042026
      - the .sNNN. naming convention (e.g. pone.0202286.s001.xlsx)             #changed_10042026
      - having a supplementary-type extension AND not being an                 #changed_10042026
        inline figure/table/equation image                                     #changed_10042026
    """                                                                        #changed_10042026
    if _SUPP_NAMING_PATTERN.search(filename):                                  #changed_10042026
        return True                                                            #changed_10042026
    ext = Path(filename).suffix.lower()                                        #changed_10042026
    if ext in _SUPP_EXTENSIONS and not _FIGURE_PATTERN.search(filename):       #changed_10042026
        return True                                                            #changed_10042026
    return False                                                               #changed_10042026


def _s3_url_to_https(s3_url: str) -> str:                                     #changed_10042026
    """Convert s3://pmc-oa-opendata/... URL to HTTPS URL.                      #changed_10042026
                                                                               #changed_10042026
    Strips the ?md5= query parameter if present.                               #changed_10042026
    """                                                                        #changed_10042026
    s3_path = s3_url.replace("s3://pmc-oa-opendata/", "")                      #changed_10042026
    s3_path = s3_path.split("?")[0]                                            #changed_10042026
    return f"{S3_HTTPS_BASE}/{s3_path}"                                        #changed_10042026


def download_supplementary_s3(pmcid: str, version: int = 1,                   #changed_10042026
                               retry_count: int = 0) -> Dict:                 #changed_10042026
    """Download supplementary files for a PMCID from AWS S3 via HTTPS.         #changed_10042026
                                                                               #changed_10042026
    Fetches the JSON metadata for the article version, filters media_urls      #changed_10042026
    for supplementary files, and downloads each individually.                  #changed_10042026
                                                                               #changed_10042026
    Args:                                                                      #changed_10042026
        pmcid:       Normalised PMCID (e.g. 'PMC6118388')                      #changed_10042026
        version:     Article version number (default 1)                        #changed_10042026
        retry_count: Internal retry counter                                    #changed_10042026
                                                                               #changed_10042026
    Returns:                                                                   #changed_10042026
        Dict with keys: status, files_downloaded, manifest                     #changed_10042026
    """                                                                        #changed_10042026
    prefix = f"{pmcid}.{version}"                                              #changed_10042026
    json_url = f"{S3_HTTPS_BASE}/{prefix}/{prefix}.json"                       #changed_10042026
    output_dir = Path(cfg.SUPPLEMENTARY_PATH) / pmcid                          #changed_10042026
    manifest_path = output_dir / "manifest.json"                               #changed_10042026
    max_retries = 3                                                            #changed_10042026
                                                                               #changed_10042026
    result = {                                                                 #changed_10042026
        'status': 'pending',                                                   #changed_10042026
        'files_downloaded': [],                                                #changed_10042026
        'manifest': None                                                       #changed_10042026
    }                                                                          #changed_10042026
                                                                               #changed_10042026
    try:                                                                       #changed_10042026
        # 1. Check existing manifest                                          #changed_10042026
        if manifest_path.exists():                                             #changed_10042026
            with open(manifest_path, 'r', encoding='utf-8') as f:             #changed_10042026
                existing_manifest = json.load(f)                               #changed_10042026
            if existing_manifest.get('download_status') == 'success':          #changed_10042026
                logging.info(f"Skipping {pmcid} - supplementary already downloaded")  #changed_10042026
                result['status'] = 'skipped'                                   #changed_10042026
                result['manifest'] = existing_manifest                         #changed_10042026
                return result                                                  #changed_10042026
                                                                               #changed_10042026
        # 2. Fetch JSON metadata from S3                                      #changed_10042026
        logging.info(f"Fetching S3 metadata for {pmcid} (version {version})") #changed_10042026
        time.sleep(cfg.PMC_RATE_LIMIT_DELAY)                                   #changed_10042026
        meta_response = requests.get(json_url, timeout=30)                     #changed_10042026
                                                                               #changed_10042026
        if meta_response.status_code == 404:                                   #changed_10042026
            logging.warning(f"{pmcid} not found on S3 (version {version})")    #changed_10042026
            result['status'] = 'not_found'                                     #changed_10042026
            return result                                                      #changed_10042026
                                                                               #changed_10042026
        if meta_response.status_code != 200:                                   #changed_10042026
            raise Exception(                                                   #changed_10042026
                f"S3 metadata HTTP {meta_response.status_code} for {pmcid}"    #changed_10042026
            )                                                                  #changed_10042026
                                                                               #changed_10042026
        metadata = meta_response.json()                                        #changed_10042026
                                                                               #changed_10042026
        # 3. Filter media_urls for supplementary files                        #changed_10042026
        media_urls = metadata.get('media_urls', [])                            #changed_10042026
        supp_urls = []                                                         #changed_10042026
        for s3_url in media_urls:                                              #changed_10042026
            raw_path = s3_url.split("?")[0]                                    #changed_10042026
            filename = Path(raw_path).name                                     #changed_10042026
            if _is_supplementary_file(filename):                               #changed_10042026
                supp_urls.append(s3_url)                                       #changed_10042026
                                                                               #changed_10042026
        if not supp_urls:                                                      #changed_10042026
            logging.info(f"{pmcid} has no supplementary files in S3 metadata") #changed_10042026
            result['status'] = 'no_supplementary'                              #changed_10042026
            return result                                                      #changed_10042026
                                                                               #changed_10042026
        logging.info(                                                          #changed_10042026
            f"{pmcid}: {len(supp_urls)} supplementary files "                  #changed_10042026
            f"(of {len(media_urls)} total media) to download"                  #changed_10042026
        )                                                                      #changed_10042026
                                                                               #changed_10042026
        # 4. Download each supplementary file                                 #changed_10042026
        output_dir.mkdir(parents=True, exist_ok=True)                          #changed_10042026
        downloaded_files = []                                                  #changed_10042026
                                                                               #changed_10042026
        for s3_url in supp_urls:                                               #changed_10042026
            raw_path = s3_url.split("?")[0]                                    #changed_10042026
            filename = Path(raw_path).name                                     #changed_10042026
            https_url = _s3_url_to_https(s3_url)                               #changed_10042026
                                                                               #changed_10042026
            time.sleep(cfg.PMC_RATE_LIMIT_DELAY)                               #changed_10042026
            file_response = requests.get(https_url, timeout=60, stream=True)   #changed_10042026
                                                                               #changed_10042026
            if file_response.status_code == 200:                               #changed_10042026
                safe_name = sanitise_filename(filename)                        #changed_10042026
                save_path = _resolve_duplicate_path(output_dir / safe_name)    #changed_10042026
                safe_name = save_path.name                                     #changed_10042026
                                                                               #changed_10042026
                with open(save_path, 'wb') as f:                               #changed_10042026
                    for chunk in file_response.iter_content(chunk_size=8192):   #changed_10042026
                        if chunk:                                              #changed_10042026
                            f.write(chunk)                                     #changed_10042026
                                                                               #changed_10042026
                file_size = save_path.stat().st_size                           #changed_10042026
                file_info = {                                                  #changed_10042026
                    'original_name': filename,                                 #changed_10042026
                    'saved_as': safe_name,                                     #changed_10042026
                    'extension': Path(filename).suffix,                        #changed_10042026
                    'size_bytes': file_size,                                   #changed_10042026
                    's3_url': s3_url                                           #changed_10042026
                }                                                              #changed_10042026
                downloaded_files.append(file_info)                             #changed_10042026
                logging.debug(f"Downloaded: {filename} -> {safe_name}")        #changed_10042026
            else:                                                              #changed_10042026
                logging.warning(                                               #changed_10042026
                    f"Failed to download {filename} for {pmcid}: "             #changed_10042026
                    f"HTTP {file_response.status_code}"                        #changed_10042026
                )                                                              #changed_10042026
                                                                               #changed_10042026
        # 5. Write manifest                                                   #changed_10042026
        manifest = {                                                           #changed_10042026
            'pmcid': pmcid,                                                    #changed_10042026
            'version': version,                                                #changed_10042026
            'download_date': datetime.now().strftime('%Y%m%d_%H%M%S'),         #changed_10042026
            'download_status': 'success',                                      #changed_10042026
            'source': 'aws_s3',                                                #changed_10042026
            'license': metadata.get('license_code'),                           #changed_10042026
            'files_count': len(downloaded_files),                              #changed_10042026
            'files': downloaded_files                                          #changed_10042026
        }                                                                      #changed_10042026
                                                                               #changed_10042026
        with open(manifest_path, 'w', encoding='utf-8') as f:                 #changed_10042026
            json.dump(manifest, f, indent=2)                                   #changed_10042026
                                                                               #changed_10042026
        result['status'] = 'success'                                           #changed_10042026
        result['files_downloaded'] = downloaded_files                          #changed_10042026
        result['manifest'] = manifest                                          #changed_10042026
        logging.info(                                                          #changed_10042026
            f"Downloaded {len(downloaded_files)} supplementary files "         #changed_10042026
            f"for {pmcid}"                                                     #changed_10042026
        )                                                                      #changed_10042026
                                                                               #changed_10042026
    except Exception as e:                                                     #changed_10042026
        logging.error(                                                         #changed_10042026
            f"Failed to download supplementary for {pmcid}: {str(e)}"          #changed_10042026
        )                                                                      #changed_10042026
        if retry_count < max_retries:                                          #changed_10042026
            logging.info(f"Retrying {pmcid} (attempt {retry_count + 1})")      #changed_10042026
            time.sleep(cfg.PMC_RATE_LIMIT_DELAY * 2)                           #changed_10042026
            return download_supplementary_s3(pmcid, version,                   #changed_10042026
                                              retry_count + 1)                 #changed_10042026
        result['status'] = 'failed'                                            #changed_10042026
        result['error'] = str(e)                                               #changed_10042026
                                                                               #changed_10042026
    return result                                                              #changed_10042026


def batch_download_supplementary(pmcid_list: List[str]) -> Optional[Dict]:
    """Download supplementary files for a list of PMCIDs via AWS S3.            #changed_10042026

    v3.3: Uses S3 HTTPS metadata lookup instead of FTP tarball download.       #changed_10042026
    No OA file list download or AWS account/CLI required.                      #changed_10042026
    """                                                                        #changed_10042026
    stats = {
        'total': len(pmcid_list),
        'success': 0,
        'skipped': 0,
        'not_found': 0,                                                        #changed_10042026
        'failed': 0,
        'no_supplementary': 0,
        'total_files_downloaded': 0                                            #changed_10042026
    }

    Path(cfg.SUPPLEMENTARY_PATH).mkdir(parents=True, exist_ok=True)
    logging.info("Starting supplementary download via AWS S3...")               #changed_10042026

    for idx, pmcid in enumerate(pmcid_list, 1):
        pmcid_upper = pmcid.strip().upper()
        if not pmcid_upper.startswith('PMC'):
            pmcid_upper = f"PMC{pmcid_upper}"

        if idx % 10 == 0:
            logging.info(f"Supplementary download progress: {idx}/{len(pmcid_list)}")
            logging.info(f"  Current stats - Success: {stats['success']}, "
                         f"Not found: {stats['not_found']}, "                  #changed_10042026
                         f"Failed: {stats['failed']}")

        result = download_supplementary_s3(pmcid_upper)                        #changed_10042026

        if result['status'] == 'success':
            files_count = len(result['files_downloaded'])                       #changed_10042026
            if files_count > 0:
                stats['success'] += 1
                stats['total_files_downloaded'] += files_count                 #changed_10042026
            else:
                stats['no_supplementary'] += 1

        elif result['status'] == 'skipped':
            stats['skipped'] += 1
            if result['manifest'] and 'files_count' in result['manifest']:
                stats['total_files_downloaded'] += result['manifest']['files_count']  #changed_10042026

        elif result['status'] == 'not_found':                                  #changed_10042026
            stats['not_found'] += 1                                            #changed_10042026

        elif result['status'] == 'no_supplementary':                           #changed_10042026
            stats['no_supplementary'] += 1                                     #changed_10042026

        else:
            stats['failed'] += 1

    logging.info("=" * 60)
    logging.info("SUPPLEMENTARY DOWNLOAD COMPLETE")
    logging.info("=" * 60)
    logging.info(f"Total PMCIDs processed: {stats['total']}")
    logging.info(f"Success (with files): {stats['success']}")
    logging.info(f"Skipped (already downloaded): {stats['skipped']}")
    logging.info(f"Not found on S3: {stats['not_found']}")                     #changed_10042026
    logging.info(f"No supplementary files: {stats['no_supplementary']}")
    logging.info(f"Failed: {stats['failed']}")
    logging.info(f"Total supplementary files downloaded: {stats['total_files_downloaded']}")  #changed_10042026
    logging.info("=" * 60)

    return stats


# =============================================================================
# SEARCH & DOWNLOAD (Option 1 / Option 3)
# =============================================================================

def search_and_download_articles(pathogen_key: str, date_start: str = None,
                                  date_end: str = None,
                                  interactive_mode: bool = False,
                                  download_supp: bool = True) -> pd.DataFrame:
    """Main function to search and download articles for single pathogen."""

    if date_start is None or date_end is None:
        date_start, date_end = get_previous_month_date_range()

    logging.info(f"Starting search for {cfg.PATHOGENS[pathogen_key]['name']}")
    logging.info(f"Date range: {date_start} to {date_end}")

    search_query = build_pathogen_search_query(pathogen_key)
    tracking_df = load_tracking_data()

    search_url = construct_esearch_url(
        database=DATABASE,
        term=search_query,
        mindate=date_start,
        maxdate=date_end,
        datetype='pdat',
        retmax='100',
        usehistory=USE_HISTORY
    )

    try:
        logging.info("Executing PubMed search...")
        response = make_http_request(search_url)
        time.sleep(cfg.RATE_LIMIT_DELAY)

        total_count = extract_total_count(response)
        pmid_list = extract_pmid_list(response)

        logging.info(f"Found {total_count} total articles, retrieved {len(pmid_list)} PMIDs")

        if interactive_mode:
            print(f"\n{'='*60}")
            print(f"SEARCH RESULTS")
            print(f"{'='*60}")
            print(f"Total articles matching criteria: {total_count}")
            print(f"Articles to be downloaded: {len(pmid_list)}")
            print(f"Date range: {date_start} to {date_end}")
            print(f"{'='*60}\n")

        if not pmid_list:
            logging.warning("No articles found for the specified criteria")
            return tracking_df

        logging.info("STEP 2: Converting PMIDs to PMCIDs...")
        pmid_to_pmcid_map, missing_pmcid_list = batch_convert_pmids_to_pmcids(pmid_list)

        for pmid in missing_pmcid_list:
            tracking_df = track_missing_pmcid(tracking_df, pmid, "No PMC version available")

        if interactive_mode:
            conversion_rate = len(pmid_to_pmcid_map) / len(pmid_list) * 100 if pmid_list else 0
            print(f"\nConversion Results:")
            print(f"  Success: {len(pmid_to_pmcid_map)}/{len(pmid_list)} ({conversion_rate:.1f}%)")
            print(f"  Missing: {len(missing_pmcid_list)}")
            print()

        logging.info("STEP 3: Fetching full-text XML from PMC...")

        success_count = 0
        failed_count = 0
        total_fetch = len(pmid_to_pmcid_map)

        for i, (pmid, pmcid) in enumerate(pmid_to_pmcid_map.items(), 1):

            if pmcid in tracking_df['pmcid'].values:
                existing_record = tracking_df[tracking_df['pmcid'] == pmcid].iloc[0]  #changed_08042026
                if existing_record['fulltext_xml_status'] == 'success':
                    logging.info(f"Skipping {pmcid} - already processed")
                    success_count += 1
                    continue

            fulltext_xml = fetch_pmc_fulltext_xml(pmcid)

            if fulltext_xml:
                batch_date = datetime.now().strftime('%Y%m%d')
                xml_success = save_xml_with_compression(fulltext_xml, pmcid, batch_date)

                if xml_success:
                    tracking_df = update_tracking_data(
                        df=tracking_df,
                        pmid=pmid,
                        pmcid=pmcid,
                        pmcid_status='success',
                        fulltext_xml_status='success',
                        error_message=None
                    )
                    success_count += 1
                    logging.info(f"Successfully saved full-text for {pmcid}")
                else:
                    tracking_df = update_tracking_data(
                        df=tracking_df,
                        pmid=pmid,
                        pmcid=pmcid,
                        pmcid_status='found',
                        fulltext_xml_status='failed',
                        error_message='XML save failed'
                    )
                    failed_count += 1
            else:
                tracking_df = update_tracking_data(
                    df=tracking_df,
                    pmid=pmid,
                    pmcid=pmcid,
                    pmcid_status='fetch_failed',
                    fulltext_xml_status='failed',
                    error_message='Full-text XML not available from PMC'
                )
                failed_count += 1
                logging.error(f"Failed to save full-text for {pmcid}")

            time.sleep(cfg.RATE_LIMIT_DELAY)

            if i % 10 == 0:
                save_tracking_data(tracking_df)
                logging.info(f"Progress saved: {i}/{total_fetch} processed")

        save_tracking_data(tracking_df)

        logging.info("Step 4: Downloading supplementary files...")
        if download_supp:  #changed_08042026
            successful_pmcids = list(pmid_to_pmcid_map.values())
            supp_stats = batch_download_supplementary(successful_pmcids)
        else:  #changed_08042026
            logging.info("Supplementary download skipped (download_supp=False)")  #changed_08042026
            supp_stats = {'success': 0, 'failed': 0, 'not_found': 0}  #changed_10042026

        logging.info(f"Processing complete:")
        logging.info(f"  Full-text XML success: {success_count}")
        logging.info(f"  Full-text XML failed: {failed_count}")
        logging.info(f"  Missing PMCIDs: {len(missing_pmcid_list)}")
        logging.info(f"  Supp success: {supp_stats['success']}")
        logging.info(f"  Supp failed: {supp_stats['failed']}")
        logging.info(f"  Supp not found on S3: {supp_stats['not_found']}")    #changed_10042026

        generate_download_summary(tracking_df, date_start, date_end)
        return tracking_df

    except Exception as e:
        logging.error(f"Search and download failed: {str(e)}")
        save_tracking_data(tracking_df)
        raise


# =============================================================================
# BATCH PMCID DOWNLOAD (Option 2 - v3.3)
# =============================================================================

def download_batch_pmcid_xml(csv_path: str = None) -> Optional[Dict]:  #changed - core v3.3 function
    """
    Download full-text XML and supplementary files for PMCIDs.

    PMCIDs are loaded from a CSV file (v3.3 default) or, for backward
    compatibility, from JSON filenames in the ground_truth directory.

    Args:
        csv_path: Path to CSV file containing PMCIDs.
                  If None, falls back to scanning cfg.GROUND_TRUTH_PATH.

    Returns:
        Summary dict with success/failure counts.
    """
    OUTPUT_PATH = Path(cfg.XML_PATH) / "ground_truth"
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    success_count = 0
    skipped_count = 0
    failed_count = 0
    failed_pmcids = []

    # Step 1: Load PMCIDs
    if csv_path is not None:  #changed - CSV-based loading
        logging.info(f"Step 1: Loading PMCIDs from CSV file: {csv_path}")
        try:
            pmcid_list = load_pmcids_from_csv(csv_path)
        except (FileNotFoundError, ValueError) as e:
            logging.error(f"Failed to load CSV: {e}")
            print(f"Error: {e}")
            return None
    else:  #changed - backward compatibility fallback
        logging.info(f"Step 1: No CSV provided - falling back to directory scan of {cfg.GROUND_TRUTH_PATH}")
        pmcid_list = collect_pmcids_from_directory(directory=cfg.GROUND_TRUTH_PATH)

    if not pmcid_list:
        logging.error("No PMCIDs to process")
        return None

    logging.info(f"Total PMCIDs to process: {len(pmcid_list)}")
    print(f"\nPMCIDs to process: {len(pmcid_list)}")

    # Step 2: Download full-text XML
    logging.info("PHASE 1: Downloading full-text XML from PMC...")

    for idx, pmcid in enumerate(pmcid_list, 1):
        if idx % 10 == 0:
            logging.info(f"Progress: {idx}/{len(pmcid_list)}")

        # Check if XML already exists (plain or compressed)
        gt_filename_pattern = f"{pmcid}*.xml"
        gz_filename_pattern = f"{pmcid}*.xml.gz"
        xml_match = next(OUTPUT_PATH.glob(gt_filename_pattern), None)  #changed - also check .gz
        gz_match = next(OUTPUT_PATH.glob(gz_filename_pattern), None)  #changed

        if xml_match or gz_match:
            logging.info(f"Skipping {pmcid} - already processed")
            skipped_count += 1
            continue

        xml_content = fetch_pmc_fulltext_xml(pmcid)

        if xml_content is not None:
            batch_date = datetime.now().strftime('%Y%m%d')
            save_success = save_xml_with_compression(xml_content, pmcid, batch_date)

            if save_success:
                success_count += 1
            else:
                failed_count += 1
                failed_pmcids.append(pmcid)
        else:
            failed_count += 1
            failed_pmcids.append(pmcid)
            logging.error(f"Failed to fetch XML for {pmcid}")

    # Step 3: Download supplementary files
    logging.info("PHASE 2: Downloading supplementary files from AWS S3...")    #changed_10042026
    success_pmcid = [pmcid for pmcid in pmcid_list if pmcid not in failed_pmcids]
    supp_stats = batch_download_supplementary(success_pmcid)

    summary = {
        'total': len(pmcid_list),
        'xml_success': success_count,
        'xml_skipped': skipped_count,
        'xml_failed': failed_count,
        'failed_pmcids': failed_pmcids,  #changed - include failed list in summary
        'supp_success': supp_stats['success'],
        'supp_skipped': supp_stats['skipped'],
        'supp_not_found': supp_stats['not_found'],                             #changed_10042026
        'supp_failed': supp_stats['failed'],
    }

    return summary


# =============================================================================
# SUMMARY PRINTING
# =============================================================================

def print_batch_summary(summary):  #changed - extracted summary printing
    """Print download summary for batch PMCID mode."""
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"Total PMCIDs processed: {summary['total']}")
    print(f"Successfully downloaded: {summary['xml_success']}")
    print(f"Skipped (already exist): {summary['xml_skipped']}")
    print(f"Failed: {summary['xml_failed']}")
    print()
    print(f"SUPPLEMENTARY FILES:")
    print(f"  Successfully downloaded: {summary['supp_success']}")
    print(f"  Skipped (already exist): {summary['supp_skipped']}")
    print(f"  Not found on S3: {summary['supp_not_found']}")                   #changed_10042026
    print(f"  Failed: {summary['supp_failed']}")

    if summary['xml_failed'] > 0:
        print(f"\nFailed PMCIDs: {summary['failed_pmcids']}")


# =============================================================================
# ARGPARSE CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='pubmed_extract_v3_3',
        description='PubMed Article Downloader v3.3 - Download full-text XML and supplementary files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive search by pathogen and month
  python pubmed_extract_v3_3.py interactive --month June --year 2025

  # Batch download from PMCID list in CSV
  python pubmed_extract_v3_3.py batch --csv pmcid_list.csv

  # Scheduled mode (downloads previous month automatically)
  python pubmed_extract_v3_3.py scheduled

  # Override base directory and API key
  python pubmed_extract_v3_3.py batch --csv ids.csv --base-dir /data/pubmed --api-key YOUR_KEY

  # Custom output directories for XML and supplementary files
  python pubmed_extract_v3_3.py interactive --month June --year 2025 --xml-dir /data/xml --supp-dir /data/supp
        """
    )

    # Global arguments
    parser.add_argument('--base-dir', type=str,
                        default=cfg.DRIVE_BASE,  #changed - use config default
                        help='Base directory for all output (default: from config.py or $PUBMED_BASE_DIR)')
    parser.add_argument('--api-key', type=str, default=None,
                        help='NCBI API key (default: $cfg.NCBI_API_KEY env var)')
    parser.add_argument('--xml-dir', type=str, default=None,  #changed_08042026
                        help='Custom output directory for downloaded XML files (default: from config.py)')
    parser.add_argument('--supp-dir', type=str, default=None,  #changed_08042026
                        help='Custom output directory for supplementary files (default: from config.py)')

    subparsers = parser.add_subparsers(dest='mode', help='Execution mode')

    # Option 1: Interactive
    interactive_parser = subparsers.add_parser('interactive',
                                                help='Search by pathogen and date range')
    interactive_parser.add_argument('--month', type=str, required=True,
                                    help='Month name or number (e.g. June, Jun, 6)')
    interactive_parser.add_argument('--year', type=int, default=None,
                                    help='Year (default: current year)')
    interactive_parser.add_argument('--pathogen', type=str, default='hepatitis_a',
                                    choices=list(cfg.PATHOGENS.keys()),
                                    help='Pathogen to search (default: hepatitis_a)')

    # Option 2: Batch PMCID download
    batch_parser = subparsers.add_parser('batch',
                                          help='Download XML + supplementary from PMCID list in CSV')
    batch_parser.add_argument('--csv', type=str, required=True,
                              help='Path to CSV file containing PMCIDs')

    # Option 3: Scheduled
    scheduled_parser = subparsers.add_parser('scheduled',
                                              help='Download previous month (for cron/scheduled use)')
    scheduled_parser.add_argument('--pathogen', type=str, default='hepatitis_a',
                                   choices=list(cfg.PATHOGENS.keys()),
                                   help='Pathogen to search (default: hepatitis_a)')

    return parser


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        sys.exit(1)

    # Initialise paths and API key
    initialise_paths(args.base_dir)
    initialise_api_key(args.api_key)

    # Override output directories if custom paths provided  #changed_08042026
    if args.xml_dir is not None:  #changed_08042026
        cfg.XML_PATH = args.xml_dir  #changed_08042026
        logging.info(f"Custom XML output directory: {cfg.XML_PATH}")  #changed_08042026
    if args.supp_dir is not None:  #changed_08042026
        cfg.SUPPLEMENTARY_PATH = args.supp_dir  #changed_08042026
        logging.info(f"Custom supplementary output directory: {cfg.SUPPLEMENTARY_PATH}")  #changed_08042026

    # Initialise logging and directories
    setup_logging()
    logging.info("Starting main execution")
    logging.info("PubMed Article Downloader v3.3 (CLI)")
    check_project_dir()

    try:
        if args.mode == 'interactive':
            date_start, date_end = parse_month_input(args.month, args.year)
            logging.info(f"Interactive mode: {args.pathogen}, {date_start} to {date_end}")

            tracking_df = search_and_download_articles(
                args.pathogen,
                date_start=date_start,
                date_end=date_end,
                interactive_mode=True
            )
            print("\nInteractive download complete")
            print(f"Check {cfg.LOG_PATH} for detailed logs and summaries")

        elif args.mode == 'batch':
            logging.info(f"Batch PMCID mode (CSV: {args.csv})")
            summary = download_batch_pmcid_xml(csv_path=args.csv)

            if summary is not None:
                print_batch_summary(summary)

        elif args.mode == 'scheduled':
            logging.info(f"Scheduled mode: {args.pathogen}")
            tracking_df = search_and_download_articles(args.pathogen)

        logging.info("All processing complete")

    except Exception as e:
        logging.error(f"Main execution failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
