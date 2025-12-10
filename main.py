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
    asyncioreactor.install(asyncio.new_event_loop())

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
        help='Force scraper type: auto (detect), static (fast), dynamic (JS-capable)'
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
        'auto_detect': args.scraper == 'auto',
        'force_scraper': None if args.scraper == 'auto' else args.scraper,
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
                output_file=args.output
            )
        else:
            return run_single_mode(
                orchestrator=orchestrator,
                domain=args.domain,
                scraper_type=args.scraper,
                quiet=args.quiet,
                output_file=args.output
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
    output_file: str = 'output_data.csv'
) -> int:
    """Run scraper for a single domain."""
    import csv
    from pathlib import Path
    
    if not quiet:
        print(f"Processing domain: {domain}")
    
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
            for f in saved_files:
                print(f"  Output: {f}")
        return 0
    else:
        print(f"\n✗ Scraping failed: {result.get('error')}")
        return 1


def save_domain_results(
    domain: str,
    records: list,
    scraper_type: str,
    main_output_file: str = 'output_data.csv'
) -> list:
    """
    Save scraping results to both main CSV and domain-specific CSV.
    
    Args:
        domain: The scraped domain
        records: List of record dictionaries
        scraper_type: Type of scraper used
        main_output_file: Path to main output file (appends)
        
    Returns:
        List of saved file paths
    """
    import csv
    from pathlib import Path
    
    saved_files = []
    
    if not records:
        return saved_files
    
    fieldnames = [
        'case_studies', 'customers', 'partnerships', 'products',
        'raw_text', 'url', 'extraction_status'
    ]
    
    # Ensure all fieldnames from records are included
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    
    # 1. Append to main output file
    main_file_exists = Path(main_output_file).exists()
    with open(main_output_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not main_file_exists:
            writer.writeheader()
        for record in records:
            writer.writerow(record)
    saved_files.append(main_output_file)
    
    # 2. Save to domain-specific file (overwrites)
    domain_name = extract_domain_name(domain)
    output_dir = Path(main_output_file).parent
    domain_file = output_dir / f"{domain_name}_output_data.csv"
    
    with open(domain_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for record in records:
            writer.writerow(record)
    saved_files.append(str(domain_file))
    
    logger = logging.getLogger(__name__)
    logger.info(f"Saved results to: {main_output_file} and {domain_file}")
    
    return saved_files


def run_batch_mode(
    orchestrator: OrchestratorAgent,
    batch_file: str,
    parallel: bool = False,
    max_concurrent: int = 5,
    quiet: bool = False,
    output_file: str = 'output_data.csv'
) -> int:
    """Run scraper for multiple domains from a file."""
    import csv
    from pathlib import Path
    global _shutdown_requested
    
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
        if parallel:
            print(f"  Mode: Parallel (max {max_concurrent} concurrent)")
        else:
            print(f"  Mode: Sequential")
    
    # Check for shutdown before starting
    if _shutdown_requested:
        print("Shutdown requested before processing started")
        return 130
    
    # Execute batch
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


def save_batch_results(
    result: dict,
    main_output_file: str = 'output_data.csv'
) -> list:
    """
    Save batch results to both main CSV and domain-specific CSVs.
    
    Args:
        result: Batch processing result dictionary
        main_output_file: Path to main output file
        
    Returns:
        List of saved file paths
    """
    import csv
    from pathlib import Path
    
    saved_files = []
    
    results = result.get('results', [])
    if not results:
        return saved_files
    
    fieldnames = [
        'case_studies', 'customers', 'partnerships', 'products',
        'raw_text', 'url', 'extraction_status', 'domain', 'scraper_type'
    ]
    
    # Collect all fieldnames from records
    for domain_result in results:
        for record in domain_result.get('records', []):
            for key in record.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
    
    output_dir = Path(main_output_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Append to main output file
    main_file_exists = Path(main_output_file).exists()
    with open(main_output_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not main_file_exists:
            writer.writeheader()
        
        for domain_result in results:
            domain = domain_result.get('domain', 'unknown')
            scraper_type = domain_result.get('scraper_type', 'unknown')
            
            for record in domain_result.get('records', []):
                row = {
                    'domain': domain,
                    'scraper_type': scraper_type,
                    **record
                }
                writer.writerow(row)
    
    saved_files.append(main_output_file)
    
    # 2. Save domain-specific files
    for domain_result in results:
        records = domain_result.get('records', [])
        if not records:
            continue
        
        domain = domain_result.get('domain', 'unknown')
        domain_name = extract_domain_name(domain)
        domain_file = output_dir / f"{domain_name}_output_data.csv"
        
        with open(domain_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for record in records:
                row = {
                    'domain': domain,
                    'scraper_type': domain_result.get('scraper_type', 'unknown'),
                    **record
                }
                writer.writerow(row)
        
        saved_files.append(str(domain_file))
    
    logger = logging.getLogger(__name__)
    logger.info(f"Saved batch results to {len(saved_files)} files")
    
    return saved_files


if __name__ == '__main__':
    sys.exit(main())
