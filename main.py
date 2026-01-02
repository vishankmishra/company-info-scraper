#!/usr/bin/env python3
"""
Main entry point for Company Info Scraper (PH6-S1, PH6-S2)

Uses Google ADK-compatible agent orchestration with:
- Health checks for production monitoring
- Graceful shutdown handling
- Configurable logging
"""

# IMPORTANT: Install asyncio reactor BEFORE any Twisted imports
# This is required for Playwright (dynamic scraper) compatibility
import sys
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    # FIX: Use the default loop, do NOT create a new one.
    asyncioreactor.install()

import argparse
import os
import signal
import yaml
import logging
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from company_info_scraper.agents import OrchestratorAgent
from company_info_scraper.services import request_shutdown as batch_request_shutdown, extract_domain_name
from company_info_scraper.logging_config import setup_logging as configure_logging

# Global flag for graceful shutdown
_shutdown_requested = False
_current_orchestrator: Optional[OrchestratorAgent] = None


def setup_logging(config: dict) -> None:
    """Configure logging based on config (PH6-S3)."""
    configure_logging(config)


def load_config(config_file: str = None) -> dict:
    """Load configuration from YAML file or use defaults."""
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully (PH6-S2)."""
    global _shutdown_requested
    
    sig_name = signal.Signals(signum).name
    print(f"\n⚠ Received {sig_name} signal. Initiating graceful shutdown...")
    print("  Completing current domain(s) before exit...")
    print("  (Press Ctrl+C again to force exit)")
    
    if _shutdown_requested:
        # Second signal - force exit
        print("Force exiting...")
        sys.exit(1)
    
    _shutdown_requested = True
    
    # Notify batch processor to stop accepting new domains (PH6-S2)
    batch_request_shutdown()


def run_health_check(config: dict, verbose: bool = False, json_output: bool = False) -> int:
    """
    Run health checks (PH6-S1).
    
    Returns:
        Exit code (0 = healthy, 1 = unhealthy)
    """
    from company_info_scraper.health import (
        check_health, 
        print_health_status,
        run_health_check_cli
    )
    
    return run_health_check_cli(
        config=config,
        verbose=verbose,
        json_output=json_output
    )


def run_process_queue(
    queue_file: str,
    output_file: str = 'output_data.csv',
    config: dict = None,
    quiet: bool = False,
    parallel: bool = False,
    max_concurrent: int = 3
) -> int:
    """
    Process a saved extraction queue with LLM (PH2-S2).
    
    Loads a queue file created by --defer-llm and processes all items
    through the LLM for extraction.
    
    Args:
        queue_file: Path to the queue JSON file
        output_file: Output CSV file path
        config: Configuration dict
        quiet: Suppress output
        parallel: Use parallel LLM processing
        max_concurrent: Max concurrent LLM calls
        
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    import csv
    import asyncio
    import time
    from pathlib import Path
    from company_info_scraper.services import ExtractionQueue, LLMExtractionService
    
    config = config or {}
    
    if not os.path.exists(queue_file):
        print(f"Error: Queue file not found: {queue_file}")
        return 1
    
    if not quiet:
        print(f"Loading queue from: {queue_file}")
    
    # Load queue
    queue = ExtractionQueue.load(queue_file)
    
    if len(queue) == 0:
        print("Error: Queue is empty")
        return 1
    
    if not quiet:
        print(f"Processing {len(queue)} items with LLM...")
        if parallel:
            print(f"  Mode: Parallel (max {max_concurrent} concurrent)")
        else:
            print(f"  Mode: Sequential")
    
    # Initialize LLM service
    llm_service = LLMExtractionService(
        model=config.get('ollama_model', 'llama3'),
        timeout=config.get('ollama_timeout', 90),
        max_retries=config.get('ollama_max_retries', 3),
        max_text_length=config.get('max_text_length', 5000)
    )
    
    start_time = time.time()
    
    # Process queue
    if parallel:
        results = asyncio.run(queue.process_all_parallel(
            llm_service=llm_service,
            max_concurrent=max_concurrent
        ))
    else:
        def progress_callback(current, total, url):
            if not quiet:
                print(f"  [{current}/{total}] Processing: {url[:50]}...")
        
        results = asyncio.run(queue.process_all(
            llm_service=llm_service,
            on_progress=progress_callback if not quiet else None
        ))
    
    elapsed_s = time.time() - start_time
    
    # Count results
    successful = sum(1 for r in results if r.extraction_status == 'success')
    failed = len(results) - successful
    
    # Save results to CSV
    if results:
        fieldnames = [
            'url', 'products', 'services', 'customers', 'partnerships',
            'case_studies', 'extraction_status', 'error'
        ]
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    'url': result.url,
                    'products': result.products,
                    'services': result.services,
                    'customers': result.customers,
                    'partnerships': result.partnerships,
                    'case_studies': result.case_studies,
                    'extraction_status': result.extraction_status,
                    'error': result.error or ''
                })
    
    # Print results
    if not quiet:
        print(f"\n{'='*50}")
        print("Queue Processing Results")
        print(f"{'='*50}")
        print(f"  Total items: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {elapsed_s:.1f}s")
        if len(results) > 0:
            print(f"  Avg per item: {elapsed_s/len(results):.1f}s")
        print(f"\n  Output saved to: {output_file}")
        print(f"{'='*50}\n")
    
    logger = logging.getLogger(__name__)
    logger.info(f"Processed queue: {successful}/{len(results)} successful, saved to {output_file}")
    
    return 0 if failed == 0 else (2 if successful > 0 else 1)


def main():
    parser = argparse.ArgumentParser(
        description='Company Info Scraper - Extract corporate data using agentic AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape a single domain
  python main.py example.com
  
  # Batch process multiple domains
  python main.py --batch domains.txt
  
  # Run with parallel processing
  python main.py --batch domains.txt --parallel
  
  # Deferred LLM mode (fast scrape, process later)
  python main.py --batch domains.txt --defer-llm
  python main.py --process-queue /tmp/scraper_queue.json --output results.csv
  
  # Health check
  python main.py --health
  
  # Health check with JSON output
  python main.py --health --json
"""
    )
    
    # Positional argument
    parser.add_argument(
        'domain',
        nargs='?',
        help='Domain or URL to scrape (e.g., example.com or https://www.example.com)'
    )
    
    # Scraping options
    parser.add_argument(
        '--batch',
        type=str,
        metavar='FILE',
        help='File containing domains (one per line) for batch processing'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Use parallel processing for batch mode (faster but more resource-intensive)'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=5,
        help='Maximum concurrent domains for parallel mode (default: 5)'
    )
    parser.add_argument(
        '--scraper',
        type=str,
        choices=['auto', 'static', 'dynamic'],
        default='auto',
        help='Scraper type (Phase 2: always uses Playwright/dynamic, other options ignored)'
    )
    
    # Queue mode options (PH2-S2: Extraction queue decoupling)
    parser.add_argument(
        '--defer-llm',
        action='store_true',
        help='Scrape without LLM extraction; queue items for later processing with --process-queue'
    )
    parser.add_argument(
        '--process-queue',
        type=str,
        metavar='FILE',
        help='Process a previously saved queue file with LLM extraction (use after --defer-llm)'
    )
    
    # Configuration
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='output_data.csv',
        help='Output CSV file path (default: output_data.csv)'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Ollama model to use (overrides config)'
    )
    
    # Health check (PH6-S1)
    parser.add_argument(
        '--health',
        action='store_true',
        help='Run health checks and exit'
    )
    parser.add_argument(
        '--health-verbose',
        action='store_true',
        help='Verbose health check output'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format (for health checks)'
    )
    
    # Logging options (PH6-S3)
    parser.add_argument(
        '--log-format',
        type=str,
        choices=['text', 'json'],
        default=None,
        help='Log output format (default: text, use json for production)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        help='Log file path (logs are also written to console)'
    )
    
    # Verbosity
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (DEBUG level)'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-essential output (WARNING level)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Setup logging (PH6-S3)
    if args.verbose:
        config['log_level'] = 'DEBUG'
    elif args.quiet:
        config['log_level'] = 'WARNING'
    if args.log_format:
        config['log_format'] = args.log_format
    if args.log_file:
        config['log_file'] = args.log_file
    setup_logging(config)
    
    logger = logging.getLogger(__name__)
    
    # Health check mode (PH6-S1)
    if args.health:
        return run_health_check(
            config=config,
            verbose=args.health_verbose or args.verbose,
            json_output=args.json
        )
    
    # Process queue mode (PH2-S2: Extraction queue decoupling)
    if args.process_queue:
        return run_process_queue(
            queue_file=args.process_queue,
            output_file=args.output,
            config=config,
            quiet=args.quiet,
            parallel=args.parallel,
            max_concurrent=args.max_concurrent
        )
    
    # Validate arguments
    if not args.domain and not args.batch:
        parser.print_help()
        print("\nError: Please specify a domain or use --batch for batch processing")
        return 1
    
    # Setup signal handlers for graceful shutdown (PH6-S2)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Merge CLI args with config
    agent_config = {
        'project_root': str(project_root),
        'output_file': args.output,
        'ollama_model': args.model or config.get('ollama_model', 'llama3'),
        'ollama_timeout': config.get('ollama_timeout', 90),
        'max_text_length': config.get('max_text_length', 5000),
        'max_concurrent': args.max_concurrent,
        # Phase 2: Universal Playwright - these config options are ignored
        'auto_detect': False,
        'force_scraper': 'dynamic',
    }
    
    # Add batch config
    batch_config = config.get('batch', {})
    agent_config['max_concurrent'] = args.max_concurrent or batch_config.get('max_concurrent', 5)
    
    # Initialize orchestrator
    global _current_orchestrator
    _current_orchestrator = OrchestratorAgent(agent_config)
    orchestrator = _current_orchestrator
    
    try:
        # Execute scraping
        if args.batch:
            return run_batch_mode(
                orchestrator=orchestrator,
                batch_file=args.batch,
                parallel=args.parallel,
                max_concurrent=args.max_concurrent,
                quiet=args.quiet,
                output_file=args.output,
                defer_llm=args.defer_llm,
                config=config
            )
        else:
            return run_single_mode(
                orchestrator=orchestrator,
                domain=args.domain,
                scraper_type=args.scraper,
                quiet=args.quiet,
                output_file=args.output,
                defer_llm=args.defer_llm,
                config=config
            )
            
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_single_mode(
    orchestrator: OrchestratorAgent,
    domain: str,
    scraper_type: str = 'auto',
    quiet: bool = False,
    output_file: str = 'output_data.csv',
    defer_llm: bool = False,
    config: dict = None
) -> int:
    """Run scraper for a single domain.
    
    Phase 2: Always uses universal Playwright scraper (scraper_type arg ignored).
    
    Args:
        orchestrator: OrchestratorAgent instance
        domain: Domain to scrape
        scraper_type: Scraper type (ignored, always uses Playwright)
        quiet: Suppress output
        output_file: Output CSV file path
        defer_llm: If True, skip LLM extraction and queue for later
        config: Configuration dict
    """
    import csv
    from pathlib import Path
    from datetime import datetime
    from company_info_scraper.services import ExtractionQueue, get_global_queue, reset_global_queue
    
    config = config or {}
    
    if not quiet:
        if defer_llm:
            print(f"Processing domain (defer LLM): {domain}")
        else:
            print(f"Processing domain: {domain}")
    
    if defer_llm:
        # Queue mode: scrape without LLM extraction
        return run_single_mode_deferred(
            orchestrator=orchestrator,
            domain=domain,
            scraper_type=scraper_type,
            quiet=quiet,
            config=config
        )
    
    result = orchestrator.execute({
        'domain': domain,
        'scraper_type': scraper_type
    })
    
    if result.get('success'):
        # Save to CSV files
        records = result.get('records', [])
        saved_files = save_domain_results(
            domain=domain,
            records=records,
            scraper_type=result.get('scraper_type', 'unknown'),
            main_output_file=output_file
        )
        
        if not quiet:
            print(f"\n✓ Scraping completed successfully!")
            print(f"  Domain: {result['domain']}")
            print(f"  Scraper: {result.get('scraper_type', 'unknown')}")
            print(f"  Records: {result['records_count']}")
            print(f"  Output: {output_file}")
        return 0
    else:
        print(f"\n✗ Scraping failed: {result.get('error')}")
        return 1


def run_single_mode_deferred(
    orchestrator: OrchestratorAgent,
    domain: str,
    scraper_type: str = 'auto',
    quiet: bool = False,
    config: dict = None
) -> int:
    """Run scraper for a single domain with deferred LLM extraction (PH2-S2).
    
    Scrapes the domain and queues raw text for later LLM processing.
    Phase 2: Always uses Playwright (universal scraping).
    """
    from datetime import datetime
    from company_info_scraper.services import ExtractionQueue
    import asyncio
    
    config = config or {}
    queue = ExtractionQueue()
    
    try:
        if not quiet:
            print(f"  Scraper: dynamic (Playwright)")
        
        # Phase 2: Use Playwright for all scraping
        from company_info_scraper.agents.scraping_agent import ScrapingAgent
        scraping_agent = ScrapingAgent(config=config)
        result = scraping_agent.execute({'domain': domain})
        
        if not result.get('success'):
            raise Exception(result.get('error', 'Scraping failed'))
        
        items = result.get('raw_data', [])
        
        # Queue items for later LLM processing
        for item in items:
            url = item.get('url', domain)
            raw_text = item.get('raw_text', '')
            if raw_text:
                queue.add(url, raw_text)
        
        # Save queue to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        queue_dir = config.get('extraction_queue_dir', '/tmp')
        queue_file = f"{queue_dir}/scraper_queue_{timestamp}.json"
        saved_path = queue.save(queue_file)
        
        if not quiet:
            print(f"\n✓ Scraping completed (LLM deferred)!")
            print(f"  Domain: {domain}")
            print(f"  Items queued: {len(queue)}")
            print(f"  Queue saved to: {saved_path}")
            print(f"\n  To process with LLM later:")
            print(f"    python main.py --process-queue {saved_path} --output results.csv")
        
        return 0
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Deferred scraping failed for {domain}: {e}")
        print(f"\n✗ Scraping failed: {e}")
        return 1


def save_domain_results(
    domain: str,
    records: list,
    scraper_type: str,
    main_output_file: str = 'output_data.csv'
) -> list:
    """
    Save scraping results to main CSV file only.
    
    Args:
        domain: The scraped domain
        records: List of record dictionaries
        scraper_type: Type of scraper used
        main_output_file: Path to main output file (appends)
        
    Returns:
        List of saved file paths (single file)
    """
    import csv
    from pathlib import Path
    
    saved_files = []
    
    if not records:
        return saved_files
    
    from datetime import datetime
    
    # Add website and timestamp fields to each record
    timestamp = datetime.now().isoformat()
    for record in records:
        if 'website' not in record:
            record['website'] = domain
        if 'timestamp' not in record:
            record['timestamp'] = timestamp
    
    fieldnames = [
        'website', 'timestamp', 'case_studies', 'customers', 'partnerships', 'products', 'services',
        'raw_text', 'url', 'extraction_status'
    ]
    
    # Ensure all fieldnames from records are included
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    
    # Append to main output file (never delete, always append)
    main_file_exists = Path(main_output_file).exists()
    with open(main_output_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not main_file_exists:
            writer.writeheader()
        for record in records:
            writer.writerow(record)
    saved_files.append(main_output_file)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Saved results to: {main_output_file}")
    
    return saved_files


def run_batch_mode(
    orchestrator: OrchestratorAgent,
    batch_file: str,
    parallel: bool = False,
    max_concurrent: int = 5,
    quiet: bool = False,
    output_file: str = 'output_data.csv',
    defer_llm: bool = False,
    config: dict = None
) -> int:
    """Run scraper for multiple domains from a file.
    
    Args:
        orchestrator: OrchestratorAgent instance
        batch_file: Path to file with domains (one per line)
        parallel: Use parallel processing
        max_concurrent: Max concurrent domains
        quiet: Suppress output
        output_file: Output CSV file path
        defer_llm: If True, skip LLM extraction and queue for later
        config: Configuration dict
    """
    import csv
    from pathlib import Path
    global _shutdown_requested
    
    config = config or {}
    
    if not os.path.exists(batch_file):
        print(f"Error: Batch file not found: {batch_file}")
        return 1
    
    with open(batch_file, 'r') as f:
        domains = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith('#')
        ]
    
    if not domains:
        print("Error: No domains found in batch file")
        return 1
    
    if not quiet:
        print(f"Processing {len(domains)} domains...")
        if defer_llm:
            print(f"  Mode: Deferred LLM (scrape only, process later)")
        elif parallel:
            print(f"  Mode: Parallel (max {max_concurrent} concurrent)")
        else:
            print(f"  Mode: Sequential")
    
    # Check for shutdown before starting
    if _shutdown_requested:
        print("Shutdown requested before processing started")
        return 130
    
    if defer_llm:
        # Deferred LLM mode: scrape without extraction
        return run_batch_mode_deferred(
            domains=domains,
            parallel=parallel,
            max_concurrent=max_concurrent,
            quiet=quiet,
            config=config
        )
    
    # Execute batch with LLM extraction
    if parallel:
        result = orchestrator.execute_batch_parallel(domains, max_concurrent)
    else:
        result = orchestrator.execute_batch(domains)
    
    # Save results to CSV files (main + domain-specific)
    saved_files = save_batch_results(
        result=result,
        main_output_file=output_file
    )
    
    # Print results
    if not quiet:
        print(f"\n{'='*50}")
        print("Batch Processing Results")
        print(f"{'='*50}")
        print(f"  Total domains: {result['total_domains']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Static scraper: {result.get('static_scraped', 0)}")
        print(f"  Dynamic scraper: {result.get('dynamic_scraped', 0)}")
        
        if 'total_elapsed_ms' in result:
            elapsed_s = result['total_elapsed_ms'] / 1000
            print(f"  Total time: {elapsed_s:.1f}s")
            if result.get('avg_time_per_domain_ms'):
                avg_s = result['avg_time_per_domain_ms'] / 1000
                print(f"  Avg per domain: {avg_s:.1f}s")
        
        print(f"\n  Output files:")
        for f in saved_files:
            print(f"    - {f}")
        
        print(f"{'='*50}\n")
    
    # Return appropriate exit code
    if result['failed'] > 0:
        return 2 if result['successful'] > 0 else 1
    return 0


def run_batch_mode_deferred(
    domains: list,
    parallel: bool = False,
    max_concurrent: int = 5,
    quiet: bool = False,
    config: dict = None
) -> int:
    """Run batch scraping with deferred LLM extraction (PH2-S2).
    
    Scrapes all domains and saves raw text to a queue file for later LLM processing.
    """
    from datetime import datetime
    from company_info_scraper.services import ExtractionQueue
    from company_info_scraper.spiders import StaticScraper
    import asyncio
    import time
    
    config = config or {}
    queue = ExtractionQueue()
    scraper = StaticScraper()
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    async def scrape_domain(domain: str) -> int:
        """Scrape a single domain and add to queue."""
        nonlocal successful, failed
        try:
            items = await scraper.scrape(domain)
            count = 0
            for item in items:
                url = item.get('url', domain)
                raw_text = item.get('raw_text', '')
                if raw_text:
                    queue.add(url, raw_text)
                    count += 1
            if count > 0:
                successful += 1
                if not quiet:
                    print(f"  ✓ {domain}: {count} pages queued")
            else:
                failed += 1
                if not quiet:
                    print(f"  ✗ {domain}: no content found")
            return count
        except Exception as e:
            failed += 1
            if not quiet:
                print(f"  ✗ {domain}: {e}")
            return 0
    
    async def scrape_all_parallel():
        """Scrape all domains in parallel."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(domain: str):
            async with semaphore:
                return await scrape_domain(domain)
        
        await asyncio.gather(*[scrape_with_semaphore(d) for d in domains])
    
    async def scrape_all_sequential():
        """Scrape all domains sequentially."""
        for domain in domains:
            await scrape_domain(domain)
    
    # Run scraping
    if parallel:
        asyncio.run(scrape_all_parallel())
    else:
        asyncio.run(scrape_all_sequential())
    
    elapsed_s = time.time() - start_time
    
    # Save queue to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    queue_dir = config.get('extraction_queue_dir', '/tmp')
    queue_file = f"{queue_dir}/scraper_queue_{timestamp}.json"
    saved_path = queue.save(queue_file)
    
    # Print results
    if not quiet:
        print(f"\n{'='*50}")
        print("Batch Scraping Results (LLM Deferred)")
        print(f"{'='*50}")
        print(f"  Total domains: {len(domains)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Items queued: {len(queue)}")
        print(f"  Total time: {elapsed_s:.1f}s")
        print(f"\n  Queue saved to: {saved_path}")
        print(f"\n  To process with LLM later:")
        print(f"    python main.py --process-queue {saved_path} --output results.csv")
        print(f"{'='*50}\n")
    
    return 0 if failed == 0 else (2 if successful > 0 else 1)


def save_batch_results(
    result: dict,
    main_output_file: str = 'output_data.csv'
) -> list:
    """
    Save batch results to main CSV file only.
    
    Args:
        result: Batch processing result dictionary
        main_output_file: Path to main output file
        
    Returns:
        List of saved file paths (single file)
    """
    import csv
    from pathlib import Path
    
    saved_files = []
    
    results = result.get('results', [])
    if not results:
        return saved_files
    
    from datetime import datetime
    
    fieldnames = [
        'website', 'timestamp', 'case_studies', 'customers', 'partnerships', 'products', 'services',
        'raw_text', 'url', 'extraction_status'
    ]
    
    # Collect all fieldnames from records
    for domain_result in results:
        for record in domain_result.get('records', []):
            for key in record.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
    
    output_dir = Path(main_output_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Append to main output file (never delete, always append)
    main_file_exists = Path(main_output_file).exists()
    timestamp = datetime.now().isoformat()
    
    with open(main_output_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not main_file_exists:
            writer.writeheader()
        
        for domain_result in results:
            domain = domain_result.get('domain', 'unknown')
            
            for record in domain_result.get('records', []):
                # Add website and timestamp fields if not present
                row = {
                    'website': domain,
                    'timestamp': timestamp,
                    **record
                }
                writer.writerow(row)
    
    saved_files.append(main_output_file)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Saved batch results to {main_output_file}")
    
    return saved_files


if __name__ == '__main__':
    sys.exit(main())
