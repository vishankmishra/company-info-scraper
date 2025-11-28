"""
Async Batch Processor (PH4-S2, PH6-S2)

Processes multiple domains concurrently using asyncio.
Supports configurable concurrency limits, rate limiting, and graceful shutdown.
"""

import asyncio
import csv
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

import yaml

from company_info_scraper.services import SiteDetector, SiteType, LLMExtractionService
from company_info_scraper.spiders import StaticScraper

logger = logging.getLogger(__name__)

# Global shutdown flag for graceful termination (PH6-S2)
_shutdown_requested = False


def request_shutdown():
    """Request graceful shutdown of batch processing."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Shutdown requested for batch processor")


def reset_shutdown():
    """Reset shutdown flag (for testing or restart)."""
    global _shutdown_requested
    _shutdown_requested = False


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def extract_domain_name(url_or_domain: str) -> str:
    """
    Extract clean domain name from URL or domain string.
    
    Examples:
        https://www.grab.com/sg/ -> grab
        www.transformhub.com -> transformhub
        example.co.uk -> example
        https://sub.domain.example.com -> example
        
    Args:
        url_or_domain: URL or domain string
        
    Returns:
        Clean domain name (just the main part, no TLD)
    """
    from urllib.parse import urlparse
    
    # Handle full URLs
    if '://' in url_or_domain:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc or parsed.path
    else:
        domain = url_or_domain
    
    # Remove www. prefix
    if domain.startswith('www.'):
        domain = domain[4:]
    
    # Split by dots and get the main domain name
    # Handle cases like: grab.com, example.co.uk, sub.example.com
    parts = domain.split('.')
    
    # Common second-level TLDs
    second_level_tlds = {'co', 'com', 'org', 'net', 'gov', 'edu', 'ac'}
    
    if len(parts) >= 3 and parts[-2] in second_level_tlds:
        # e.g., example.co.uk -> example
        return parts[-3].lower()
    elif len(parts) >= 2:
        # e.g., example.com -> example, sub.example.com -> example
        return parts[-2].lower()
    else:
        # Fallback: return first part
        return parts[0].lower()


@dataclass
class DomainResult:
    """Result for a single domain."""
    domain: str
    success: bool
    scraper_type: str  # 'static' or 'dynamic'
    records_count: int = 0
    records: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    retries: int = 0


@dataclass
class BatchResult:
    """Result for batch processing."""
    total_domains: int
    successful: int
    failed: int
    static_scraped: int
    dynamic_scraped: int
    total_elapsed_ms: float
    results: List[DomainResult] = field(default_factory=list)
    rate_limited_count: int = 0  # How many times rate limiting kicked in
    
    @property
    def success_rate(self) -> float:
        return self.successful / max(self.total_domains, 1)
    
    @property
    def avg_time_per_domain_ms(self) -> float:
        return self.total_elapsed_ms / max(self.total_domains, 1)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_second: float = 2.0
    burst_size: int = 5
    per_domain_delay: float = 1.0


class RateLimiter:
    """Token bucket rate limiter for controlling request rate.
    
    Implements a token bucket algorithm with configurable rate and burst size.
    """
    
    def __init__(self, rate: float = 2.0, burst: int = 5):
        """Initialize rate limiter.
        
        Args:
            rate: Tokens per second
            burst: Maximum tokens (burst capacity)
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self._wait_count = 0
    
    async def acquire(self) -> float:
        """Acquire a token, waiting if necessary.
        
        Returns:
            Time waited in seconds
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            
            # Add tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            
            # Need to wait for tokens
            wait_time = (1 - self.tokens) / self.rate
            self._wait_count += 1
            
        await asyncio.sleep(wait_time)
        
        async with self._lock:
            self.tokens = 0  # We consumed the token we waited for
        
        return wait_time
    
    @property
    def wait_count(self) -> int:
        """Number of times we had to wait for rate limiting."""
        return self._wait_count


class BatchProcessor:
    """Async batch processor for multi-domain scraping (PH4-S2).
    
    Processes multiple domains concurrently with configurable parallelism
    and rate limiting to prevent overwhelming target sites.
    
    Usage:
        processor = BatchProcessor(max_concurrent=5)
        results = await processor.process(['example.com', 'another.com'])
        
        # Or load from config
        processor = BatchProcessor.from_config('config.yaml')
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        auto_detect: bool = True,
        default_scraper: str = 'static',
        llm_timeout: int = 90,
        llm_max_retries: int = 3,
        rate_limit_delay: float = 1.0,
        request_delay: float = 0.5,
        timeout_per_domain: int = 120,
        retry_failed: bool = True,
        max_retries: int = 2,
        rate_limit_config: Optional[RateLimitConfig] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ):
        """Initialize batch processor.
        
        Args:
            max_concurrent: Maximum concurrent domain processing
            auto_detect: Whether to auto-detect static/dynamic sites
            default_scraper: Default scraper type if detection fails
            llm_timeout: Timeout for LLM extraction
            llm_max_retries: Max retries for LLM calls
            rate_limit_delay: Delay between starting each domain
            request_delay: Delay between requests within a domain
            timeout_per_domain: Max time per domain before timeout
            retry_failed: Whether to retry failed domains
            max_retries: Max retries per domain
            rate_limit_config: Rate limiting configuration
            on_progress: Optional callback(current, total, domain) for progress
        """
        self.max_concurrent = max_concurrent
        self.auto_detect = auto_detect
        self.default_scraper = default_scraper
        self.rate_limit_delay = rate_limit_delay
        self.request_delay = request_delay
        self.timeout_per_domain = timeout_per_domain
        self.retry_failed = retry_failed
        self.max_retries = max_retries
        self.on_progress = on_progress
        
        # Rate limiting
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.rate_limiter = None
        if self.rate_limit_config.enabled:
            self.rate_limiter = RateLimiter(
                rate=self.rate_limit_config.requests_per_second,
                burst=self.rate_limit_config.burst_size
            )
        
        # Initialize services
        self.site_detector = SiteDetector()
        self.static_scraper = StaticScraper()
        self.llm_service = LLMExtractionService(
            timeout=llm_timeout,
            max_retries=llm_max_retries
        )
        
        # Stats
        self._processed = 0
        self._total = 0
    
    @classmethod
    def from_config(cls, config_path: str = 'config.yaml') -> 'BatchProcessor':
        """Create BatchProcessor from config file.
        
        Args:
            config_path: Path to YAML config file
            
        Returns:
            Configured BatchProcessor instance
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()
        
        batch_config = config.get('batch', {})
        rate_config = config.get('rate_limiting', {})
        
        rate_limit_config = RateLimitConfig(
            enabled=rate_config.get('enabled', True),
            requests_per_second=rate_config.get('requests_per_second', 2.0),
            burst_size=rate_config.get('burst_size', 5),
            per_domain_delay=rate_config.get('per_domain_delay', 1.0)
        )
        
        return cls(
            max_concurrent=batch_config.get('max_concurrent', 5),
            auto_detect=config.get('auto_detect', True),
            default_scraper='static',
            llm_timeout=config.get('ollama_timeout', 90),
            llm_max_retries=config.get('ollama_max_retries', 3),
            rate_limit_delay=batch_config.get('rate_limit_delay', 1.0),
            request_delay=batch_config.get('request_delay', 0.5),
            timeout_per_domain=batch_config.get('timeout_per_domain', 120),
            retry_failed=batch_config.get('retry_failed', True),
            max_retries=batch_config.get('max_retries', 2),
            rate_limit_config=rate_limit_config
        )
    
    async def process(
        self,
        domains: List[str],
        skip_llm: bool = False
    ) -> BatchResult:
        """Process multiple domains concurrently with rate limiting.
        
        Args:
            domains: List of domain URLs to process
            skip_llm: If True, skip LLM extraction (scrape only)
            
        Returns:
            BatchResult with all domain results
            
        Note:
            Supports graceful shutdown via request_shutdown(). When shutdown
            is requested, the processor will complete current domains and
            return partial results.
        """
        global _shutdown_requested
        
        if not domains:
            return BatchResult(
                total_domains=0,
                successful=0,
                failed=0,
                static_scraped=0,
                dynamic_scraped=0,
                total_elapsed_ms=0,
                results=[]
            )
        
        self._processed = 0
        self._total = len(domains)
        self._cancelled_count = 0
        
        rate_limit_info = ""
        if self.rate_limiter:
            rate_limit_info = f", rate_limit={self.rate_limit_config.requests_per_second}/s"
        
        logger.info(
            f"Starting batch processing: {len(domains)} domains, "
            f"max_concurrent={self.max_concurrent}{rate_limit_info}"
        )
        
        start_time = time.time()
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Process all domains concurrently (limited by semaphore and rate limiter)
        tasks = []
        domains_started = []
        
        for i, domain in enumerate(domains):
            # Check for shutdown request before starting new domains (PH6-S2)
            if _shutdown_requested:
                logger.info(
                    f"Shutdown requested. Stopping after {len(domains_started)} domains "
                    f"(skipping {len(domains) - len(domains_started)} remaining)"
                )
                # Mark remaining domains as cancelled
                for remaining_domain in domains[i:]:
                    tasks.append(asyncio.coroutine(lambda d=remaining_domain: DomainResult(
                        domain=d,
                        success=False,
                        scraper_type='cancelled',
                        error='Shutdown requested'
                    ))())
                    self._cancelled_count += 1
                break
            
            # Apply rate limit delay between domain starts
            if i > 0 and self.rate_limit_delay > 0:
                await asyncio.sleep(self.rate_limit_delay)
            
            task = self._process_domain_with_retry(domain, semaphore, skip_llm)
            tasks.append(task)
            domains_started.append(domain)
        
        # Wait for all started tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
        
        # Convert exceptions to failed results
        domain_results: List[DomainResult] = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                domain_results.append(DomainResult(
                    domain=domain,
                    success=False,
                    scraper_type='unknown',
                    error=str(result)
                ))
            else:
                domain_results.append(result)
        
        total_elapsed = (time.time() - start_time) * 1000
        
        # Calculate stats
        successful = sum(1 for r in domain_results if r.success)
        static_count = sum(1 for r in domain_results if r.scraper_type == 'static')
        dynamic_count = sum(1 for r in domain_results if r.scraper_type == 'dynamic')
        rate_limited = self.rate_limiter.wait_count if self.rate_limiter else 0
        
        shutdown_note = ""
        if _shutdown_requested:
            shutdown_note = f", cancelled: {self._cancelled_count}"
        
        logger.info(
            f"Batch complete: {successful}/{len(domains)} successful in {total_elapsed/1000:.1f}s. "
            f"Static: {static_count}, Dynamic: {dynamic_count}, Rate limited: {rate_limited}x{shutdown_note}"
        )
        
        return BatchResult(
            total_domains=len(domains),
            successful=successful,
            failed=len(domains) - successful,
            static_scraped=static_count,
            dynamic_scraped=dynamic_count,
            total_elapsed_ms=total_elapsed,
            results=domain_results,
            rate_limited_count=rate_limited
        )
    
    async def _process_domain_with_retry(
        self,
        domain: str,
        semaphore: asyncio.Semaphore,
        skip_llm: bool
    ) -> DomainResult:
        """Process domain with retry support."""
        last_result = None
        retries = 0
        
        for attempt in range(self.max_retries + 1):
            result = await self._process_domain(domain, semaphore, skip_llm)
            result.retries = attempt
            
            if result.success:
                return result
            
            last_result = result
            retries = attempt
            
            if not self.retry_failed or attempt >= self.max_retries:
                break
            
            # Wait before retry with exponential backoff
            wait_time = 2 ** attempt
            logger.warning(
                f"Retrying {domain} (attempt {attempt + 2}/{self.max_retries + 1}) "
                f"after {wait_time}s..."
            )
            await asyncio.sleep(wait_time)
        
        if last_result:
            last_result.retries = retries
        return last_result
    
    async def _process_domain(
        self,
        domain: str,
        semaphore: asyncio.Semaphore,
        skip_llm: bool
    ) -> DomainResult:
        """Process a single domain with semaphore and rate limit control."""
        async with semaphore:
            # Apply rate limiting if enabled
            if self.rate_limiter:
                wait_time = await self.rate_limiter.acquire()
                if wait_time > 0:
                    logger.debug(f"Rate limited for {domain}: waited {wait_time:.2f}s")
            
            # Apply timeout per domain
            try:
                return await asyncio.wait_for(
                    self._process_domain_impl(domain, skip_llm),
                    timeout=self.timeout_per_domain
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout processing {domain} after {self.timeout_per_domain}s")
                return DomainResult(
                    domain=domain,
                    success=False,
                    scraper_type='unknown',
                    error=f"Timeout after {self.timeout_per_domain}s"
                )
    
    async def _process_domain_impl(
        self,
        domain: str,
        skip_llm: bool
    ) -> DomainResult:
        """Implementation of domain processing."""
        start_time = time.time()
        
        try:
            # Step 1: Detect site type
            if self.auto_detect:
                scraper_type = await self._detect_site_type(domain)
            else:
                scraper_type = self.default_scraper
            
            # Step 2: Scrape based on type
            if scraper_type == 'static':
                raw_data = await self._scrape_static(domain)
            else:
                # For dynamic sites, we'd use Playwright
                # For now, fall back to static if dynamic not available in async context
                logger.warning(
                    f"Dynamic scraping not available in batch mode for {domain}, "
                    f"falling back to static"
                )
                raw_data = await self._scrape_static(domain)
                scraper_type = 'static'
            
            # Step 3: LLM Extraction (if not skipped)
            records = []
            if not skip_llm and raw_data:
                records = await self._extract_all(raw_data)
            else:
                # Return raw data without extraction
                records = raw_data
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Update progress
            self._processed += 1
            if self.on_progress:
                self.on_progress(self._processed, self._total, domain)
            
            logger.info(
                f"Completed {domain}: {len(records)} records in {elapsed_ms:.0f}ms "
                f"(scraper: {scraper_type})"
            )
            
            return DomainResult(
                domain=domain,
                success=True,
                scraper_type=scraper_type,
                records_count=len(records),
                records=records,
                elapsed_ms=elapsed_ms
            )
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._processed += 1
            
            logger.error(f"Failed to process {domain}: {e}")
            
            return DomainResult(
                domain=domain,
                success=False,
                scraper_type='unknown',
                elapsed_ms=elapsed_ms,
                error=str(e)
            )
    
    async def _detect_site_type(self, domain: str) -> str:
        """Detect if site is static or dynamic."""
        try:
            result = await self.site_detector.detect(domain)
            if result.site_type == SiteType.STATIC:
                logger.debug(f"Detected STATIC: {domain} (confidence: {result.confidence:.0%})")
                return 'static'
            else:
                logger.debug(f"Detected DYNAMIC: {domain} (confidence: {result.confidence:.0%})")
                return 'dynamic'
        except Exception as e:
            logger.warning(f"Site detection failed for {domain}: {e}")
            return self.default_scraper
    
    async def _scrape_static(self, domain: str) -> List[Dict[str, Any]]:
        """Scrape using static scraper."""
        items = await self.static_scraper.scrape(domain)
        
        # Convert to dict format
        return [
            {'url': item.get('url', ''), 'raw_text': item.get('raw_text', '')}
            for item in items
        ]
    
    async def _extract_all(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract data from all scraped pages using LLM."""
        results = []
        
        for record in raw_data:
            text = record.get('raw_text', '')
            url = record.get('url', 'unknown')
            
            if text:
                extraction = await self.llm_service.extract(text, url=url)
                results.append({
                    'url': url,
                    'products': extraction.products,
                    'customers': extraction.customers,
                    'partnerships': extraction.partnerships,
                    'case_studies': extraction.case_studies,
                    'extraction_status': extraction.status
                })
            else:
                results.append({
                    'url': url,
                    'products': 'N/A',
                    'customers': 'N/A',
                    'partnerships': 'N/A',
                    'case_studies': 'N/A',
                    'extraction_status': 'failure'
                })
        
        return results
    
    def save_results_csv(
        self,
        batch_result: BatchResult,
        output_file: str = 'batch_output.csv',
        save_domain_files: bool = True
    ) -> List[str]:
        """Save batch results to CSV file(s).
        
        Saves results to the main output file AND creates domain-specific
        CSV files for each domain (e.g., grab_output_data.csv).
        
        Args:
            batch_result: The batch processing result
            output_file: Main output CSV file path
            save_domain_files: Also save domain-specific files (default: True)
            
        Returns:
            List of paths to saved files
        """
        saved_files = []
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            'url', 'domain', 'products', 'customers', 
            'partnerships', 'case_studies', 'extraction_status',
            'scraper_type', 'elapsed_ms'
        ]
        
        # Write to main output file (append if exists)
        file_exists = Path(output_file).exists()
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            for domain_result in batch_result.results:
                for record in domain_result.records:
                    row = {
                        'domain': domain_result.domain,
                        'scraper_type': domain_result.scraper_type,
                        'elapsed_ms': domain_result.elapsed_ms,
                        **record
                    }
                    writer.writerow(row)
        
        logger.info(f"Saved batch results to {output_file}")
        saved_files.append(output_file)
        
        # Save domain-specific files
        if save_domain_files:
            output_dir = Path(output_file).parent
            for domain_result in batch_result.results:
                domain_file = self._save_domain_csv(
                    domain_result, 
                    output_dir,
                    fieldnames
                )
                if domain_file:
                    saved_files.append(domain_file)
        
        return saved_files
    
    def _save_domain_csv(
        self,
        domain_result: DomainResult,
        output_dir: Path,
        fieldnames: List[str]
    ) -> Optional[str]:
        """Save results for a single domain to its own CSV file.
        
        Creates file named: {domain_name}_output_data.csv
        E.g., grab_output_data.csv for grab.com
        
        Args:
            domain_result: Result for a single domain
            output_dir: Directory to save the file
            fieldnames: CSV field names
            
        Returns:
            Path to saved file, or None if no records
        """
        if not domain_result.records:
            return None
        
        # Extract clean domain name
        domain_name = extract_domain_name(domain_result.domain)
        domain_file = output_dir / f"{domain_name}_output_data.csv"
        
        with open(domain_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in domain_result.records:
                row = {
                    'domain': domain_result.domain,
                    'scraper_type': domain_result.scraper_type,
                    'elapsed_ms': domain_result.elapsed_ms,
                    **record
                }
                writer.writerow(row)
        
        logger.info(f"Saved domain-specific results to {domain_file}")
        return str(domain_file)


# Convenience function for quick batch processing
async def process_domains(
    domains: List[str],
    max_concurrent: int = 5,
    skip_llm: bool = False,
    rate_limit: bool = True,
    config_path: Optional[str] = None
) -> BatchResult:
    """Quick batch processing of domains.
    
    Args:
        domains: List of domain URLs
        max_concurrent: Maximum concurrent processing
        skip_llm: Skip LLM extraction if True
        rate_limit: Enable rate limiting
        config_path: Optional path to config file
        
    Returns:
        BatchResult with all results
    """
    if config_path:
        processor = BatchProcessor.from_config(config_path)
    else:
        rate_config = RateLimitConfig(enabled=rate_limit) if rate_limit else RateLimitConfig(enabled=False)
        processor = BatchProcessor(
            max_concurrent=max_concurrent,
            rate_limit_config=rate_config
        )
    
    return await processor.process(domains, skip_llm=skip_llm)

