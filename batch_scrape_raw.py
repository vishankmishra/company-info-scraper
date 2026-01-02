#!/usr/bin/env python3
"""
Batch Raw Text Scraper - Decoupled from LLM Processing

This script scrapes domains using the existing Playwright spider and outputs
raw text only (no LLM extraction). The output can be used for offline LLM testing.

Usage:
    python batch_scrape_raw.py
    python batch_scrape_raw.py --output raw_scrape_output.csv
    python batch_scrape_raw.py --format jsonl --output raw_scrape_output.jsonl

Output fields:
    - domain: Original domain input
    - final_url: The final URL after redirects
    - raw_text: Extracted text content
    - scrape_status: "success" or "failed"
    - error: Error message if failed
    - pages_scraped: Number of pages scraped from this domain
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


# Hardcoded domains list (as specified in task)
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


def get_venv_python() -> str:
    """Get the path to the venv Python interpreter."""
    # Check common venv locations
    project_root = Path(__file__).parent
    venv_paths = [
        project_root / "venv" / "bin" / "python",
        project_root / ".venv" / "bin" / "python",
        project_root / "venv" / "Scripts" / "python.exe",  # Windows
        project_root / ".venv" / "Scripts" / "python.exe",  # Windows
    ]
    
    for venv_path in venv_paths:
        if venv_path.exists():
            return str(venv_path)
    
    # Fallback to current Python
    return sys.executable


def scrape_domain_subprocess(domain: str, timeout: int = 120) -> ScrapeResult:
    """
    Scrape a single domain using Playwright spider in isolated subprocess.
    
    This reuses the existing ScrapingAgent subprocess pattern to avoid
    reactor conflicts.
    
    Args:
        domain: Domain to scrape (e.g., 'example.com')
        timeout: Subprocess timeout in seconds
        
    Returns:
        ScrapeResult with raw text and status
    """
    start_time = time.time()
    result = ScrapeResult(domain=domain)
    
    # Get the correct Python interpreter (from venv)
    python_executable = get_venv_python()
    
    # Create domain-specific result file
    result_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    result_file_path = result_file.name
    result_file.close()
    
    # Create subprocess script that runs the Playwright spider
    # This is adapted from ScrapingAgent._run_crawler
    script_content = f'''
import sys
import os
import json

# Add project root to path
project_root = "{os.getcwd()}"
sys.path.insert(0, project_root)

# Install reactor BEFORE any Twisted imports
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from company_info_scraper.spiders.scraper import FullPageSpider
from scrapy import signals

# Get settings
settings = get_project_settings()

# Disable pipelines - we only want raw text, no LLM processing
settings.set('ITEM_PIPELINES', {{
    'company_info_scraper.pipelines.CompanyInfoScraperPipeline': 300
}})
settings.set('FEED_URI', None)
settings.set('LOG_LEVEL', 'INFO')
settings.set('ROBOTSTXT_OBEY', False)

# Spider reference container
spider_ref = [None]

def crawler_started(spider):
    spider_ref[0] = spider

# Create process and crawl
process = CrawlerProcess(settings)
process.crawl(FullPageSpider, domain="{domain}")

if process.crawlers:
    crawler = list(process.crawlers)[-1]
    crawler.signals.connect(crawler_started, signal=signals.spider_opened)

try:
    process.start()
except Exception as e:
    print(f"Crawler error: {{e}}", file=sys.stderr)

# Collect results
items = []
final_url = ""
if spider_ref[0] and hasattr(spider_ref[0], 'collected_items'):
    items = spider_ref[0].collected_items
    # Get the first URL as the final_url (homepage after redirects)
    if items:
        final_url = items[0].get('url', '')

# Combine all raw text from all pages
combined_text = ""
for item in items:
    text = item.get('raw_text', '')
    if text:
        combined_text += f"\\n\\n--- PAGE: {{item.get('url', 'unknown')}} ---\\n\\n"
        combined_text += text

result = {{
    'success': len(items) > 0,
    'final_url': final_url,
    'raw_text': combined_text.strip(),
    'pages_scraped': len(items),
    'items': items
}}

# Write results to temp file
with open(r"{result_file_path}", 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)
'''
    
    # Write script to temp file
    script_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    script_file.write(script_content)
    script_file.close()
    
    try:
        logger.info(f"[{domain}] Starting Playwright scraper...")
        
        # Run script in subprocess using venv Python
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
        
        # Read results from temp file
        if os.path.exists(result_file_path):
            with open(result_file_path, 'r', encoding='utf-8') as f:
                subprocess_result = json.load(f)
            
            if subprocess_result.get('success'):
                result.scrape_status = "success"
                result.final_url = subprocess_result.get('final_url', '')
                result.raw_text = subprocess_result.get('raw_text', '')
                result.pages_scraped = subprocess_result.get('pages_scraped', 0)
                logger.info(f"[{domain}] ✓ Success: {result.pages_scraped} pages, {len(result.raw_text)} chars in {elapsed:.1f}s")
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
        # Clean up temp files
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
    fieldnames = ['domain', 'final_url', 'raw_text', 'scrape_status', 'error', 'pages_scraped', 'scrape_time_seconds']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))
    
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
    """
    Run batch scraping for multiple domains.
    
    Args:
        domains: List of domains to scrape
        output_file: Output file path
        output_format: "csv" or "jsonl"
        timeout_per_domain: Timeout per domain in seconds
        
    Returns:
        Summary statistics
    """
    total_domains = len(domains)
    results: List[ScrapeResult] = []
    
    logger.info("=" * 60)
    logger.info("BATCH RAW TEXT SCRAPER")
    logger.info("=" * 60)
    logger.info(f"Domains to scrape: {total_domains}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"Output format: {output_format}")
    logger.info(f"Timeout per domain: {timeout_per_domain}s")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    for i, domain in enumerate(domains, 1):
        logger.info(f"\n[{i}/{total_domains}] Processing: {domain}")
        result = scrape_domain_subprocess(domain, timeout=timeout_per_domain)
        results.append(result)
    
    total_time = time.time() - start_time
    
    # Save results
    if output_format == "jsonl":
        save_results_jsonl(results, output_file)
    else:
        save_results_csv(results, output_file)
    
    # Calculate statistics
    successful = sum(1 for r in results if r.scrape_status == "success")
    failed = total_domains - successful
    total_pages = sum(r.pages_scraped for r in results)
    total_chars = sum(len(r.raw_text) for r in results)
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("BATCH SCRAPING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total domains: {total_domains}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total pages scraped: {total_pages}")
    logger.info(f"Total characters: {total_chars:,}")
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Average time per domain: {total_time/total_domains:.1f}s")
    logger.info(f"\nOutput saved to: {output_file}")
    logger.info("=" * 60)
    
    # Log failed domains
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
        'total_time_seconds': round(total_time, 2),
        'output_file': output_file
    }


def main():
    parser = argparse.ArgumentParser(
        description='Batch Raw Text Scraper - Extract raw text without LLM processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python batch_scrape_raw.py
    python batch_scrape_raw.py --output my_output.csv
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
        help='Optional: Read domains from file instead of using hardcoded list'
    )
    
    args = parser.parse_args()
    
    # Determine domains to scrape
    if args.domains_file:
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
    
    # Adjust output file extension based on format
    output_file = args.output
    if args.format == 'jsonl' and not output_file.endswith('.jsonl'):
        output_file = output_file.rsplit('.', 1)[0] + '.jsonl'
    elif args.format == 'csv' and not output_file.endswith('.csv'):
        output_file = output_file.rsplit('.', 1)[0] + '.csv'
    
    # Run batch scrape
    summary = run_batch_scrape(
        domains=domains,
        output_file=output_file,
        output_format=args.format,
        timeout_per_domain=args.timeout
    )
    
    # Return exit code based on results
    if summary['failed'] == 0:
        return 0
    elif summary['successful'] > 0:
        return 2  # Partial success
    else:
        return 1  # Complete failure


if __name__ == '__main__':
    sys.exit(main())

