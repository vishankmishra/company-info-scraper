#!/usr/bin/env python3
"""
Batch Raw Text Scraper - Decoupled from LLM Processing

Phase 5 Bulletproof: 
- Contact extraction with word-boundary regex (no false positives)
- Social link extraction (LinkedIn, Twitter/X, Facebook)
- Leadership page content preservation in raw_text

Usage:
    python batch_scrape_raw.py
    python batch_scrape_raw.py --output raw_scrape_output.csv
    python batch_scrape_raw.py --format jsonl --output raw_scrape_output.jsonl
    python batch_scrape_raw.py --domain example.com  # Single domain test

Output fields:
    - domain: Original domain input
    - final_url: The final URL after redirects
    - raw_text: Extracted text content (includes leadership page content)
    - scrape_status: "success" or "failed"
    - error: Error message if failed
    - pages_scraped: Number of pages scraped from this domain
    - emails: List of extracted emails with type labels
    - phones: List of extracted phones with type labels
    - social_links: List of social media profile URLs
    - leadership_url: URL identified as team/about page
"""

import sys
import os
import argparse
import subprocess
import json
import tempfile
import csv
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# Hardcoded domains list
DOMAINS = [
    "dduh.in",
    "logisall.in",
    "saanikaindustries.com",
    "quantysclinical.com",
    "msi-dev.azurewebsites.net",
    "allindiatpt.com",
    "koshys.com",
    "quickindialogistics.com",
    "omhousehold.com",
    "packtogo.in",
    "agarwalsinc.com",
    "hypernxt.com",
    "htips.in",
    "bontonholidays.com",
    "hindheaters.com",
    "roboticequipments.com",
    "canvera.com",
    "jimsh.org",
    "mandmlegal.co.in",
    "ironmansecurity.in",
    "anandaashram.co.in",
    "bindassbasket.com",
    "chaarvievents.com",
    "anpg.in",
    "leotradeandtours.com",
    "kabraexpress.com",
]


@dataclass
class ScrapeResult:
    """Result of scraping a single domain."""
    domain: str
    final_url: str = ""
    raw_text: str = ""
    scrape_status: str = "pending"
    error: str = ""
    pages_scraped: int = 0
    scrape_time_seconds: float = 0.0
    # Phase 5 Bulletproof: Contact info fields
    emails: List[Dict] = field(default_factory=list)
    phones: List[Dict] = field(default_factory=list)
    social_links: List[str] = field(default_factory=list)
    leadership_url: str = ""


def get_venv_python() -> str:
    """Get the path to the venv Python interpreter."""
    project_root = Path(__file__).parent
    venv_paths = [
        project_root / "venv" / "bin" / "python",
        project_root / ".venv" / "bin" / "python",
        project_root / "venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "Scripts" / "python.exe",
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            return str(venv_path)
    
    return sys.executable


def scrape_domain_subprocess(domain: str, timeout: int = 120) -> ScrapeResult:
    """
    Scrape a single domain using Playwright spider in isolated subprocess.
    
    Args:
        domain: Domain to scrape (e.g., 'example.com')
        timeout: Subprocess timeout in seconds
        
    Returns:
        ScrapeResult with raw text, contacts, socials, and status
    """
    start_time = time.time()
    result = ScrapeResult(domain=domain)
    
    python_executable = get_venv_python()
    
    result_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    result_file_path = result_file.name
    result_file.close()
    
    script_content = f'''
import sys
import os
import json

project_root = "{os.getcwd()}"
sys.path.insert(0, project_root)

if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from company_info_scraper.spiders.scraper import FullPageSpider
from scrapy import signals

settings = get_project_settings()

settings.set('ITEM_PIPELINES', {{
    'company_info_scraper.pipelines.CompanyInfoScraperPipeline': 300
}})
settings.set('FEED_URI', None)
settings.set('LOG_LEVEL', 'INFO')
settings.set('ROBOTSTXT_OBEY', False)

spider_ref = [None]

def crawler_started(spider):
    spider_ref[0] = spider

process = CrawlerProcess(settings)
process.crawl(FullPageSpider, domain="{domain}")

if process.crawlers:
    crawler = list(process.crawlers)[-1]
    crawler.signals.connect(crawler_started, signal=signals.spider_opened)

try:
    process.start()
except Exception as e:
    print(f"Crawler error: {{e}}", file=sys.stderr)

items = []
final_url = ""
all_emails = []
all_phones = []
all_social_links = []
leadership_url = ""
combined_raw_text = ""

if spider_ref[0]:
    items = getattr(spider_ref[0], 'collected_items', [])
    if items:
        final_url = items[0].get('url', '')
    
    # Phase 5 Bulletproof: Get aggregated data from spider
    all_emails = getattr(spider_ref[0], 'all_emails', [])
    all_phones = getattr(spider_ref[0], 'all_phones', [])
    all_social_links = list(getattr(spider_ref[0], 'all_social_links', set()))
    leadership_url = getattr(spider_ref[0], 'leadership_url', '') or ''
    combined_raw_text = getattr(spider_ref[0], 'combined_raw_text', '')

# Deduplicate contacts
def dedupe_contacts(contacts):
    best = {{}}
    for c in contacts:
        v = c.get('value', '')
        t = c.get('type', 'Generic')
        if v not in best:
            best[v] = c
        elif t != 'Generic' and best[v].get('type') == 'Generic':
            best[v] = c
    return list(best.values())

result = {{
    'success': len(items) > 0 or len(combined_raw_text) > 0,
    'final_url': final_url,
    'raw_text': combined_raw_text.strip(),
    'pages_scraped': len(items) if items else (1 if combined_raw_text else 0),
    'emails': dedupe_contacts(all_emails),
    'phones': dedupe_contacts(all_phones),
    'social_links': sorted(list(set(all_social_links))),
    'leadership_url': leadership_url
}}

with open(r"{result_file_path}", 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)
'''
    
    script_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    script_file.write(script_content)
    script_file.close()
    
    try:
        logger.info(f"[{domain}] Starting Playwright scraper...")
        
        proc_result = subprocess.run(
            [python_executable, script_file.name],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        elapsed = time.time() - start_time
        result.scrape_time_seconds = round(elapsed, 2)
        
        if proc_result.returncode != 0:
            result.scrape_status = "failed"
            result.error = f"Subprocess error: {proc_result.stderr[:500]}"
            logger.error(f"[{domain}] Failed: {result.error[:100]}...")
            return result
        
        if os.path.exists(result_file_path):
            with open(result_file_path, 'r', encoding='utf-8') as f:
                subprocess_result = json.load(f)
            
            if subprocess_result.get('success'):
                result.scrape_status = "success"
                result.final_url = subprocess_result.get('final_url', '')
                result.raw_text = subprocess_result.get('raw_text', '')
                result.pages_scraped = subprocess_result.get('pages_scraped', 0)
                result.emails = subprocess_result.get('emails', [])
                result.phones = subprocess_result.get('phones', [])
                result.social_links = subprocess_result.get('social_links', [])
                result.leadership_url = subprocess_result.get('leadership_url', '')
                
                # Detailed logging
                email_count = len(result.emails)
                phone_count = len(result.phones)
                social_count = len(result.social_links)
                raw_text_len = len(result.raw_text)
                
                logger.info(
                    f"[{domain}] ✓ Success: {result.pages_scraped} pages, "
                    f"{raw_text_len:,} chars, {email_count} emails, {phone_count} phones, "
                    f"{social_count} socials in {elapsed:.1f}s"
                )
                if result.leadership_url:
                    logger.info(f"[{domain}]   🏢 Leadership URL: {result.leadership_url}")
                if result.social_links:
                    logger.info(f"[{domain}]   🔗 Social Links: {result.social_links[:3]}")
            else:
                result.scrape_status = "failed"
                result.error = "No content extracted"
                logger.warning(f"[{domain}] ✗ No content extracted")
        else:
            result.scrape_status = "failed"
            result.error = "No result file generated"
            logger.error(f"[{domain}] ✗ No result file")
            
    except subprocess.TimeoutExpired:
        result.scrape_status = "failed"
        result.error = f"Timeout after {timeout}s"
        result.scrape_time_seconds = timeout
        logger.error(f"[{domain}] ✗ Timeout after {timeout}s")
        
    except Exception as e:
        result.scrape_status = "failed"
        result.error = str(e)
        result.scrape_time_seconds = round(time.time() - start_time, 2)
        logger.error(f"[{domain}] ✗ Error: {e}")
        
    finally:
        try:
            os.unlink(script_file.name)
        except Exception:
            pass
        try:
            if os.path.exists(result_file_path):
                os.unlink(result_file_path)
        except Exception:
            pass
    
    return result


def save_results_csv(results: List[ScrapeResult], output_file: str) -> None:
    """Save results to CSV file."""
    fieldnames = [
        'domain', 'final_url', 'raw_text', 'scrape_status', 'error', 
        'pages_scraped', 'scrape_time_seconds',
        'emails', 'phones', 'social_links', 'leadership_url'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row['emails'] = json.dumps(row['emails'], ensure_ascii=False)
            row['phones'] = json.dumps(row['phones'], ensure_ascii=False)
            row['social_links'] = json.dumps(row['social_links'], ensure_ascii=False)
            writer.writerow(row)
    
    logger.info(f"Results saved to: {output_file}")


def save_results_jsonl(results: List[ScrapeResult], output_file: str) -> None:
    """Save results to JSONL file (one JSON object per line)."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(asdict(result), ensure_ascii=False) + '\n')
    
    logger.info(f"Results saved to: {output_file}")


def run_batch_scrape(
    domains: List[str],
    output_file: str = "raw_scrape_output.csv",
    output_format: str = "csv",
    timeout_per_domain: int = 120
) -> Dict[str, Any]:
    """Run batch scraping for multiple domains."""
    total_domains = len(domains)
    results: List[ScrapeResult] = []
    
    logger.info("=" * 70)
    logger.info("BATCH RAW TEXT SCRAPER (Phase 5 Bulletproof)")
    logger.info("=" * 70)
    logger.info(f"Features: Word-boundary regex, Social extraction, Leadership preservation")
    logger.info(f"Domains to scrape: {total_domains}")
    logger.info(f"Output: {output_file} ({output_format})")
    logger.info(f"Timeout per domain: {timeout_per_domain}s")
    logger.info("=" * 70)
    
    start_time = time.time()
    
    for i, domain in enumerate(domains, 1):
        logger.info(f"\n[{i}/{total_domains}] Processing: {domain}")
        result = scrape_domain_subprocess(domain, timeout=timeout_per_domain)
        results.append(result)
    
    total_time = time.time() - start_time
    
    if output_format == "jsonl":
        save_results_jsonl(results, output_file)
    else:
        save_results_csv(results, output_file)
    
    # Statistics
    successful = sum(1 for r in results if r.scrape_status == "success")
    failed = total_domains - successful
    total_pages = sum(r.pages_scraped for r in results)
    total_chars = sum(len(r.raw_text) for r in results)
    total_emails = sum(len(r.emails) for r in results)
    total_phones = sum(len(r.phones) for r in results)
    total_socials = sum(len(r.social_links) for r in results)
    leadership_found = sum(1 for r in results if r.leadership_url)
    
    logger.info("\n" + "=" * 70)
    logger.info("BATCH SCRAPING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total domains: {total_domains}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total pages scraped: {total_pages}")
    logger.info(f"Total characters: {total_chars:,}")
    logger.info(f"Total emails extracted: {total_emails}")
    logger.info(f"Total phones extracted: {total_phones}")
    logger.info(f"Total social links: {total_socials}")
    logger.info(f"Leadership pages found: {leadership_found}")
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Average time per domain: {total_time/total_domains:.1f}s")
    logger.info(f"\nOutput saved to: {output_file}")
    logger.info("=" * 70)
    
    if failed > 0:
        logger.info("\nFailed domains:")
        for r in results:
            if r.scrape_status == "failed":
                logger.info(f"  - {r.domain}: {r.error[:80]}")
    
    return {
        'total_domains': total_domains,
        'successful': successful,
        'failed': failed,
        'total_pages': total_pages,
        'total_chars': total_chars,
        'total_emails': total_emails,
        'total_phones': total_phones,
        'total_socials': total_socials,
        'leadership_found': leadership_found,
        'total_time_seconds': round(total_time, 2),
        'output_file': output_file
    }


def main():
    parser = argparse.ArgumentParser(
        description='Batch Raw Text Scraper - Phase 5 Bulletproof Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python batch_scrape_raw.py
    python batch_scrape_raw.py --domain bontonholidays.com --format jsonl
    python batch_scrape_raw.py --format jsonl --output output.jsonl
    python batch_scrape_raw.py --timeout 180
"""
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='raw_scrape_output.csv',
        help='Output file path (default: raw_scrape_output.csv)'
    )
    
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['csv', 'jsonl'],
        default='csv',
        help='Output format: csv or jsonl (default: csv)'
    )
    
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=120,
        help='Timeout per domain in seconds (default: 120)'
    )
    
    parser.add_argument(
        '--domains-file',
        type=str,
        help='Read domains from file instead of using hardcoded list'
    )
    
    parser.add_argument(
        '--domain', '-d',
        type=str,
        help='Scrape a single domain (for testing)'
    )
    
    args = parser.parse_args()
    
    if args.domain:
        domains = [args.domain]
    elif args.domains_file:
        if not os.path.exists(args.domains_file):
            logger.error(f"Domains file not found: {args.domains_file}")
            return 1
        with open(args.domains_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        domains = DOMAINS
    
    if not domains:
        logger.error("No domains to scrape")
        return 1
    
    output_file = args.output
    if args.format == 'jsonl' and not output_file.endswith('.jsonl'):
        output_file = output_file.rsplit('.', 1)[0] + '.jsonl'
    elif args.format == 'csv' and not output_file.endswith('.csv'):
        output_file = output_file.rsplit('.', 1)[0] + '.csv'
    
    summary = run_batch_scrape(
        domains=domains,
        output_file=output_file,
        output_format=args.format,
        timeout_per_domain=args.timeout
    )
    
    if summary['failed'] == 0:
        return 0
    elif summary['successful'] > 0:
        return 2
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
